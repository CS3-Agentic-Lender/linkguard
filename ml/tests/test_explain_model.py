"""Working out each feature's push on a link's score from the saved logistic regression model.

The model has the shape the save-the-model work saves: a first step that keeps the 8 final
features out of the ten scaled ones, then logistic regression. These tests build the same
shape on small made-up rows, so their numbers say nothing about the real model.
"""

import math

import numpy as np
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from features.explain import (
    KEEP_STEP,
    MAX_REASONS,
    MODEL_STEP,
    linear_contributions,
    model_coefficients,
    reasons_for_link,
)
from features.hostname import FEATURE_NAMES
from ranking.final_list import FINAL_FEATURES

ROWS = 300


def made_up_scaled_rows(rows: int = ROWS) -> tuple[np.ndarray, np.ndarray]:
    """Ten scaled values per row. Phishing rows have longer names and more digits."""
    generator = np.random.default_rng(0)
    labels = (np.arange(rows) % 3 == 0).astype(int)
    scaled = generator.normal(0, 1, (rows, len(FEATURE_NAMES)))
    scaled[:, FEATURE_NAMES.index("HostnameLength")] += 1.5 * labels
    scaled[:, FEATURE_NAMES.index("NoOfDigitsInHostname")] += 1.0 * labels
    return scaled, labels


def saved_shape_model(labels_offset: int = 0) -> Pipeline:
    """The saved model's shape, fitted on made-up rows."""
    keep = [FEATURE_NAMES.index(name) for name in FINAL_FEATURES]
    model = Pipeline(
        [
            (KEEP_STEP, ColumnTransformer([("final", "passthrough", keep)], remainder="drop")),
            (MODEL_STEP, LogisticRegression(solver="liblinear", class_weight="balanced", C=0.01)),
        ]
    )
    scaled, labels = made_up_scaled_rows()
    return model.fit(scaled, labels + labels_offset)


def by_name(row: np.ndarray) -> dict[str, float]:
    return dict(zip(FEATURE_NAMES, (float(value) for value in row)))


# Reading the weights out of the saved model


def test_the_weights_are_named_by_the_8_features_the_model_keeps():
    coefficients = model_coefficients(saved_shape_model())

    assert list(coefficients) == list(FINAL_FEATURES)


def test_each_weight_is_the_models_own_coefficient():
    model = saved_shape_model()

    coefficients = model_coefficients(model)

    assert list(coefficients.values()) == pytest.approx(model.named_steps[MODEL_STEP].coef_[0].tolist())


def test_a_model_whose_second_class_is_not_phishing_is_refused():
    with pytest.raises(ValueError, match="phishing"):
        model_coefficients(saved_shape_model(labels_offset=1))  # classes 1 and 2


def test_a_model_keeping_more_features_than_it_has_weights_is_refused():
    model = saved_shape_model()
    keep = model.named_steps[KEEP_STEP]
    keep.transformers_ = [("final", "passthrough", list(range(len(FINAL_FEATURES) + 1)))]

    with pytest.raises(ValueError, match="keeps 9 features but has 8"):
        model_coefficients(model)


def test_a_model_of_another_shape_is_refused():
    plain = LogisticRegression().fit(*made_up_scaled_rows())

    with pytest.raises(ValueError, match="shape"):
        model_coefficients(plain)


# Each feature's push: weight times scaled value


def test_each_push_is_the_weight_times_the_scaled_value():
    contributions = linear_contributions({"HostnameLength": 0.5, "IsDomainIP": -2.0}, {"HostnameLength": 3.0, "IsDomainIP": 1.0})

    assert contributions == {"HostnameLength": 1.5, "IsDomainIP": -2.0}


def test_a_feature_the_model_does_not_use_gets_no_push():
    scaled = by_name(np.ones(len(FEATURE_NAMES)))

    contributions = linear_contributions({"HostnameLength": 0.5}, scaled)

    assert list(contributions) == ["HostnameLength"]


def test_a_model_feature_with_no_scaled_value_is_refused():
    with pytest.raises(ValueError, match="HostnameLength"):
        linear_contributions({"HostnameLength": 0.5}, {"IsDomainIP": 1.0})


def test_the_pushes_add_up_to_the_links_score_minus_an_average_links():
    # An average training link has every scaled value at 0, so its log-odds is the intercept.
    model = saved_shape_model()
    scaled, _ = made_up_scaled_rows()
    row = scaled[:1]

    contributions = linear_contributions(model_coefficients(model), by_name(row[0]))

    log_odds = model.decision_function(row)[0]
    intercept = model.named_steps[MODEL_STEP].intercept_[0]
    assert math.fsum(contributions.values()) == pytest.approx(log_odds - intercept)


# The function the scan calls: a link's scaled features in, up to three reasons out


def test_a_link_with_several_raising_features_gets_up_to_three_largest_first():
    model = saved_shape_model()
    coefficients = model_coefficients(model)
    # Every feature two steps onto the side that raises this model's score.
    row = {name: 2.0 * math.copysign(1.0, coefficients.get(name, 1.0)) for name in FEATURE_NAMES}

    reasons = reasons_for_link(model, row)

    contributions = linear_contributions(coefficients, row)
    assert 1 <= len(reasons) <= MAX_REASONS
    assert all(contributions[name] > 0 for name in reasons)
    assert [contributions[name] for name in reasons] == sorted((contributions[name] for name in reasons), reverse=True)


def test_an_average_link_has_no_reasons():
    reasons = reasons_for_link(saved_shape_model(), by_name(np.zeros(len(FEATURE_NAMES))))

    assert reasons == ()


def test_a_link_on_the_safe_side_of_every_feature_has_no_reasons():
    model = saved_shape_model()
    coefficients = model_coefficients(model)
    row = {name: -2.0 * math.copysign(1.0, coefficients.get(name, 1.0)) for name in FEATURE_NAMES}

    assert reasons_for_link(model, row) == ()


def test_the_same_link_always_gets_the_same_reasons():
    model = saved_shape_model()
    scaled, _ = made_up_scaled_rows()
    row = by_name(scaled[0])

    assert reasons_for_link(model, row) == reasons_for_link(model, row)

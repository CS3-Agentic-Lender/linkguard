"""Working out each feature's push on a link's score from the saved gradient boosting model.

The model has the saved model's shape: a first step that keeps the 8 final features out of
the ten scaled ones, then gradient boosting. The pushes come from SHAP's tree explainer for
that last step, wrapped the way explanation_check does it. These tests build the same shape on small made-up rows, so their numbers
say nothing about the real model.
"""

import math

import numpy as np
import pytest
import shap
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline

from features.explain import (
    KEEP_STEP,
    MAX_REASONS,
    MODEL_STEP,
    RAISING_SIDE,
    kept_features,
    reasons_for_link,
    tree_contributions,
)
from features.hostname import FEATURE_NAMES
from ranking.final_list import FINAL_FEATURES
from training.explanation_check import tree_explainer

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
            (MODEL_STEP, HistGradientBoostingClassifier(max_iter=30, random_state=0)),
        ]
    )
    scaled, labels = made_up_scaled_rows()
    return model.fit(scaled, labels + labels_offset)


@pytest.fixture(scope="module")
def model() -> Pipeline:
    return saved_shape_model()


@pytest.fixture(scope="module")
def explainer(model):
    return tree_explainer(model)


def by_name(row: np.ndarray) -> dict[str, float]:
    return dict(zip(FEATURE_NAMES, (float(value) for value in row)))


def every_feature_at(value_on_raising_side: float) -> dict[str, float]:
    """Every feature this far onto the side its sentence describes (negative: the other side)."""
    return {name: value_on_raising_side * RAISING_SIDE.get(name, 1) for name in FEATURE_NAMES}


def fixed_explainer(answer):
    """Stands in for the tree explainer and always gives the same answer."""
    return lambda values: answer


# Which features the saved model keeps


def test_the_kept_features_are_the_8_final_ones_in_the_models_order(model):
    assert kept_features(model) == tuple(FINAL_FEATURES)


def test_a_model_whose_second_class_is_not_phishing_is_refused():
    with pytest.raises(ValueError, match="phishing"):
        kept_features(saved_shape_model(labels_offset=1))  # classes 1 and 2


def test_a_model_of_another_shape_is_refused():
    plain = HistGradientBoostingClassifier(max_iter=5).fit(*made_up_scaled_rows())

    with pytest.raises(ValueError, match="shape"):
        kept_features(plain)


# Each feature's push, from the tree explainer


def test_every_kept_feature_gets_a_push_and_no_other_does(model, explainer):
    scaled, _ = made_up_scaled_rows()

    contributions = tree_contributions(model, explainer, by_name(scaled[0]))

    assert list(contributions) == list(FINAL_FEATURES)


def test_the_pushes_add_up_to_the_links_score_minus_an_average_links(model, explainer):
    # The explainer's expected value is the average training link's log-odds.
    scaled, _ = made_up_scaled_rows()
    row = scaled[:1]

    contributions = tree_contributions(model, explainer, by_name(row[0]))

    log_odds = model.decision_function(row)[0]
    tree = shap.TreeExplainer(model.named_steps[MODEL_STEP])
    average = float(np.ravel(tree.expected_value)[0])
    assert math.fsum(contributions.values()) == pytest.approx(log_odds - average)


def test_a_kept_feature_with_no_scaled_value_is_refused(model, explainer):
    scaled = every_feature_at(1.0)
    del scaled["HostnameLength"]

    with pytest.raises(ValueError, match="HostnameLength"):
        tree_contributions(model, explainer, scaled)


def test_an_explainer_giving_the_wrong_number_of_pushes_is_refused(model):
    with pytest.raises(ValueError, match="8 features but the explainer gave 3"):
        tree_contributions(model, fixed_explainer([0.1, 0.2, 0.3]), every_feature_at(1.0))


def test_an_explainer_giving_one_answer_per_class_is_refused(model):
    per_class = [[0.1] * len(FINAL_FEATURES), [0.1] * len(FINAL_FEATURES)]

    with pytest.raises(ValueError, match="one push per feature"):
        tree_contributions(model, fixed_explainer(per_class), every_feature_at(1.0))


# The function the scan calls: a link's scaled features in, up to three reasons out


def test_a_link_with_several_raising_features_gets_up_to_three_largest_first(model, explainer):
    row = every_feature_at(2.0)

    reasons = reasons_for_link(model, explainer, row)

    contributions = tree_contributions(model, explainer, row)
    assert 1 <= len(reasons) <= MAX_REASONS
    assert all(contributions[name] > 0 for name in reasons)
    pushes = [contributions[name] for name in reasons]
    assert pushes == sorted(pushes, reverse=True)


def test_an_average_link_has_no_reasons(model, explainer):
    # Every value is at the average, so no sentence is true for the link.
    assert reasons_for_link(model, explainer, by_name(np.zeros(len(FEATURE_NAMES)))) == ()


def test_a_link_on_the_safe_side_of_every_feature_has_no_reasons(model, explainer):
    assert reasons_for_link(model, explainer, every_feature_at(-2.0)) == ()


def test_the_same_link_always_gets_the_same_reasons(model, explainer):
    scaled, _ = made_up_scaled_rows()
    row = by_name(scaled[0])

    assert reasons_for_link(model, explainer, row) == reasons_for_link(model, explainer, row)

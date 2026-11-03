import numpy as np
import pandas as pd
import pytest
from sklearn.decomposition import PCA

from features.hostname import FEATURE_NAMES
from ranking.pca import PcaError, components_to_reach, fit_pca, variance_table
from ranking.training_split import training_split
from splitting.scaling import fit_scaler, scale

ROWS = 400
HUGE = 1e6


def made_up_feature_set(rows: int = ROWS) -> pd.DataFrame:
    """Made-up rows where the first five features move together and the rest are noise."""
    generator = np.random.default_rng(1)
    shared = generator.normal(size=rows)
    frame = pd.DataFrame({"row": range(rows)})
    for position, name in enumerate(FEATURE_NAMES):
        noise = generator.normal(size=rows)
        frame[name] = 3 * shared + noise if position < 5 else noise
    frame["label"] = np.arange(rows) % 2
    frame["host"] = [f"host{row}.example" for row in range(rows)]
    return frame


def made_up_split(rows: int = ROWS) -> pd.DataFrame:
    """Every fourth row is a test row."""
    return pd.DataFrame({"row": range(rows), "set": ["test" if row % 4 == 3 else "train" for row in range(rows)]})


def training_scaler(features: pd.DataFrame, split: pd.DataFrame):
    return fit_scaler(training_split(features, split)[list(FEATURE_NAMES)])


def fitted() -> PCA:
    features, split = made_up_feature_set(), made_up_split()
    return fit_pca(features, split, training_scaler(features, split))


def test_pca_sees_only_the_training_rows():
    features, split = made_up_feature_set(), made_up_split()
    scaler = training_scaler(features, split)
    # Test rows get huge values. If any reached the PCA, the first component would be
    # pulled towards them and the fit would differ from one on the training rows alone.
    poisoned = features.copy()
    is_test = poisoned["row"].isin(split.loc[split["set"] == "test", "row"])
    poisoned.loc[is_test, list(FEATURE_NAMES)] = HUGE

    pca = fit_pca(poisoned, split, scaler)

    training = training_split(features, split)[list(FEATURE_NAMES)]
    alone = PCA(svd_solver="full", random_state=0).fit(scale(scaler, training))
    assert pca.n_samples_ == 300
    np.testing.assert_array_equal(pca.components_, alone.components_)
    np.testing.assert_array_equal(pca.explained_variance_ratio_, alone.explained_variance_ratio_)


def test_the_saved_scaler_is_only_used_to_transform(monkeypatch):
    features, split = made_up_feature_set(), made_up_split()
    scaler = training_scaler(features, split)
    means = scaler.mean_.copy()

    def refuse(*args, **kwargs):
        raise AssertionError("The saved scaler must not be fitted again.")

    for method in ("fit", "fit_transform", "partial_fit"):
        monkeypatch.setattr(scaler, method, refuse)

    fit_pca(features, split, scaler)

    np.testing.assert_array_equal(scaler.mean_, means)


def test_a_scaler_fitted_on_other_rows_stops_the_run():
    features, split = made_up_feature_set(), made_up_split()
    scaler = fit_scaler(features[list(FEATURE_NAMES)])  # all 400 rows, test rows included

    with pytest.raises(PcaError, match="400 rows"):
        fit_pca(features, split, scaler)


def test_fits_all_ten_components():
    pca = fitted()

    assert pca.n_components_ == 10
    assert list(pca.feature_names_in_) == list(FEATURE_NAMES)


def test_a_second_run_gives_the_same_result():
    first = fitted()
    second = fitted()

    np.testing.assert_array_equal(first.components_, second.components_)
    np.testing.assert_array_equal(first.explained_variance_ratio_, second.explained_variance_ratio_)


def test_variance_table_has_each_component_and_the_running_total():
    table = variance_table(fitted())

    assert table["Component"].tolist() == [f"PC{number}" for number in range(1, 11)]
    assert table["Cumulative %"].is_monotonic_increasing
    assert table["Cumulative %"].iloc[-1] == pytest.approx(100)
    np.testing.assert_allclose(table["Variance %"].cumsum(), table["Cumulative %"])


@pytest.mark.parametrize(
    ("ratios", "expected"),
    [
        ([0.5, 0.3, 0.15, 0.05], 3),
        ([0.95, 0.05], 1),
        ([0.6, 0.3, 0.04, 0.06], 4),
    ],
)
def test_components_to_reach_counts_the_fewest_that_reach_95_percent(ratios, expected):
    assert components_to_reach(np.array(ratios)) == expected

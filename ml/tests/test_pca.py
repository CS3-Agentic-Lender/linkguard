import numpy as np
import pandas as pd
import pytest
from sklearn.decomposition import PCA

from features.hostname import FEATURE_NAMES
from ranking.pca import (
    CHART_NAME,
    REPORT_NAME,
    PcaError,
    components_to_reach,
    fit_pca,
    loadings_table,
    main,
    marked_features,
    report,
    takeaway,
    variance_chart,
    variance_table,
)
from ranking.training_split import FEATURES_CSV_NAME, SPLIT_CSV_NAME, training_split
from splitting.scaling import SCALER_FILE_NAME, fit_scaler, save_scaler, scale
from splitting.split import save_split

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


def test_components_to_reach_counts_a_total_of_exactly_95_percent_despite_rounding():
    # These add up to 0.9499999999999998 at three components, not 0.95, because of float rounding.
    ratios = np.array([0.69, 0.18, 0.08, 0.05])

    assert components_to_reach(ratios) == 3


def test_components_to_reach_does_not_count_a_total_really_below_95_percent():
    ratios = np.array([0.69, 0.18, 0.079, 0.051])  # 94.9% at three components

    assert components_to_reach(ratios) == 4


def test_loadings_table_has_the_ten_features_as_rows_and_the_main_components_as_columns():
    pca = fitted()

    table = loadings_table(pca, 3)

    assert table.index.tolist() == list(FEATURE_NAMES)
    assert table.columns.tolist() == ["PC1", "PC2", "PC3"]
    np.testing.assert_array_equal(table.to_numpy(), pca.components_[:3].T)


def test_marks_the_two_largest_weights_by_size_keeping_the_sign_out_of_it():
    loadings = pd.DataFrame(
        {"PC1": [0.1, -0.9, 0.5, 0.2], "PC2": [0.6, 0.6, 0.1, -0.7]},
        index=["a", "b", "c", "d"],
    )

    marked = marked_features(loadings)

    # A tie keeps the feature order, so the result never changes between runs.
    assert marked == {"PC1": ["b", "c"], "PC2": ["d", "a"]}


def test_a_scaler_for_other_columns_stops_the_run():
    features, split = made_up_feature_set(), made_up_split()
    training = training_split(features, split)
    scaler = fit_scaler(training[list(reversed(FEATURE_NAMES))])

    with pytest.raises(PcaError, match="columns"):
        fit_pca(features, split, scaler)


def test_takeaway_names_how_many_components_reach_95_percent():
    pca = fitted()
    count = components_to_reach(pca.explained_variance_ratio_)
    reached = 100 * pca.explained_variance_ratio_[:count].sum()

    assert takeaway(pca) == f"It takes {count} of the 10 components to reach 95% of the variance ({reached:.1f}% in all)."


def test_chart_plots_the_cumulative_variance_for_all_ten_components():
    pca = fitted()

    figure = variance_chart(pca)

    (axis,) = figure.get_axes()
    (line,) = [line for line in axis.get_lines() if line.get_marker() == "o"]
    assert list(line.get_xdata()) == list(range(1, 11))
    np.testing.assert_allclose(line.get_ydata(), 100 * np.cumsum(pca.explained_variance_ratio_))


def test_chart_has_a_dashed_line_at_95_percent():
    (axis,) = variance_chart(fitted()).get_axes()

    dashed = [line for line in axis.get_lines() if line.get_linestyle() == "--"]
    assert len(dashed) == 1
    assert list(dashed[0].get_ydata()) == [95, 95]


def test_chart_has_labelled_axes_a_title_and_the_takeaway():
    pca = fitted()

    figure = variance_chart(pca)

    (axis,) = figure.get_axes()
    assert axis.get_xlabel() == "Number of components"
    assert axis.get_ylabel() == "Cumulative explained variance (%)"
    assert figure.get_suptitle()
    assert axis.get_title() == takeaway(pca)


def test_report_has_the_variance_table_the_loadings_table_and_the_notes():
    pca = fitted()
    count = components_to_reach(pca.explained_variance_ratio_)

    page = report(pca)

    assert "Training rows: 300." in page
    assert "| PC1 |" in page and "| PC10 |" in page
    loadings_header = "| Feature | " + " | ".join(f"PC{number}" for number in range(1, count + 1)) + " | Marked on |"
    assert loadings_header in page
    feature_rows = [line for line in page.splitlines() if line.startswith("| `")]
    assert len(feature_rows) == 10
    assert sum(row.count("**") for row in feature_rows) == 2 * 2 * count  # two bold cells per main component
    assert takeaway(pca) in page
    assert "never used as model inputs" in page
    assert "Pipeline" in page


def test_report_shows_signed_weights_to_two_decimals():
    pca = fitted()
    weight = pca.components_[0][0]

    page = report(pca)

    row = next(line for line in page.splitlines() if line.startswith(f"| `{FEATURE_NAMES[0]}` |"))
    assert f"{weight:.2f}" in row


def write_inputs(ml_dir, features: pd.DataFrame, split: pd.DataFrame) -> None:
    (ml_dir / "data").mkdir()
    features.to_csv(ml_dir / "data" / FEATURES_CSV_NAME, index=False)
    save_split(split.set_index("row")["set"], features.set_index("row")["host"], ml_dir / "data" / SPLIT_CSV_NAME)
    save_scaler(training_scaler(features, split), ml_dir / "models" / SCALER_FILE_NAME)


def test_main_saves_the_report_and_the_chart_and_returns_0(tmp_path, capsys):
    write_inputs(tmp_path, made_up_feature_set(), made_up_split())

    code = main(tmp_path)

    assert code == 0
    page = (tmp_path / "reports" / REPORT_NAME).read_text()
    assert "Training rows: 300." in page
    assert f"![Cumulative explained variance]({CHART_NAME})" in page
    assert (tmp_path / "reports" / CHART_NAME).read_bytes().startswith(b"\x89PNG")
    assert "Saved" in capsys.readouterr().out


def test_main_gives_the_same_report_on_a_second_run(tmp_path):
    write_inputs(tmp_path, made_up_feature_set(), made_up_split())

    main(tmp_path)
    first = (tmp_path / "reports" / REPORT_NAME).read_text()
    main(tmp_path)

    assert (tmp_path / "reports" / REPORT_NAME).read_text() == first


@pytest.mark.parametrize("absent", [FEATURES_CSV_NAME, SPLIT_CSV_NAME, SCALER_FILE_NAME])
def test_main_explains_a_missing_input_saves_nothing_and_returns_1(tmp_path, capsys, absent):
    write_inputs(tmp_path, made_up_feature_set(), made_up_split())
    folder = "models" if absent == SCALER_FILE_NAME else "data"
    (tmp_path / folder / absent).unlink()

    code = main(tmp_path)

    assert code == 1
    assert not (tmp_path / "reports").exists()
    out = capsys.readouterr().out
    assert out.startswith("PCA stopped:")
    assert absent in out


def test_main_stops_when_the_split_check_fails(tmp_path, capsys):
    features = made_up_feature_set()
    write_inputs(tmp_path, features, made_up_split())
    # The cleaned data was rebuilt since the split was made: row 2 now has another host.
    features.loc[features["row"] == 2, "host"] = "other.example"
    features.to_csv(tmp_path / "data" / FEATURES_CSV_NAME, index=False)

    code = main(tmp_path)

    assert code == 1
    assert not (tmp_path / "reports").exists()
    assert capsys.readouterr().out.startswith("PCA stopped:")

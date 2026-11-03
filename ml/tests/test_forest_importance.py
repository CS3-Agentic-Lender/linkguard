import numpy as np
import pandas as pd
import pytest

from features.hostname import FEATURE_NAMES
from ranking.forest_importance import REPORT_NAME, forest_importance, main, report
from ranking.training_split import FEATURES_CSV_NAME, SPLIT_CSV_NAME
from splitting.split import save_split

ROWS = 400


def made_up_feature_set(rows: int = ROWS) -> pd.DataFrame:
    """Made-up rows where HostnameLength follows the label closely and the rest is noise."""
    generator = np.random.default_rng(1)
    label = np.arange(rows) % 2
    frame = pd.DataFrame({"row": range(rows)})
    for name in FEATURE_NAMES:
        frame[name] = generator.integers(0, 5, rows)
    frame["HostnameLength"] = 10 + 20 * label + generator.integers(0, 3, rows)
    frame["label"] = label
    frame["host"] = [f"host{row}.example" for row in range(rows)]
    return frame


def made_up_split(rows: int = ROWS) -> pd.DataFrame:
    """Every fourth row is a test row."""
    return pd.DataFrame({"row": range(rows), "set": ["test" if row % 4 == 3 else "train" for row in range(rows)]})


def ranked() -> pd.DataFrame:
    return forest_importance(made_up_feature_set(), made_up_split())


def test_table_lists_all_ten_features_highest_importance_first():
    table = ranked()

    assert sorted(table["Feature"]) == sorted(FEATURE_NAMES)
    assert table["Rank"].tolist() == list(range(1, 11))
    assert table["Importance"].is_monotonic_decreasing
    assert table.loc[0, "Feature"] == "HostnameLength"


def test_importances_add_up_to_one():
    assert ranked()["Importance"].sum() == pytest.approx(1.0)


def test_a_second_run_gives_the_same_order_and_scores():
    pd.testing.assert_frame_equal(ranked(), ranked())


def test_test_rows_do_not_change_the_importances():
    features = made_up_feature_set()
    split = made_up_split()
    baseline = forest_importance(features, split)

    # Test rows get extreme values and flipped labels. If any reached the forest, the
    # importances would move.
    test_rows = split.loc[split["set"] == "test", "row"]
    poisoned = features.copy()
    is_test = poisoned["row"].isin(test_rows)
    for name in FEATURE_NAMES:
        poisoned.loc[is_test, name] = 999
    poisoned.loc[is_test, "label"] = 1 - poisoned.loc[is_test, "label"]

    pd.testing.assert_frame_equal(forest_importance(poisoned, split), baseline)


def test_ties_keep_the_extractor_order():
    features = made_up_feature_set()
    for name in FEATURE_NAMES:
        if name != "HostnameLength":
            features[name] = 1  # a constant feature is never used to split, so it scores 0

    table = forest_importance(features, made_up_split())

    tied = table[table["Feature"] != "HostnameLength"]
    assert (tied["Importance"] == 0).all()
    assert tied["Feature"].tolist() == [name for name in FEATURE_NAMES if name != "HostnameLength"]


def test_report_has_the_table_row_count_seed_and_bias_note():
    page = report(ranked(), 1234)

    assert "| 1 | `HostnameLength` |" in page
    assert page.count("\n| ") == 11  # header and ten features
    assert "Training rows: 1,234. Seed: 0. Trees: 100." in page
    assert "many different values" in page


def test_main_saves_the_report_and_returns_0(tmp_path, capsys):
    (tmp_path / "data").mkdir()
    features = made_up_feature_set()
    features.to_csv(tmp_path / "data" / FEATURES_CSV_NAME, index=False)
    save_split(made_up_split().set_index("row")["set"], features.set_index("row")["host"], tmp_path / "data" / SPLIT_CSV_NAME)

    code = main(tmp_path)

    assert code == 0
    saved = (tmp_path / "reports" / REPORT_NAME).read_text()
    assert "Training rows: 300." in saved
    assert "Saved to" in capsys.readouterr().out


@pytest.mark.parametrize("present", [FEATURES_CSV_NAME, SPLIT_CSV_NAME])
def test_main_explains_a_missing_input_saves_nothing_and_returns_1(tmp_path, capsys, present):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / present).touch()

    code = main(tmp_path)

    assert code == 1
    assert not (tmp_path / "reports" / REPORT_NAME).exists()
    assert "Random forest importance stopped:" in capsys.readouterr().out

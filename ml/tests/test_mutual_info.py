import numpy as np
import pandas as pd
import pytest

from features.hostname import FEATURE_NAMES
from ranking import mutual_info
from ranking.mutual_info import REPORT_NAME, main, mutual_information, report
from ranking.training_split import FEATURES_CSV_NAME, SPLIT_CSV_NAME, training_split

ROWS = 400


def made_up_feature_set(rows: int = ROWS) -> pd.DataFrame:
    """Made-up rows where HostnameLength follows the label closely and the rest is noise."""
    generator = np.random.default_rng(1)
    label = np.arange(rows) % 2
    frame = pd.DataFrame({"row": range(rows)})
    for name in FEATURE_NAMES:
        if name in mutual_info.CONTINUOUS_FEATURES:
            frame[name] = generator.random(rows)
        else:
            frame[name] = generator.integers(0, 5, rows)
    frame["HostnameLength"] = 10 + 20 * label + generator.integers(0, 3, rows)
    frame["label"] = label
    frame["host"] = [f"host{row}.example" for row in range(rows)]
    return frame


def made_up_split(rows: int = ROWS) -> pd.DataFrame:
    """Every fourth row is a test row."""
    return pd.DataFrame({"row": range(rows), "set": ["test" if row % 4 == 3 else "train" for row in range(rows)]})


def training_rows() -> pd.DataFrame:
    return training_split(made_up_feature_set(), made_up_split())


def test_table_lists_all_ten_features_highest_score_first():
    table = mutual_information(training_rows())

    assert sorted(table["Feature"]) == sorted(FEATURE_NAMES)
    assert table["Rank"].tolist() == list(range(1, 11))
    assert table["Score"].is_monotonic_decreasing
    assert table.loc[0, "Feature"] == "HostnameLength"


def test_a_second_run_gives_the_same_scores():
    first = mutual_information(training_rows())
    second = mutual_information(training_rows())

    pd.testing.assert_frame_equal(first, second)


def test_test_rows_do_not_change_the_scores():
    features = made_up_feature_set()
    split = made_up_split()
    baseline = mutual_information(training_split(features, split))

    # Test rows get extreme values and flipped labels. If any reached the scoring, the
    # scores would move.
    test_rows = split.loc[split["set"] == "test", "row"]
    poisoned = features.copy()
    is_test = poisoned["row"].isin(test_rows)
    for name in FEATURE_NAMES:
        poisoned.loc[is_test, name] = 999
    poisoned.loc[is_test, "label"] = 1 - poisoned.loc[is_test, "label"]

    pd.testing.assert_frame_equal(mutual_information(training_split(poisoned, split)), baseline)


def test_the_three_ratios_are_the_continuous_features():
    assert set(mutual_info.CONTINUOUS_FEATURES) == {name for name in FEATURE_NAMES if "Ratio" in name}


def test_ties_keep_the_extractor_order():
    # A constant discrete feature scores exactly 0. Constant continuous features are left
    # out: the estimator's added noise can give them a small score on so few rows.
    discrete = [name for name in FEATURE_NAMES if name not in mutual_info.CONTINUOUS_FEATURES]
    training = training_rows()
    for name in discrete:
        training[name] = 1

    table = mutual_information(training)

    tied = table[table["Feature"].isin(discrete)]
    assert (tied["Score"] == 0).all()
    assert tied["Feature"].tolist() == discrete


def test_report_has_the_table_row_count_seed_and_unit():
    table = mutual_information(training_rows())

    page = report(table, 1234)

    assert "| 1 | `HostnameLength` |" in page
    assert page.count("\n| ") == 11  # header and ten features
    assert "Training rows: 1,234. Seed: 0." in page
    assert "nats" in page


def test_main_saves_the_report_and_returns_0(tmp_path, capsys):
    (tmp_path / "data").mkdir()
    made_up_feature_set().to_csv(tmp_path / "data" / FEATURES_CSV_NAME, index=False)
    made_up_split().to_csv(tmp_path / "data" / SPLIT_CSV_NAME, index=False)

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
    assert "Mutual information stopped:" in capsys.readouterr().out

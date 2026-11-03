import numpy as np
import pandas as pd
import pytest

from features.hostname import FEATURE_NAMES
from ranking.held_out_importance import (
    HELD_OUT_SHARE,
    REPORT_NAME,
    held_out_importance,
    inner_split,
    main,
    report,
)
from ranking.training_split import FEATURES_CSV_NAME, SPLIT_CSV_NAME, training_split
from splitting.split import save_split

ROWS = 600


def made_up_feature_set(rows: int = ROWS) -> pd.DataFrame:
    """Made-up rows where HostnameLength follows the label closely and the rest is noise.

    Rows share hosts (12 rows per host), so grouping by host matters.
    """
    generator = np.random.default_rng(1)
    host_number = np.arange(rows) // 12
    label = host_number % 2
    frame = pd.DataFrame({"row": range(rows)})
    for name in FEATURE_NAMES:
        frame[name] = generator.integers(0, 5, rows)
    frame["HostnameLength"] = 10 + 20 * label + generator.integers(0, 3, rows)
    frame["label"] = label
    frame["host"] = [f"host{number}.example" for number in host_number]
    return frame


def made_up_split(rows: int = ROWS) -> pd.DataFrame:
    """Every fifth host is a test host."""
    host_number = np.arange(rows) // 12
    return pd.DataFrame({"row": range(rows), "set": np.where(host_number % 5 == 4, "test", "train")})


def result():
    return held_out_importance(made_up_feature_set(), made_up_split())


def test_table_lists_all_ten_features_biggest_drop_first():
    table = result().table

    assert sorted(table["Feature"]) == sorted(FEATURE_NAMES)
    assert table["Rank"].tolist() == list(range(1, 11))
    assert table["Accuracy drop"].is_monotonic_decreasing
    assert table.loc[0, "Feature"] == "HostnameLength"


def test_no_host_is_on_both_sides_of_the_inner_split():
    training = training_split(made_up_feature_set(), made_up_split())
    hosts = made_up_feature_set().set_index("row").loc[training["row"], "host"].to_numpy()

    learn, held_out = inner_split(hosts)

    assert set(hosts[learn]).isdisjoint(hosts[held_out])
    assert len(learn) + len(held_out) == len(training)
    assert len(held_out) / len(training) == pytest.approx(HELD_OUT_SHARE, abs=0.1)


def test_a_second_run_gives_the_same_result():
    first, second = result(), result()

    pd.testing.assert_frame_equal(first.table, second.table)
    assert (first.learned_accuracy, first.held_out_accuracy) == (second.learned_accuracy, second.held_out_accuracy)


def test_test_rows_do_not_change_the_result():
    features = made_up_feature_set()
    split = made_up_split()
    baseline = held_out_importance(features, split)

    # Test rows get extreme values and flipped labels. If any reached the forest or the
    # held-out scoring, the result would move.
    is_test = features["row"].isin(split.loc[split["set"] == "test", "row"])
    poisoned = features.copy()
    for name in FEATURE_NAMES:
        poisoned.loc[is_test, name] = 999
    poisoned.loc[is_test, "label"] = 1 - poisoned.loc[is_test, "label"]

    again = held_out_importance(poisoned, split)
    pd.testing.assert_frame_equal(again.table, baseline.table)
    assert again.held_out_accuracy == baseline.held_out_accuracy


def test_report_has_the_table_accuracies_and_method():
    outcome = result()

    page = report(outcome)

    assert "| 1 | `HostnameLength` |" in page
    assert page.count("\n| ") == 11  # header and ten features
    assert "held-out training hosts" in page
    assert f"{outcome.held_out_accuracy:.3f}" in page
    assert "test split is never used" in page


def test_main_saves_the_report_and_returns_0(tmp_path, capsys):
    (tmp_path / "data").mkdir()
    features = made_up_feature_set()
    features.to_csv(tmp_path / "data" / FEATURES_CSV_NAME, index=False)
    save_split(made_up_split().set_index("row")["set"], features.set_index("row")["host"], tmp_path / "data" / SPLIT_CSV_NAME)

    code = main(tmp_path)

    assert code == 0
    assert (tmp_path / "reports" / REPORT_NAME).exists()
    assert "Saved to" in capsys.readouterr().out


def test_main_explains_a_missing_input_saves_nothing_and_returns_1(tmp_path, capsys):
    (tmp_path / "data").mkdir()

    code = main(tmp_path)

    assert code == 1
    assert not (tmp_path / "reports" / REPORT_NAME).exists()
    assert "Held-out importance stopped:" in capsys.readouterr().out

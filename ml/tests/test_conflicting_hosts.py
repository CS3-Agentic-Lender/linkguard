import pandas as pd

from featureset.build import OUTPUT_COLUMNS, output_path
from features.hostname import FEATURE_NAMES
from leakage.conflicting_hosts import (
    HostCount,
    conflicting_hosts,
    count_by_set,
    count_conflicting,
    main,
)
from splitting.split import SET_COLUMN, SPLIT_CSV_NAME, TEST_SET, TRAIN_SET, save_split

# Made-up rows. mixed.example and both.example have both labels. Every other host
# has one label only. The index has gaps, like the cleaned data after duplicates
# are removed.
ROWS = pd.DataFrame(
    {
        "host": [
            "mixed.example", "mixed.example", "mixed.example",
            "both.example", "both.example",
            "safe.example", "safe.example",
            "bad.example",
            "plain.example",
        ],
        "label": [0, 1, 1, 1, 0, 0, 0, 1, 0],
    },
    index=[0, 2, 3, 5, 6, 8, 9, 11, 12],
)

# mixed.example and safe.example are in training. both.example, bad.example and
# plain.example are in the test set. Each host is in one set only, like the shared split.
SPLIT = pd.Series(
    [TRAIN_SET, TRAIN_SET, TRAIN_SET, TEST_SET, TEST_SET, TRAIN_SET, TRAIN_SET, TEST_SET, TEST_SET],
    index=ROWS.index,
    name=SET_COLUMN,
)


def test_finds_exactly_the_hosts_with_both_labels():
    assert conflicting_hosts(ROWS) == {"mixed.example", "both.example"}


def test_finds_no_host_when_every_host_has_one_label():
    one_label = ROWS[~ROWS["host"].isin({"mixed.example", "both.example"})]

    assert conflicting_hosts(one_label) == set()


def test_counts_the_hosts_with_both_labels_and_all_their_rows():
    assert count_conflicting(ROWS) == HostCount(hosts=2, rows=5)


def test_counts_the_hosts_with_both_labels_in_each_set():
    counts = count_by_set(ROWS, SPLIT)

    assert counts == {TRAIN_SET: HostCount(hosts=1, rows=3), TEST_SET: HostCount(hosts=1, rows=2)}


def test_a_set_with_no_such_host_counts_zero():
    all_training = pd.Series(TRAIN_SET, index=ROWS.index)

    counts = count_by_set(ROWS, all_training)

    assert counts == {TRAIN_SET: HostCount(hosts=2, rows=5), TEST_SET: HostCount(hosts=0, rows=0)}


def _feature_table(rows: pd.DataFrame) -> pd.DataFrame:
    """A training feature set for the made-up rows: the real columns, with made-up feature values."""
    table = rows.rename_axis("row").reset_index()
    for name in FEATURE_NAMES:
        table[name] = 0
    return table[list(OUTPUT_COLUMNS)]


def _save_inputs(ml_dir, rows=ROWS, split=SPLIT):
    path = output_path(ml_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    _feature_table(rows).to_csv(path, index=False)
    save_split(split, rows["host"], ml_dir / "data" / SPLIT_CSV_NAME)


def test_main_prints_the_counts_overall_and_in_each_set_and_returns_0(tmp_path, capsys):
    _save_inputs(tmp_path)

    code = main(tmp_path)

    assert code == 0
    out = capsys.readouterr().out
    assert "Hosts with both labels: 2, with 5 of 9 rows." in out
    assert "Training: 1 host, 3 rows." in out
    assert "Test: 1 host, 2 rows." in out


def test_main_reads_a_host_called_null_as_text(tmp_path, capsys):
    # pandas would read "null" as a missing value unless told not to.
    rows = ROWS.assign(host=ROWS["host"].replace("bad.example", "null"))
    _save_inputs(tmp_path, rows=rows)

    assert main(tmp_path) == 0
    assert "Hosts with both labels: 2, with 5 of 9 rows." in capsys.readouterr().out


def test_main_explains_a_missing_feature_set_and_returns_1(tmp_path, capsys):
    code = main(tmp_path)

    assert code == 1
    out = capsys.readouterr().out
    assert "The training feature set was not found" in out
    assert "uv run python -m featureset.build" in out


def test_main_explains_a_missing_split_and_returns_1(tmp_path, capsys):
    _save_inputs(tmp_path)
    (tmp_path / "data" / SPLIT_CSV_NAME).unlink()

    code = main(tmp_path)

    assert code == 1
    out = capsys.readouterr().out
    assert "The split was not found" in out
    assert "uv run python -m splitting.build" in out


def test_main_stops_with_a_message_when_the_split_belongs_to_other_data(tmp_path, capsys):
    _save_inputs(tmp_path)
    reordered = ROWS.iloc[::-1]
    path = output_path(tmp_path)
    _feature_table(reordered).to_csv(path, index=False)

    code = main(tmp_path)

    assert code == 1
    assert "uv run python -m splitting.build" in capsys.readouterr().out

"""Count the hosts that appear with both labels, overall and in each set of the shared split.

A host with both labels has at least one legitimate row and at least one phishing
row. Every row has the same ten features as the other rows on its host, so these
rows give the model one input with two answers.

Reads ml/data/training_features.csv and the shared split in ml/data/split.csv.
Links are only read as text. Nothing is opened or fetched.

Run from ml/:  uv run python -m leakage.conflicting_hosts
"""

import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from cleaning.labels import LABEL_COLUMN
from featureset.build import HOST_COLUMN, ROW_COLUMN, output_path
from splitting.split import REBUILD_HINT, SETS, SPLIT_CSV_NAME, TEST_SET, TRAIN_SET, SplitMismatchError, load_split

FEATURE_SET_HINT = "Make it first with `uv run python -m featureset.build`."
SET_NAMES = {TRAIN_SET: "Training", TEST_SET: "Test"}


@dataclass(frozen=True)
class HostCount:
    hosts: int
    rows: int


def conflicting_hosts(rows: pd.DataFrame) -> set[str]:
    """Return the hosts that have rows with both labels. rows needs a host and a label column."""
    labels_per_host = rows.groupby(HOST_COLUMN)[LABEL_COLUMN].nunique()
    return set(labels_per_host[labels_per_host > 1].index)


def count_conflicting(rows: pd.DataFrame) -> HostCount:
    """How many hosts have both labels, and how many rows those hosts have between them."""
    hosts = conflicting_hosts(rows)
    return HostCount(hosts=len(hosts), rows=int(rows[HOST_COLUMN].isin(hosts).sum()))


def count_by_set(rows: pd.DataFrame, split: pd.Series) -> dict[str, HostCount]:
    """The same counts for each set of the split, keyed by set name.

    The hosts are found from every row. The split keeps each host in one set, so
    each host is counted in one set only.
    """
    hosts = conflicting_hosts(rows)
    counts = {}
    for name in SETS:
        in_set = rows[(split == name) & rows[HOST_COLUMN].isin(hosts)]
        counts[name] = HostCount(hosts=in_set[HOST_COLUMN].nunique(), rows=len(in_set))
    return counts


def _plural(count: int, noun: str) -> str:
    return f"{count:,} {noun if count == 1 else noun + 's'}"


def _load_inputs(ml_dir: Path) -> tuple[pd.DataFrame, pd.Series]:
    """The training feature set keyed by row, and its split. Raises FileNotFoundError or SplitMismatchError."""
    features_path = output_path(ml_dir)
    if not features_path.is_file():
        raise FileNotFoundError(f"The training feature set was not found at {features_path}. {FEATURE_SET_HINT}")
    split_path = ml_dir / "data" / SPLIT_CSV_NAME
    if not split_path.is_file():
        raise FileNotFoundError(f"The split was not found at {split_path}. {REBUILD_HINT}")
    # keep_default_na=False keeps a host such as "null" as text instead of a missing value.
    table = pd.read_csv(features_path, keep_default_na=False, dtype={HOST_COLUMN: str})
    rows = table.set_index(ROW_COLUMN).rename_axis(None)
    # load_split checks that the split was made from these same rows, in this order.
    split = load_split(split_path, rows[HOST_COLUMN])
    return rows, split.reindex(rows.index)


def main(ml_dir: Path) -> int:
    """Print the counts overall and in each set. Returns 1 with a plain message if an input is missing or wrong."""
    try:
        rows, split = _load_inputs(ml_dir)
    except (FileNotFoundError, SplitMismatchError) as error:
        print(error)
        return 1
    total = count_conflicting(rows)
    print(f"Hosts with both labels: {total.hosts:,}, with {total.rows:,} of {len(rows):,} rows.")
    for name, count in count_by_set(rows, split).items():
        print(f"{SET_NAMES[name]}: {_plural(count.hosts, 'host')}, {_plural(count.rows, 'row')}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parents[1]))

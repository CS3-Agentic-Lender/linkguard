"""Split the cleaned rows once into training and test sets, grouped by hostname.

The features come from the hostname only, so every link on one host has the same
features. If a host were in both sets, the model would be tested on rows it had
effectively already seen. So all rows of a host go into the same set, and the
phishing share is kept about the same in both sets (stratified by label).

The split is saved under ml/data/ (gitignored) so that training and evaluation
load this one split and never make their own.
"""

from pathlib import Path

import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

SPLIT_SEED = 42
# One fold of five is held out, so the test set is about 20% of the rows.
FOLD_COUNT = 5
TRAIN_SET = "train"
TEST_SET = "test"
SPLIT_CSV_NAME = "split.csv"
ROW_COLUMN = "row"
SET_COLUMN = "set"


def _check_inputs(labels: pd.Series, hosts: pd.Series) -> None:
    if not labels.index.equals(hosts.index):
        raise ValueError("Labels and hosts must cover the same rows in the same order.")
    if hosts.isna().any() or (hosts == "").any():
        raise ValueError("Every row needs a cleaned host to group by.")


def split_by_host(labels: pd.Series, hosts: pd.Series, seed: int = SPLIT_SEED) -> pd.Series:
    """Return TRAIN_SET or TEST_SET for each row, keyed by the rows' index.

    Rows with the same host always land in the same set. The same inputs and seed
    always give the same split.
    """
    _check_inputs(labels, hosts)
    folds = StratifiedGroupKFold(n_splits=FOLD_COUNT, shuffle=True, random_state=seed)
    _, test_positions = next(folds.split(labels.to_frame(), labels, groups=hosts))
    sets = pd.Series(TRAIN_SET, index=labels.index, name=SET_COLUMN)
    sets.iloc[test_positions] = TEST_SET
    return sets


def hosts_in_both(hosts: pd.Series, split: pd.Series) -> set[str]:
    """Return the hosts that have rows in both the training and the test set."""
    train_hosts = set(hosts[split == TRAIN_SET])
    test_hosts = set(hosts[split == TEST_SET])
    return train_hosts & test_hosts


def phishing_share_gap(labels: pd.Series, split: pd.Series) -> float:
    """Largest gap, in percentage points, between a set's phishing share and the whole data's."""
    whole = labels.mean()
    gaps = [abs(labels[split == name].mean() - whole) for name in (TRAIN_SET, TEST_SET)]
    return 100 * max(gaps)


def save_split(split: pd.Series, path: Path) -> Path:
    """Write each row's index and set to path, creating its folder if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    split.rename_axis(ROW_COLUMN).reset_index().to_csv(path, index=False)
    return path


def load_split(path: Path) -> pd.Series:
    """Read a split written by save_split(), keyed by the original row index."""
    table = pd.read_csv(path)
    return table.set_index(ROW_COLUMN)[SET_COLUMN].rename_axis(None)

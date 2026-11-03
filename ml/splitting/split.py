"""Split the cleaned rows once into training and test sets, grouped by hostname.

The features come from the hostname only, so every link on one host has the same
features. If a host were in both sets, the model would be tested on rows it had
effectively already seen. So all rows of a host go into the same set, and the
phishing share is kept about the same in both sets (stratified by label).

The split is saved under ml/data/ (gitignored) so that training and evaluation
load this one split and never make their own. Next to it goes a small check file
with the row count and a fingerprint of the hosts, so loading the split against
cleaned data that was rebuilt or reordered stops instead of quietly mixing sets.
"""

import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

SPLIT_SEED = 42
# One fold of five is held out, so the test set is about 20% of the rows.
FOLD_COUNT = 5
TRAIN_SET = "train"
TEST_SET = "test"
SPLIT_CSV_NAME = "split.csv"
SPLIT_CHECK_NAME = "split_check.json"
ROW_COLUMN = "row"
SET_COLUMN = "set"
SETS = (TRAIN_SET, TEST_SET)
REBUILD_HINT = "Rebuild it with `uv run python -m splitting.build`."


class SplitMismatchError(ValueError):
    """The saved split does not belong to the cleaned data it is being used with."""


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
    """Return the values (hosts, or whole links) that have rows in both the training and the test set."""
    train_hosts = set(hosts[split == TRAIN_SET])
    test_hosts = set(hosts[split == TEST_SET])
    return train_hosts & test_hosts


def plain_host(link: str) -> str:
    """The link's host as Python's own URL parser reads it, lowercased.

    This is deliberately not the extractor's clean-up, so the leak check does not
    trust the hosts the split was grouped by. It keeps "www.", so it is never coarser
    than the cleaned host: if the cleaned hosts are split correctly, no plain host
    can be in both sets.
    """
    host = urlsplit(link if "//" in link else "//" + link).hostname
    if not host:
        raise ValueError("The link has no host.")
    return host


def empty_sets(split: pd.Series) -> list[str]:
    """Return the names of the sets that have no rows."""
    return [name for name in SETS if not (split == name).any()]


def phishing_share_gap(labels: pd.Series, split: pd.Series) -> float:
    """Largest gap, in percentage points, between a set's phishing share and the whole data's."""
    whole = labels.mean()
    gaps = [abs(labels[split == name].mean() - whole) for name in (TRAIN_SET, TEST_SET)]
    return 100 * max(gaps)


def _check_path(path: Path) -> Path:
    return path.with_name(SPLIT_CHECK_NAME)


def _host_fingerprint(hosts: pd.Series) -> str:
    """A hash of every row number and its host, in row order."""
    digest = hashlib.sha256()
    for row, host in hosts.items():
        digest.update(f"{row}\t{host}\n".encode())
    return digest.hexdigest()


def save_split(split: pd.Series, hosts: pd.Series, path: Path) -> Path:
    """Write each row's index and set to path, and the check file beside it.

    hosts are the cleaned hosts the split was grouped by, one per row.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    split.rename_axis(ROW_COLUMN).reset_index().to_csv(path, index=False)
    check = {"rows": len(hosts), "host_fingerprint": _host_fingerprint(hosts)}
    _check_path(path).write_text(json.dumps(check, indent=2) + "\n")
    return path


def _check_rows(table: pd.DataFrame, hosts: pd.Series) -> None:
    unknown = sorted(set(table[SET_COLUMN].astype(str)) - set(SETS))
    if unknown:
        raise SplitMismatchError(f"The split has set names other than {list(SETS)}: {unknown}. {REBUILD_HINT}")
    rows = table[ROW_COLUMN]
    if rows.duplicated().any() or set(rows) != set(hosts.index):
        raise SplitMismatchError(
            f"Every cleaned row must be in exactly one set, but the split does not match the cleaned rows. {REBUILD_HINT}"
        )


def _check_fingerprint(path: Path, hosts: pd.Series) -> None:
    check_path = _check_path(path)
    if not check_path.exists():
        raise SplitMismatchError(f"The split's check file {check_path.name} is missing. {REBUILD_HINT}")
    check = json.loads(check_path.read_text())
    if check["rows"] != len(hosts):
        raise SplitMismatchError(
            f"The split was made from {check['rows']:,} cleaned rows, but there are {len(hosts):,} now. {REBUILD_HINT}"
        )
    if check["host_fingerprint"] != _host_fingerprint(hosts):
        raise SplitMismatchError(
            f"The split was made from different cleaned data: the hosts are not the same, row by row. {REBUILD_HINT}"
        )


def load_split(path: Path, hosts: pd.Series) -> pd.Series:
    """Read a split written by save_split(), keyed by the original row index.

    hosts are the cleaned hosts of the cleaned data the split will be used with, one
    per row (the feature set's host column, for example). The split is only returned
    if it was made from that same data, row for row.
    """
    table = pd.read_csv(path)
    _check_rows(table, hosts)
    _check_fingerprint(path, hosts)
    return table.set_index(ROW_COLUMN)[SET_COLUMN].rename_axis(None)

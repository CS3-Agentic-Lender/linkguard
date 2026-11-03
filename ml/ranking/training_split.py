"""Read the training split of the saved feature set.

Feature ranking only ever looks at training rows. The test split stays untouched
until model evaluation, so test rows are dropped here, before anything is scored.

The feature set (ml/data/training_features.csv) has a row number, the ten hostname
features, the label and the cleaned host. The saved split (ml/data/split.csv) gives
each row number its set, train or test. The two are joined on the row number, not on
line position, so a feature set with a row missing stops the run instead of shifting.
"""

from pathlib import Path

import pandas as pd

from cleaning.labels import LABEL_COLUMN
from features.hostname import FEATURE_NAMES

FEATURES_CSV_NAME = "training_features.csv"
SPLIT_CSV_NAME = "split.csv"
ROW_COLUMN = "row"
SET_COLUMN = "set"
TRAIN = "train"
TEST = "test"
MISSING_HINTS = {
    FEATURES_CSV_NAME: 'Build it with "uv run python -m featureset.build" (see "The training feature set" in ml/README.md).',
    SPLIT_CSV_NAME: 'Make it with "uv run python -m splitting.build" (see ml/README.md).',
}


class TrainingSplitError(Exception):
    """The feature set or the split cannot give a trustworthy training split."""


def _require_columns(frame: pd.DataFrame, columns: list[str], what: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise TrainingSplitError(f"The {what} is missing the columns {missing}.")


def training_split(features: pd.DataFrame, split: pd.DataFrame) -> pd.DataFrame:
    """The feature set's training rows (row, ten features, label), sorted by row number."""
    _require_columns(features, [ROW_COLUMN, *FEATURE_NAMES, LABEL_COLUMN], "feature set")
    _require_columns(split, [ROW_COLUMN, SET_COLUMN], "split")

    unknown = sorted(set(split[SET_COLUMN].astype(str)) - {TRAIN, TEST})
    if unknown:
        raise TrainingSplitError(f"The split has set names other than {TRAIN!r} and {TEST!r}: {unknown}.")
    for frame, what in ((split, "split"), (features, "feature set")):
        if frame[ROW_COLUMN].duplicated().any():
            raise TrainingSplitError(f"The {what} lists the same row more than once.")

    train_rows = split.loc[split[SET_COLUMN] == TRAIN, ROW_COLUMN]
    if train_rows.empty:
        raise TrainingSplitError("The split has no training rows.")
    # A training row the feature set lacks would rank the features on fewer rows than
    # training uses, so it stops the run rather than being skipped.
    absent = sorted(set(train_rows) - set(features[ROW_COLUMN]))
    if absent:
        raise TrainingSplitError(
            f"{len(absent):,} training rows are not in the feature set, for example row {absent[0]}."
        )

    training = features.loc[features[ROW_COLUMN].isin(train_rows), [ROW_COLUMN, *FEATURE_NAMES, LABEL_COLUMN]]
    if training.isna().any().any():
        raise TrainingSplitError("The training rows have missing values.")
    return training.sort_values(ROW_COLUMN).reset_index(drop=True)


def _read(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except (pd.errors.EmptyDataError, pd.errors.ParserError) as error:
        raise TrainingSplitError(f"{path} could not be read: {error}") from error


def load_inputs(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the feature set and the split from data_dir, stopping with a plain message if either cannot be read."""
    for name, hint in MISSING_HINTS.items():
        path = data_dir / name
        if not path.is_file():
            raise TrainingSplitError(f"{path} was not found. {hint}")
    return _read(data_dir / FEATURES_CSV_NAME), _read(data_dir / SPLIT_CSV_NAME)

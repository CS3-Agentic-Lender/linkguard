"""Load the saved training rows, scale them with the saved scaler, and hand them to the classifiers.

Run it from ml/ with one command:

    uv run python -m training.pipeline

It reads three files that earlier stories save, and makes none of its own:

- the training feature set (FEATURES_PATH): one line per cleaned row with its row number,
  the ten hostname features in the extractor's order, the label (1 = phishing,
  0 = legitimate) and the cleaned host, which is kept for grouping and is never a model input;
- the shared train/test split (SPLIT_PATH): one line per row of the feature set, giving
  its row number and whether it is in the training or the test set;
- the scaler fitted on the training set only (SCALER_PATH).

Leakage rules this module keeps:

- It makes no split. The training rows are exactly the ones the saved split names.
- It fits no scaler. The saved scaler is only used to transform.
- Test rows are never read. Only the training row numbers are taken from the split, and
  the feature file is read with every other line skipped, so test rows never reach memory.

The scaler is a pickle, and loading a pickle runs code. Only load the scaler our own
split-and-scale step saved to ml/models/, never one from anywhere else.
"""

import argparse
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone

from cleaning.labels import LABEL_COLUMN, LEGITIMATE, PHISHING
from features.hostname import FEATURE_NAMES
from leakage.excluded import EXCLUDED_FEATURES

ML_DIR = Path(__file__).resolve().parent.parent

# Where the earlier stories save their files. ml/data/ is gitignored, and so are
# *.joblib files in ml/models/, so none of these is ever committed.
FEATURES_PATH = ML_DIR / "data" / "training_features.csv"
SPLIT_PATH = ML_DIR / "data" / "split.csv"
SCALER_PATH = ML_DIR / "models" / "scaler.joblib"

# Column names in those files.
ROW_COLUMN = "row"
HOSTNAME_COLUMN = "host"
SPLIT_ROW_COLUMN = ROW_COLUMN
SPLIT_SET_COLUMN = "set"
TRAIN = "train"
TEST = "test"

CLASS_NAMES = {PHISHING: "phishing", LEGITIMATE: "legitimate"}


class PipelineError(Exception):
    """A saved file is missing or does not match what the pipeline expects."""


@dataclass(frozen=True)
class TrainingSet:
    """The training rows, ready for the classifiers.

    rows: the row numbers from the saved split, in the order they are used.
    features: the ten features, unscaled, one row per training row (index = row number).
    scaled: the same rows after the saved scaler's transform. Only for fitting a model on
        the whole training part. The saved scaler has seen every training row, so inside
        cross-validation use `features` instead, with the scaler and the model in one
        Pipeline that each fold fits on its own training rows.
    labels: 1 = phishing, 0 = legitimate.
    hostnames: the cleaned hostname of each row, for hostname-grouped cross-validation.
        It is never a model input.
    """

    rows: np.ndarray
    features: pd.DataFrame
    scaled: np.ndarray
    labels: pd.Series
    hostnames: pd.Series


def _require_file(path: Path, what: str) -> None:
    if not path.is_file():
        raise PipelineError(
            f"The {what} was not found at {path}. "
            "It is saved by an earlier step; see \"Training pipeline\" in ml/README.md."
        )


def load_training_rows(split_path: Path) -> np.ndarray:
    """Return the row numbers the saved split puts in the training set, in ascending order."""
    _require_file(split_path, "saved train/test split")
    split = pd.read_csv(split_path)
    expected = [SPLIT_ROW_COLUMN, SPLIT_SET_COLUMN]
    if list(split.columns) != expected:
        raise PipelineError(f"The split file must have the columns {expected}, but it has {list(split.columns)}.")
    if not pd.api.types.is_integer_dtype(split[SPLIT_ROW_COLUMN]):
        raise PipelineError("The split file's row numbers must all be whole numbers.")
    unknown = sorted(set(split[SPLIT_SET_COLUMN].astype(str)) - {TRAIN, TEST})
    if unknown:
        raise PipelineError(f"The split file has set names other than {TRAIN!r} and {TEST!r}: {unknown}.")
    if split[SPLIT_ROW_COLUMN].duplicated().any():
        raise PipelineError("The split file names the same row more than once.")
    if (split[SPLIT_ROW_COLUMN] < 0).any():
        raise PipelineError("The split file has a negative row number.")

    rows = np.sort(split.loc[split[SPLIT_SET_COLUMN] == TRAIN, SPLIT_ROW_COLUMN].to_numpy())
    if rows.size == 0:
        raise PipelineError("The split file has no training rows.")
    return rows


def check_feature_columns(columns: Sequence[str]) -> list[str]:
    """Return the feature matrix columns, or stop if they are not exactly the agreed features.

    The feature matrix is every column of the feature set except the row number, the label
    and the host.
    It must hold the extractor's ten features in the extractor's order and nothing else, and
    any column on the never-a-model-input list stops the pipeline by name.
    """
    matrix = [column for column in columns if column not in (ROW_COLUMN, LABEL_COLUMN, HOSTNAME_COLUMN)]

    excluded = [column for column in matrix if column in EXCLUDED_FEATURES]
    if excluded:
        raise PipelineError(f"Excluded columns must never be model inputs, but the feature matrix has: {excluded}.")

    missing = [name for name in FEATURE_NAMES if name not in matrix]
    extra = [column for column in matrix if column not in FEATURE_NAMES]
    if missing or extra:
        raise PipelineError(
            f"The feature matrix must be the ten hostname features. Missing: {missing}. Not expected: {extra}."
        )
    if tuple(matrix) != FEATURE_NAMES:
        raise PipelineError(
            f"The features are in the wrong order. Expected {list(FEATURE_NAMES)}, got {matrix}."
        )
    for needed in (ROW_COLUMN, LABEL_COLUMN, HOSTNAME_COLUMN):
        if needed not in columns:
            raise PipelineError(f"The feature set has no {needed!r} column.")
    return matrix


def load_training_features(features_path: Path, rows: np.ndarray) -> pd.DataFrame:
    """Read only the given rows of the feature set; every other line of the file is skipped unread.

    The file's lines are expected in row order, so row n is on data line n. Each line also
    carries its row number, and every line read must carry the row the split asked for.
    If a line were ever missing or out of place, the rows would no longer match and the
    pipeline stops instead of training on the wrong rows.
    """
    _require_file(features_path, "training feature set")
    header = pd.read_csv(features_path, nrows=0).columns
    check_feature_columns(list(header))

    wanted = set(rows.tolist())
    # Line 0 is the header; data row n is on line n + 1. Lines for any other row,
    # including every test row, are skipped by the reader and never parsed.
    frame = pd.read_csv(
        features_path,
        skiprows=lambda line: line != 0 and (line - 1) not in wanted,
        keep_default_na=False,
        dtype={HOSTNAME_COLUMN: str},
    )
    if len(frame) != len(rows):
        raise PipelineError(
            f"The split names {len(rows)} training rows, but the feature set only has {len(frame)} of them. "
            "The split and the feature set must come from the same cleaned data."
        )
    if not pd.api.types.is_integer_dtype(frame[ROW_COLUMN]):
        raise PipelineError("The feature set's row numbers must all be whole numbers.")
    mismatched = np.flatnonzero(frame[ROW_COLUMN].to_numpy() != rows)
    if mismatched.size:
        first = mismatched[0]
        raise PipelineError(
            f"The feature set is out of step with the split: the line where row {rows[first]} should be "
            f"holds row {frame[ROW_COLUMN].iloc[first]} "
            f"({mismatched.size} training rows affected). Rebuild the feature set from the same cleaned data."
        )
    frame = frame.set_index(ROW_COLUMN)
    frame.index.name = SPLIT_ROW_COLUMN
    return frame


def check_values(frame: pd.DataFrame) -> None:
    """Stop if a feature is not a finite number or a label is not 0 or 1."""
    for name in FEATURE_NAMES:
        column = frame[name]
        if not pd.api.types.is_numeric_dtype(column) or pd.api.types.is_bool_dtype(column):
            raise PipelineError(f"Feature {name!r} must be numbers only, but it holds {column.dtype} values.")
        if not np.isfinite(column.to_numpy(dtype=float)).all():
            raise PipelineError(f"Feature {name!r} has a missing or infinite value.")

    labels = frame[LABEL_COLUMN]
    if not pd.api.types.is_integer_dtype(labels) or not labels.isin(list(CLASS_NAMES)).all():
        raise PipelineError(f"The label must be {PHISHING} (phishing) or {LEGITIMATE} (legitimate) on every row.")


def load_scaler(scaler_path: Path):
    """Load the saved scaler and check it was fitted on these ten features. It is never refitted."""
    _require_file(scaler_path, "saved scaler")
    scaler = joblib.load(scaler_path)
    if not hasattr(scaler, "transform"):
        raise PipelineError(f"The file at {scaler_path} is not a scaler: it has no transform step.")
    if not hasattr(scaler, "n_features_in_"):
        raise PipelineError("The saved scaler has not been fitted. It must be fitted by the split-and-scale step.")
    if scaler.n_features_in_ != len(FEATURE_NAMES):
        raise PipelineError(
            f"The saved scaler was fitted on {scaler.n_features_in_} features, but the pipeline uses {len(FEATURE_NAMES)}."
        )
    names = getattr(scaler, "feature_names_in_", None)
    if names is not None and tuple(names) != FEATURE_NAMES:
        raise PipelineError(
            f"The saved scaler was fitted on different features or in a different order: {list(names)}."
        )
    return scaler


def load_training_set(
    features_path: Path = FEATURES_PATH,
    split_path: Path = SPLIT_PATH,
    scaler_path: Path = SCALER_PATH,
) -> TrainingSet:
    """Load the training rows named by the saved split and scale them with the saved scaler."""
    scaler = load_scaler(scaler_path)
    rows = load_training_rows(split_path)
    frame = load_training_features(features_path, rows)
    check_values(frame)

    features = frame.loc[:, list(FEATURE_NAMES)]
    scaled = np.asarray(scaler.transform(features), dtype=float)
    return TrainingSet(
        rows=rows,
        features=features,
        scaled=scaled,
        labels=frame[LABEL_COLUMN],
        hostnames=frame[HOSTNAME_COLUMN],
    )


def hand_to_classifiers(classifiers: Mapping[str, object], training_set: TrainingSet) -> dict[str, object]:
    """Fit a fresh copy of each classifier on the same scaled training rows and return them by name.

    This is for fitting on the whole training part only. Do not cross-validate on the
    result: use `training_set.features` with the scaler and the model in one Pipeline.
    """
    return {
        name: clone(classifier).fit(training_set.scaled, training_set.labels.to_numpy())
        for name, classifier in classifiers.items()
    }


def class_counts(labels: pd.Series) -> dict[int, int]:
    """Rows per label, phishing (1) first."""
    return {label: int((labels == label).sum()) for label in (PHISHING, LEGITIMATE)}


def report(training_set: TrainingSet) -> str:
    """A short plain-text summary of what the pipeline loaded."""
    counts = class_counts(training_set.labels)
    lines = [
        f"Training rows from the saved split: {len(training_set.rows)}",
        f"Features ({len(FEATURE_NAMES)}): {', '.join(FEATURE_NAMES)}",
        "Scaled with the saved scaler (transform only, nothing refitted).",
        "Class counts (training set):",
    ]
    lines += [f"  label {label} = {CLASS_NAMES[label]}: {count}" for label, count in counts.items()]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--features", type=Path, default=FEATURES_PATH, help="training feature set CSV")
    parser.add_argument("--split", type=Path, default=SPLIT_PATH, help="saved train/test split CSV")
    parser.add_argument("--scaler", type=Path, default=SCALER_PATH, help="saved scaler (.joblib)")
    args = parser.parse_args(argv)

    try:
        training_set = load_training_set(args.features, args.split, args.scaler)
    except PipelineError as error:
        print(f"Training pipeline stopped: {error}", file=sys.stderr)
        return 1
    print(report(training_set))
    return 0


if __name__ == "__main__":  # pragma: no cover - run as a command, tested through a subprocess
    sys.exit(main())

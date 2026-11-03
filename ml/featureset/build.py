"""Recompute the ten hostname features for every row of the cleaned dataset.

Reads ml/data/phiusiil_cleaned.csv and writes ml/data/training_features.csv.
The features come from the shared extractor, so training and live scans use the
same code. Links are only read as text. Nothing is opened or fetched.

Run from ml/:  uv run python -m featureset.build
"""

import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from cleaning.labels import LABEL_COLUMN
from cleaning.storage import CLEANED_CSV_NAME, load_cleaned
from features.hostname import FEATURE_NAMES, cleaned_host, extract_features

OUTPUT_CSV_NAME = "training_features.csv"
URL_COLUMN = "URL"
ROW_COLUMN = "row"
HOSTNAME_COLUMN = "hostname"
NOT_TEXT_MESSAGE = "The link is not text."
OUTPUT_COLUMNS: tuple[str, ...] = (ROW_COLUMN, *FEATURE_NAMES, LABEL_COLUMN, HOSTNAME_COLUMN)


@dataclass(frozen=True)
class Failure:
    row: int
    reason: str


@dataclass(frozen=True)
class BuildResult:
    features: pd.DataFrame
    failures: tuple[Failure, ...]


def build_feature_set(rows: pd.DataFrame) -> BuildResult:
    """One output row per row whose link can be read, plus every row that could not."""
    records = []
    failures = []
    # Every row is tried, so one run lists all the failures instead of only the first.
    for row, link, label in zip(rows.index, rows[URL_COLUMN], rows[LABEL_COLUMN]):
        # A blank or missing cell is not a string, and the extractor only takes text.
        if not isinstance(link, str):
            failures.append(Failure(int(row), NOT_TEXT_MESSAGE))
            continue
        try:
            features = extract_features(link)
            host = cleaned_host(link)
        except ValueError as error:
            failures.append(Failure(int(row), str(error)))
            continue
        records.append({ROW_COLUMN: int(row), **features, LABEL_COLUMN: label, HOSTNAME_COLUMN: host})
    table = pd.DataFrame(records, columns=list(OUTPUT_COLUMNS))
    return BuildResult(table, tuple(failures))


def failure_lines(failures: tuple[Failure, ...]) -> list[str]:
    """The failure count, then one line per reason with its count and the first row it happened on."""
    counts = Counter(failure.reason for failure in failures)
    first_row: dict[str, int] = {}
    for failure in failures:
        first_row.setdefault(failure.reason, failure.row)
    lines = [f"{len(failures):,} rows failed. No file was written."]
    for reason, count in counts.most_common():
        noun = "row" if count == 1 else "rows"
        lines.append(f"  {count:,} {noun}: {reason} (for example row {first_row[reason]})")
    return lines


def output_path(ml_dir: Path) -> Path:
    """Where the feature set is saved. ml/data/ is gitignored."""
    return ml_dir / "data" / OUTPUT_CSV_NAME


def main(ml_dir: Path) -> int:
    """Build the feature set and save it. Returns 1 and saves nothing if any row fails."""
    rows = load_cleaned(ml_dir / "data" / CLEANED_CSV_NAME)
    result = build_feature_set(rows)
    if result.failures:
        print("\n".join(failure_lines(result.failures)))
        return 1
    path = output_path(ml_dir)
    result.features.to_csv(path, index=False)
    print(f"Built features for {len(result.features):,} of {len(rows):,} rows.")
    print(f"Saved to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parents[1]))

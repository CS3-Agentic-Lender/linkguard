"""Score how much each hostname feature tells about the label, on the training split only.

Mutual information is 0 when a feature tells nothing about the label and grows the more
it does. Unlike correlation it also catches relationships that are not a straight line.
It is one of the two cross-checks on the PCA ranking.

The seven whole-number features are scored as discrete values. The three ratios are
continuous, so scikit-learn estimates them from each row's nearest neighbours, adding a
little random noise first. The fixed seed makes a second run give the same scores.

Writes ml/reports/mutual_information.md. Run from ml/:  uv run python -m ranking.mutual_info
"""

import sys
from pathlib import Path

import pandas as pd
from sklearn.feature_selection import mutual_info_classif

from cleaning.labels import LABEL_COLUMN
from features.hostname import FEATURE_NAMES
from ranking.training_split import SET_COLUMN, TRAIN, TrainingSplitError, load_inputs, training_split

SEED = 0  # fixed so a second run gives the same scores
NEIGHBOURS = 3  # scikit-learn's default, used for the continuous features
CONTINUOUS_FEATURES = ("LetterRatioInHostname", "DigitRatioInHostname", "SpecialCharRatioInHostname")
REPORT_NAME = "mutual_information.md"


def mutual_information(features: pd.DataFrame, split: pd.DataFrame) -> pd.DataFrame:
    """Rank, Feature and Score for the ten features, highest score first.

    Takes the whole feature set and the split, and drops the test rows itself, so no
    caller can hand it test rows by mistake. Ties keep the extractor's feature order,
    so the order never changes between runs.
    """
    training = training_split(features, split)
    discrete = [name not in CONTINUOUS_FEATURES for name in FEATURE_NAMES]
    scores = mutual_info_classif(
        training[list(FEATURE_NAMES)],
        training[LABEL_COLUMN],
        discrete_features=discrete,
        n_neighbors=NEIGHBOURS,
        random_state=SEED,
    )
    table = pd.DataFrame({"Feature": FEATURE_NAMES, "Score": scores})
    table = table.sort_values("Score", ascending=False, kind="stable").reset_index(drop=True)
    table.insert(0, "Rank", range(1, len(table) + 1))
    return table


def report(table: pd.DataFrame, training_rows: int) -> str:
    """The ranking as a Markdown page."""
    lines = [
        "# Mutual information of the ten hostname features",
        "",
        "| Rank | Feature | Score |",
        "|---|---|---|",
        *(f"| {rank} | `{feature}` | {score:.4f} |" for rank, feature, score in table.itertuples(index=False)),
        "",
        f"Training rows: {training_rows:,}. Seed: {SEED}.",
        "",
        "Scores are in nats. 0 means the feature tells nothing about the label.",
        "",
        "Made by `uv run python -m ranking.mutual_info`.",
    ]
    return "\n".join(lines) + "\n"


def main(ml_dir: Path) -> int:
    """Score the training split and save the report. Returns 1 and saves nothing if the inputs are wrong."""
    try:
        features, split = load_inputs(ml_dir / "data")
        table = mutual_information(features, split)
    except TrainingSplitError as error:
        print(f"Mutual information stopped: {error}")
        return 1
    # Every training row is in the feature set (training_split checks it), so this is the row count scored.
    page = report(table, int((split[SET_COLUMN] == TRAIN).sum()))
    path = ml_dir / "reports" / REPORT_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page)
    print(page)
    print(f"Saved to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parents[1]))

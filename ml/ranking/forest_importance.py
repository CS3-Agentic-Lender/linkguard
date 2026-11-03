"""Score how much a random forest leans on each hostname feature, on the training split only.

A random forest is many decision trees, each trained on a random sample of the training
rows. A feature's importance is how much its splits cut the mix of labels, averaged over
every tree. The ten importances add up to 1. It is one of the two cross-checks on the
PCA ranking.

The forest uses the unscaled features, because a tree only compares a feature with its
own thresholds, so scale makes no difference. The fixed seed makes a second run give the
same importances.

This built-in importance tends to favour features with many different values, so it can
overrate some. The report says so, so the ranking is read as a cross-check, not a verdict.

Writes ml/reports/forest_importance.md. Run from ml/:  uv run python -m ranking.forest_importance
"""

import sys
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from cleaning.labels import LABEL_COLUMN
from features.hostname import FEATURE_NAMES
from ranking.training_split import SET_COLUMN, TRAIN, TrainingSplitError, load_inputs, training_split

SEED = 0  # fixed so a second run gives the same importances
TREES = 100  # scikit-learn's default
REPORT_NAME = "forest_importance.md"


def forest_importance(features: pd.DataFrame, split: pd.DataFrame) -> pd.DataFrame:
    """Rank, Feature and Importance for the ten features, highest importance first.

    Takes the whole feature set and the split, and drops the test rows itself, so no
    caller can hand it test rows by mistake. Ties keep the extractor's feature order,
    so the order never changes between runs.
    """
    training = training_split(features, split)
    forest = RandomForestClassifier(n_estimators=TREES, random_state=SEED, n_jobs=-1)
    forest.fit(training[list(FEATURE_NAMES)], training[LABEL_COLUMN])
    table = pd.DataFrame({"Feature": FEATURE_NAMES, "Importance": forest.feature_importances_})
    table = table.sort_values("Importance", ascending=False, kind="stable").reset_index(drop=True)
    table.insert(0, "Rank", range(1, len(table) + 1))
    return table


def report(table: pd.DataFrame, training_rows: int) -> str:
    """The ranking as a Markdown page."""
    lines = [
        "# Random forest importance of the ten hostname features",
        "",
        "| Rank | Feature | Importance |",
        "|---|---|---|",
        *(f"| {rank} | `{feature}` | {score:.4f} |" for rank, feature, score in table.itertuples(index=False)),
        "",
        f"Training rows: {training_rows:,}. Seed: {SEED}. Trees: {TREES}.",
        "",
        "The ten importances add up to 1. This built-in importance tends to favour features with many different values, so read it as a cross-check.",
        "",
        "Made by `uv run python -m ranking.forest_importance`.",
    ]
    return "\n".join(lines) + "\n"


def main(ml_dir: Path) -> int:
    """Train on the training split and save the report. Returns 1 and saves nothing if the inputs are wrong."""
    try:
        features, split = load_inputs(ml_dir / "data")
        table = forest_importance(features, split)
    except TrainingSplitError as error:
        print(f"Random forest importance stopped: {error}")
        return 1
    # Every training row is in the feature set (training_split checks it), so this is the row count used.
    page = report(table, int((split[SET_COLUMN] == TRAIN).sum()))
    path = ml_dir / "reports" / REPORT_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page)
    print(page)
    print(f"Saved to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parents[1]))

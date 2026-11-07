"""Score each hostname feature by how much the forest gets worse without it, on hosts it never learned from.

The built-in forest importance is measured on the rows the forest learned from, and it
favours features with many different values. This is the fairer check. The training split
is cut again by host: 80% of the training hosts teach the forest, and the other 20% are
held out. Then each feature in turn is shuffled on the held-out rows. The bigger the drop
in accuracy, the more the forest relies on that feature. The test split is never used.

The forest is the same as the built-in ranking's: 100 trees, unscaled features, seed 0.
The cut and the shuffles use the same seed, so a second run gives the same result.

Writes ml/reports/held_out_importance.md. Run from ml/:  uv run python -m ranking.held_out_importance
"""

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.model_selection import GroupShuffleSplit

from cleaning.labels import LABEL_COLUMN
from features.hostname import FEATURE_NAMES
from ranking.forest_importance import SEED, TREES
from ranking.training_split import HOST_COLUMN, ROW_COLUMN, TrainingSplitError, load_inputs, training_split

HELD_OUT_SHARE = 0.2  # share of the training hosts held out, as in Ibrahima's check on the forest PR
SHUFFLES = 5  # each feature is shuffled this many times and the drops averaged
REPORT_NAME = "held_out_importance.md"


@dataclass(frozen=True)
class HeldOutResult:
    table: pd.DataFrame
    learned_accuracy: float
    held_out_accuracy: float
    learned_rows: int
    held_out_rows: int


def inner_split(hosts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Positions of the rows that teach the forest and the rows held out, with no host on both sides."""
    cut = GroupShuffleSplit(n_splits=1, test_size=HELD_OUT_SHARE, random_state=SEED)
    learn, held_out = next(cut.split(np.zeros(len(hosts)), groups=hosts))
    return learn, held_out


def held_out_importance(features: pd.DataFrame, split: pd.DataFrame) -> HeldOutResult:
    """Rank the ten features by the accuracy drop on held-out training hosts, biggest first.

    Takes the whole feature set and the split, and drops the test rows itself. Ties keep
    the extractor's feature order.
    """
    training = training_split(features, split)
    hosts = features.set_index(ROW_COLUMN).loc[training[ROW_COLUMN], HOST_COLUMN].to_numpy()
    learn, held_out = inner_split(hosts)
    x = training[list(FEATURE_NAMES)]
    y = training[LABEL_COLUMN]

    forest = RandomForestClassifier(n_estimators=TREES, random_state=SEED, n_jobs=-1)
    forest.fit(x.iloc[learn], y.iloc[learn])
    shuffled = permutation_importance(
        forest, x.iloc[held_out], y.iloc[held_out], n_repeats=SHUFFLES, random_state=SEED, scoring="accuracy"
    )

    table = pd.DataFrame({"Feature": FEATURE_NAMES, "Accuracy drop": shuffled.importances_mean})
    table = table.sort_values("Accuracy drop", ascending=False, kind="stable").reset_index(drop=True)
    table.insert(0, "Rank", range(1, len(table) + 1))
    return HeldOutResult(
        table=table,
        learned_accuracy=float(forest.score(x.iloc[learn], y.iloc[learn])),
        held_out_accuracy=float(forest.score(x.iloc[held_out], y.iloc[held_out])),
        learned_rows=len(learn),
        held_out_rows=len(held_out),
    )


def report(result: HeldOutResult) -> str:
    """The ranking as a Markdown page."""
    lines = [
        "# Random forest importance on held-out training hosts",
        "",
        "| Rank | Feature | Accuracy drop |",
        "|---|---|---|",
        *(f"| {rank} | `{feature}` | {drop:.4f} |" for rank, feature, drop in result.table.itertuples(index=False)),
        "",
        f"The forest learned from {result.learned_rows:,} training rows and was scored on {result.held_out_rows:,} rows "
        f"from held-out training hosts. No host is on both sides. The test split is never used.",
        "",
        f"Accuracy on the rows it learned from: {result.learned_accuracy:.3f}. "
        f"On the held-out hosts: {result.held_out_accuracy:.3f}. Seed: {SEED}. Trees: {TREES}. Shuffles per feature: {SHUFFLES}.",
        "",
        "Made by `uv run python -m ranking.held_out_importance`.",
    ]
    return "\n".join(lines) + "\n"


def main(ml_dir: Path) -> int:
    """Run the check and save the report. Returns 1 and saves nothing if the inputs are wrong."""
    try:
        features, split = load_inputs(ml_dir / "data")
        result = held_out_importance(features, split)
    except TrainingSplitError as error:
        print(f"Held-out importance stopped: {error}")
        return 1
    page = report(result)
    path = ml_dir / "reports" / REPORT_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page)
    print(page)
    print(f"Saved to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parents[1]))

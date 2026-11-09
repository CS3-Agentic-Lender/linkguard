"""Tune the chosen model's settings with a grid search on the training split only.

The chosen model is gradient boosting (scikit-learn's HistGradientBoostingClassifier). Sprint 3
planning changed the choosing rule to ROC-AUC, because the risk-level cut-offs story sets our
own flag lines, and gradient boosting had the best ROC-AUC in the model comparison (0.836).
The search space and the scoring measure were written down before the search ran, in the
search space note in the Sprint 3 Confluence folder:

- learning_rate: 0.05, 0.1, 0.2. How big a step each new tree takes.
- max_iter: 100, 300. The most trees allowed. Early stopping can stop sooner.
- max_leaf_nodes: 15, 31, 63. How detailed each tree may be.
- min_samples_leaf: 20, 100. A larger value stops a tree learning from a few odd rows.
- Fixed: early stopping on (the default), seed 0, no class weight. These match the model
  comparison, so its settings are the "before" row.

Each combination is scored with the same hostname-grouped, stratified 5-fold cross-validation
as the model comparison (same folds, seed 0). The scaler and the model sit in one Pipeline,
so each fold fits the scaler on its own training rows only. The scoring measure is ROC-AUC,
which does not depend on where the flag line is drawn. The test split is never loaded: the
rows come from the training pipeline, which only reads the rows the saved split puts in training.

Writes ml/reports/tuning_results.json and ml/reports/tuning.md.

Run from ml/:  uv run python -m training.tuning
"""

import argparse
import itertools
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import f1_score, fbeta_score, make_scorer, precision_score, recall_score
from sklearn.model_selection import GridSearchCV

from cleaning.labels import PHISHING
from ranking.final_list import FINAL_FEATURES
from training.classifiers import DECIMALS, FOLDS, SEED, fold_positions, model_pipeline
from training.pipeline import FEATURES_PATH, ML_DIR, SCALER_PATH, SPLIT_PATH, PipelineError, load_training_set

# The settings searched, in the order they are shown.
SEARCH_SPACE: dict[str, tuple] = {
    "learning_rate": (0.05, 0.1, 0.2),
    "max_iter": (100, 300),
    "max_leaf_nodes": (15, 31, 63),
    "min_samples_leaf": (20, 100),
}
SETTINGS = tuple(SEARCH_SPACE)
# scikit-learn's defaults, which the model comparison scored.
BEFORE = {"learning_rate": 0.1, "max_iter": 100, "max_leaf_nodes": 31, "min_samples_leaf": 20}
# Every combination the grid holds.
ALL_COMBINATIONS = [dict(zip(SETTINGS, values)) for values in itertools.product(*SEARCH_SPACE.values())]
SCORING_MEASURE = "roc_auc"
# Combinations this close to the best mean ROC-AUC count as a tie, and the simplest of them wins.
CLOSE = 0.001
BETA = 2
# The table's columns, in the model comparison's order, with F2 added at the end.
MEASURES = ("recall", "precision", "f1", "roc_auc", "accuracy", "f2")
MEASURE_TITLES = {
    "recall": "Phishing recall",
    "precision": "Precision",
    "f1": "F1",
    "roc_auc": "ROC-AUC",
    "accuracy": "Accuracy",
    "f2": "F2",
}
RESULTS_PATH = ML_DIR / "reports" / "tuning_results.json"
REPORT_PATH = ML_DIR / "reports" / "tuning.md"
LABEL = "In-dataset cross-validation results, not real-world accuracy."


def base_model() -> HistGradientBoostingClassifier:
    """The chosen model with the settings the search does not change."""
    return HistGradientBoostingClassifier(random_state=SEED)


def search_space(space: dict[str, tuple] | None = None) -> dict[str, list]:
    return {f"model__{name}": list(values) for name, values in (space or SEARCH_SPACE).items()}


def scorers() -> dict:
    """Every measure in the table, phishing as the positive class. ROC-AUC is the one that chooses."""
    return {
        "recall": make_scorer(recall_score, pos_label=PHISHING, zero_division=0),
        "precision": make_scorer(precision_score, pos_label=PHISHING, zero_division=0),
        "f1": make_scorer(f1_score, pos_label=PHISHING, zero_division=0),
        "roc_auc": "roc_auc",  # scores the probability of label 1, which is phishing
        "accuracy": "accuracy",
        "f2": make_scorer(fbeta_score, beta=BETA, pos_label=PHISHING, zero_division=0),
    }


def run_search(
    features: pd.DataFrame, labels: pd.Series, hosts: pd.Series, n_jobs: int = -1, space: dict[str, tuple] | None = None
) -> GridSearchCV:
    """Score every combination on the comparison's folds. Nothing is refitted on all rows here.

    n_jobs=-1 uses every core. Tests pass 1, so every fit runs in this process and can be watched,
    and a smaller `space` so they stay fast. The real run always uses SEARCH_SPACE.
    """
    search = GridSearchCV(
        model_pipeline(base_model()),
        search_space(space),
        scoring=scorers(),
        refit=False,
        cv=fold_positions(labels, hosts),
        n_jobs=n_jobs,
        error_score="raise",
    )
    return search.fit(features, labels)


def _setting(name: str, value):
    return float(value) if name == "learning_rate" else int(value)


def combinations(search: GridSearchCV) -> list[dict]:
    """One entry per combination: its settings and each measure's mean and spread over the folds.

    Scores are kept at full precision, so choosing is never decided by rounding. They are only
    rounded when saved (see `rounded`).
    """
    results = search.cv_results_
    rows = []
    for index, params in enumerate(results["params"]):
        row = {name: _setting(name, params[f"model__{name}"]) for name in SETTINGS}
        for measure in MEASURES:
            row[measure] = {
                "mean": float(results[f"mean_test_{measure}"][index]),
                "std": float(results[f"std_test_{measure}"][index]),
                "folds": [float(results[f"split{fold}_test_{measure}"][index]) for fold in range(FOLDS)],
            }
        rows.append(row)
    return rows


def rounded(rows: list[dict]) -> list[dict]:
    """A copy of the combinations with every score rounded to DECIMALS places, for the saved file."""
    return [
        {
            key: (
                {
                    "mean": round(v["mean"], DECIMALS),
                    "std": round(v["std"], DECIMALS),
                    "folds": [round(f, DECIMALS) for f in v["folds"]],
                }
                if isinstance(v, dict)
                else v
            )
            for key, v in row.items()
        }
        for row in rows
    ]


def simplicity(row: dict) -> tuple:
    """Smaller sorts first = simpler: fewer leaves, then fewer trees, then larger leaves, then smaller steps."""
    return (row["max_leaf_nodes"], row["max_iter"], -row["min_samples_leaf"], row["learning_rate"])


def choose(rows: list[dict]) -> dict:
    """The simplest combination within CLOSE of the best mean ROC-AUC."""
    best = max(row[SCORING_MEASURE]["mean"] for row in rows)
    close = [row for row in rows if row[SCORING_MEASURE]["mean"] >= best - CLOSE - 1e-12]
    return min(close, key=simplicity)


def settings_of(row: dict) -> dict:
    return {name: row[name] for name in SETTINGS}


def find(rows: list[dict], settings: dict) -> dict:
    return next(row for row in rows if settings_of(row) == settings)


def settings_text(row: dict) -> str:
    return (
        f"learning rate {row['learning_rate']:g}, up to {row['max_iter']} trees, "
        f"{row['max_leaf_nodes']} leaves, min leaf {row['min_samples_leaf']}"
    )


def _cell(row: dict, measure: str) -> str:
    return f"{row[measure]['mean']:.3f} ± {row[measure]['std']:.3f}"


def report(results: dict) -> str:
    rows = results["combinations"]
    before, after = find(rows, results["before"]), find(rows, results["chosen"])
    header = "| Model | " + " | ".join(MEASURE_TITLES[m] for m in MEASURES) + " |"
    line = "|" + "---|" * (len(MEASURES) + 1)
    table = [
        header,
        line,
        f"| Before tuning ({settings_text(before)}) | " + " | ".join(_cell(before, m) for m in MEASURES) + " |",
        f"| After tuning ({settings_text(after)}) | " + " | ".join(_cell(after, m) for m in MEASURES) + " |",
    ]
    every = [
        "| Learning rate | Max trees | Leaves | Min leaf | ROC-AUC | Phishing recall | Precision |",
        "|---|---|---|---|---|---|---|",
        *(
            f"| {row['learning_rate']:g} | {row['max_iter']} | {row['max_leaf_nodes']} | {row['min_samples_leaf']} | "
            f"{_cell(row, 'roc_auc')} | {_cell(row, 'recall')} | {_cell(row, 'precision')} |"
            for row in sorted(rows, key=lambda r: -r[SCORING_MEASURE]["mean"])
        ),
    ]
    change = after["roc_auc"]["mean"] - before["roc_auc"]["mean"]
    return "\n".join(
        [
            "# Tuning the chosen model",
            "",
            f"**{LABEL}**",
            "",
            "## How it was made",
            "",
            f"- {results['training_rows']:,} training rows. They are the training part of the shared host-grouped split. The test rows were not used.",
            f"- The model is gradient boosting (HistGradientBoostingClassifier), on the {len(results['features'])} final features.",
            f"- Stratified {results['folds']}-fold cross-validation, grouped by host, with seed {results['seed']}. These are the same folds as the model comparison.",
            "- Inside each fold the scaler and the model are fitted together on the fold's training rows only.",
            "- Every combination below was tried. The scoring measure is ROC-AUC, chosen before the search ran.",
            f"- Combinations within {CLOSE} of the best mean ROC-AUC count as a tie, and the simplest wins: fewer leaves, then fewer trees, then larger leaves, then a smaller learning rate.",
            "- Phishing (label 1) is the positive class. Each score is the mean over the folds ± the standard deviation. "
            "Recall, precision, F1, F2 and accuracy use the default 0.5 flag line. The risk-level cut-offs set the real ones.",
            "",
            "## Before and after",
            "",
            *table,
            "",
            f"Mean ROC-AUC changed by {change:+.3f}. The before row is scikit-learn's default settings, which the model comparison scored.",
            "",
            "## Every combination, best ROC-AUC first",
            "",
            *every,
            "",
            "Made by `uv run python -m training.tuning`.",
            "",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--features", type=Path, default=FEATURES_PATH, help="training feature set CSV")
    parser.add_argument("--split", type=Path, default=SPLIT_PATH, help="saved train/test split CSV")
    parser.add_argument("--scaler", type=Path, default=SCALER_PATH, help="saved scaler (.joblib)")
    parser.add_argument("--results", type=Path, default=RESULTS_PATH, help="where to save the results JSON")
    parser.add_argument("--report", type=Path, default=REPORT_PATH, help="where to save the Markdown report")
    args = parser.parse_args(argv)

    try:
        training = load_training_set(args.features, args.split, args.scaler)
    except PipelineError as error:
        print(f"Tuning stopped: {error}", file=sys.stderr)
        return 1
    features = training.features.loc[:, list(FINAL_FEATURES)]
    rows = combinations(run_search(features, training.labels, training.hostnames))
    chosen = choose(rows)
    results = {
        "model": "HistGradientBoostingClassifier",
        "features": list(FINAL_FEATURES),
        "folds": FOLDS,
        "seed": SEED,
        "training_rows": len(training.rows),
        "scoring": SCORING_MEASURE,
        "close": CLOSE,
        "fixed": {"random_state": SEED, "early_stopping": "auto", "class_weight": None},
        "before": dict(BEFORE),
        "chosen": settings_of(chosen),
        "combinations": rounded(rows),
    }
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(json.dumps(results, indent=2) + "\n")
    args.report.write_text(report(results))
    before = find(rows, BEFORE)
    print(f"Before ({settings_text(before)}): mean ROC-AUC {before['roc_auc']['mean']:.3f}")
    print(f"Chosen ({settings_text(chosen)}): mean ROC-AUC {chosen['roc_auc']['mean']:.3f}")
    print(f"Saved {args.results} and {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

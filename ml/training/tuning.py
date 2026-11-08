"""Tune the chosen model's settings with a grid search on the training split only.

The chosen model is logistic regression with balanced class weights (see
ml/reports/model_comparison.md). The search space and the scoring measure were written down
before the search ran, in the search space note in the Sprint 3 Confluence folder:

- C: 0.001, 0.01, 0.1, 1, 10, 100, 1000. How closely the model may fit the training rows.
- l1_ratio: 0 (l2) or 1 (l1). scikit-learn 1.8 renamed the old `penalty` setting to this.
  l1 can switch a weak feature off. l2 shrinks every weight a little.
- solver liblinear (fixed): it supports both penalties, so they are compared fairly.
- class_weight balanced (fixed): if the search could change how much gets flagged, F2 would
  reward flagging every link. Where to draw that line is the risk-level cut-off story's job.

Each combination is scored with the same hostname-grouped, stratified 5-fold cross-validation
as the model comparison (same folds, seed 0). The scaler and the model sit in one Pipeline,
so each fold fits the scaler on its own training rows only. The scoring measure is F2, which
counts phishing recall more than precision. The test split is never loaded: the rows come
from the training pipeline, which only reads the rows the saved split puts in training.

The "before" row is the current model (C = 1, l2), scored in the same search. Writes
ml/reports/tuning_results.json and ml/reports/tuning.md.

Run from ml/:  uv run python -m training.tuning
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, fbeta_score, make_scorer, precision_score, recall_score
from sklearn.model_selection import GridSearchCV

from cleaning.labels import PHISHING
from ranking.final_list import FINAL_FEATURES
from training.classifiers import DECIMALS, FOLDS, SEED, fold_positions, model_pipeline
from training.pipeline import FEATURES_PATH, ML_DIR, SCALER_PATH, SPLIT_PATH, PipelineError, load_training_set

C_VALUES = (0.001, 0.01, 0.1, 1.0, 10.0, 100.0, 1000.0)
L1_RATIOS = (0.0, 1.0)  # 0 = l2, 1 = l1
PENALTY_NAMES = {0.0: "l2", 1.0: "l1"}
BEFORE = {"C": 1.0, "l1_ratio": 0.0}  # the settings the model comparison scored
SCORING_MEASURE = "f2"
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


def base_model() -> LogisticRegression:
    """The chosen model with the settings the search does not change."""
    return LogisticRegression(solver="liblinear", class_weight="balanced", max_iter=1000, random_state=SEED)


def search_space() -> dict[str, list[float]]:
    return {"model__C": list(C_VALUES), "model__l1_ratio": list(L1_RATIOS)}


def scorers() -> dict:
    """Every measure in the table, phishing as the positive class. F2 is the one that chooses."""
    return {
        "recall": make_scorer(recall_score, pos_label=PHISHING, zero_division=0),
        "precision": make_scorer(precision_score, pos_label=PHISHING, zero_division=0),
        "f1": make_scorer(f1_score, pos_label=PHISHING, zero_division=0),
        "roc_auc": "roc_auc",  # scores the probability of label 1, which is phishing
        "accuracy": "accuracy",
        "f2": make_scorer(fbeta_score, beta=BETA, pos_label=PHISHING, zero_division=0),
    }


def run_search(features: pd.DataFrame, labels: pd.Series, hosts: pd.Series, n_jobs: int = -1) -> GridSearchCV:
    """Score every combination on the comparison's folds. Nothing is refitted on all rows here.

    n_jobs=-1 uses every core. Tests pass 1, so every fit runs in this process and can be watched.
    """
    search = GridSearchCV(
        model_pipeline(base_model()),
        search_space(),
        scoring=scorers(),
        refit=False,
        cv=fold_positions(labels, hosts),
        n_jobs=n_jobs,
        error_score="raise",
    )
    return search.fit(features, labels)


def combinations(search: GridSearchCV) -> list[dict]:
    """One entry per combination: its settings and each measure's mean and spread over the folds."""
    results = search.cv_results_
    rows = []
    for index, params in enumerate(results["params"]):
        row = {"C": float(params["model__C"]), "l1_ratio": float(params["model__l1_ratio"])}
        for measure in MEASURES:
            row[measure] = {
                "mean": round(float(results[f"mean_test_{measure}"][index]), DECIMALS),
                "std": round(float(results[f"std_test_{measure}"][index]), DECIMALS),
                "folds": [
                    round(float(results[f"split{fold}_test_{measure}"][index]), DECIMALS) for fold in range(FOLDS)
                ],
            }
        rows.append(row)
    return rows


def choose(rows: list[dict]) -> dict:
    """The highest mean F2. On an exact tie the smaller C wins, because it is the simpler model."""
    return max(rows, key=lambda row: (row[SCORING_MEASURE]["mean"], -row["C"], -row["l1_ratio"]))


def find(rows: list[dict], settings: dict) -> dict:
    return next(row for row in rows if row["C"] == settings["C"] and row["l1_ratio"] == settings["l1_ratio"])


def settings_text(row: dict) -> str:
    return f"C = {row['C']:g}, {PENALTY_NAMES[row['l1_ratio']]}"


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
        "| C | Penalty | F2 | Phishing recall | Precision |",
        "|---|---|---|---|---|",
        *(
            f"| {row['C']:g} | {PENALTY_NAMES[row['l1_ratio']]} | {_cell(row, 'f2')} | {_cell(row, 'recall')} | {_cell(row, 'precision')} |"
            for row in sorted(rows, key=lambda r: (r["l1_ratio"], r["C"]))
        ),
    ]
    change = after["f2"]["mean"] - before["f2"]["mean"]
    return "\n".join(
        [
            "# Tuning the chosen model",
            "",
            f"**{LABEL}**",
            "",
            "## How it was made",
            "",
            f"- {results['training_rows']:,} training rows. They are the training part of the shared host-grouped split. The test rows were not used.",
            f"- The model is logistic regression with balanced class weights and the liblinear solver, on the {len(results['features'])} final features.",
            f"- Stratified {results['folds']}-fold cross-validation, grouped by host, with seed {results['seed']}. These are the same folds as the model comparison.",
            "- Inside each fold the scaler and the model are fitted together on the fold's training rows only.",
            "- Every combination below was tried. The scoring measure is F2, chosen before the search ran.",
            "- Phishing (label 1) is the positive class. Each score is the mean over the folds ± the standard deviation.",
            "",
            "## Before and after",
            "",
            *table,
            "",
            f"Mean F2 changed by {change:+.3f}. On an exact tie the smaller C wins, because it is the simpler model.",
            "",
            "## Every combination",
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
        "features": list(FINAL_FEATURES),
        "folds": FOLDS,
        "seed": SEED,
        "training_rows": len(training.rows),
        "scoring": SCORING_MEASURE,
        "fixed": {"solver": "liblinear", "class_weight": "balanced", "max_iter": 1000},
        "before": dict(BEFORE),
        "chosen": {"C": chosen["C"], "l1_ratio": chosen["l1_ratio"]},
        "combinations": rows,
    }
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(json.dumps(results, indent=2) + "\n")
    args.report.write_text(report(results))
    before = find(rows, BEFORE)
    print(f"Before ({settings_text(before)}): mean F2 {before['f2']['mean']:.3f}")
    print(f"Chosen ({settings_text(chosen)}): mean F2 {chosen['f2']['mean']:.3f}")
    print(f"Saved {args.results} and {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

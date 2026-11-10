"""Draw the precision/recall curve for the phishing class, from cross-validation on the training rows.

The risk-level cut-offs are chosen from this curve, so it must come from scores the model made
on links it was not trained on. It must not come from the test split either, or the test
results would no longer be fair.

So every training row gets one out-of-fold phishing score. The training rows are cut into the
same 5 host-grouped, stratified folds as the model comparison and the tuning (seed 0). For each
fold, a fresh scaler and the tuned gradient boosting model are fitted on the other 4 folds and
score the held-out fold. Each row is scored once, by a model that never saw its host. The test
split is never loaded.

The curve shows, for every possible cut-off on the phishing score: phishing recall (the share
of phishing links at or above it) and precision (the share of links at or above it that really
are phishing). The model's settings come from ml/reports/tuning_results.json.

Writes ml/reports/precision_recall.png (the chart) and ml/reports/precision_recall.json (the
curve at cut-offs 0.00, 0.01, ..., 1.00, for choosing the cut-offs). Pass --cutoffs LOWER UPPER
to mark two cut-offs on the chart.

Run from ml/:  uv run python -m training.precision_recall
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from sklearn.metrics import average_precision_score, precision_recall_curve

from cleaning.labels import PHISHING
from ranking.final_list import FINAL_FEATURES
from training.classifiers import DECIMALS, FOLDS, SEED, fold_positions, model_pipeline
from training.final_model import FinalModelError, chosen_settings
from training.pipeline import (
    FEATURES_PATH,
    ML_DIR,
    SCALER_PATH,
    SPLIT_PATH,
    PipelineError,
    load_training_set,
)
from training.tuning import RESULTS_PATH, base_model, settings_text

CHART_PATH = ML_DIR / "reports" / "precision_recall.png"
CURVE_PATH = ML_DIR / "reports" / "precision_recall.json"
CHART_SIZE_INCHES = (7, 5.5)
CHART_DPI = 100
CUTOFF_STEPS = np.round(np.linspace(0, 1, 101), 2)  # the cut-offs saved in the JSON file
TITLE = "Precision/recall for phishing, cross-validation on the training set"


def out_of_fold_scores(features: pd.DataFrame, labels: pd.Series, hosts: pd.Series, settings: dict) -> np.ndarray:
    """One phishing score per row, each from the fold model that did not learn from that row's host."""
    scores = np.full(len(labels), np.nan)
    for learn, held_out in fold_positions(labels, hosts):
        pipe = model_pipeline(base_model().set_params(**settings))
        pipe.fit(features.iloc[learn], labels.iloc[learn])
        phishing = list(pipe.classes_).index(PHISHING)
        scores[held_out] = pipe.predict_proba(features.iloc[held_out])[:, phishing]
    return scores


def at_cutoff(labels: np.ndarray, scores: np.ndarray, cutoff: float) -> dict:
    """Phishing recall and precision when every score at or above the cut-off counts as phishing."""
    flagged = scores >= cutoff
    phishing = labels == PHISHING
    caught = int((flagged & phishing).sum())
    return {
        "cutoff": float(cutoff),
        "recall": round(caught / int(phishing.sum()), DECIMALS),
        # With nothing flagged there is no precision to measure; 1.0 is the convention sklearn uses.
        "precision": round(caught / int(flagged.sum()), DECIMALS) if flagged.any() else 1.0,
        "flagged_share": round(float(flagged.mean()), DECIMALS),
    }


def curve_table(labels: np.ndarray, scores: np.ndarray) -> list[dict]:
    return [at_cutoff(labels, scores, cutoff) for cutoff in CUTOFF_STEPS]


def chart(labels: np.ndarray, scores: np.ndarray, cutoffs: Sequence[float] = ()) -> Figure:
    """The precision/recall curve, with each given cut-off marked and labelled."""
    precision, recall, _ = precision_recall_curve(labels, scores, pos_label=PHISHING)
    phishing_share = float(np.mean(labels == PHISHING))
    figure = Figure(figsize=CHART_SIZE_INCHES, layout="constrained")
    axis = figure.subplots()
    axis.plot(recall, precision, color="#1f4e79", linewidth=2, label="Tuned gradient boosting")
    axis.axhline(
        phishing_share,
        color="grey",
        linestyle="--",
        linewidth=1,
        label=f"Guessing (phishing share {phishing_share:.2f})",
    )
    for cutoff in cutoffs:
        point = at_cutoff(labels, scores, cutoff)
        axis.plot(
            point["recall"],
            point["precision"],
            marker="o",
            markersize=9,
            color="#c0392b",
            linestyle="none",
        )
        axis.annotate(
            f"cut-off {cutoff:.2f}\nrecall {point['recall']:.2f}, precision {point['precision']:.2f}",
            (point["recall"], point["precision"]),
            textcoords="offset points",
            # Below and left of the point is always empty, because the curve falls from left to right.
            xytext=(-10, -10),
            horizontalalignment="right",
            verticalalignment="top",
            fontsize=9,
        )
    axis.set_title(TITLE)
    axis.set_xlabel("Phishing recall (share of phishing links caught)")
    axis.set_ylabel("Precision (share of flagged links that are phishing)")
    axis.set_xlim(0, 1.02)
    axis.set_ylim(0, 1.02)
    axis.grid(alpha=0.3)
    axis.legend(loc="lower left")
    return figure


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--features", type=Path, default=FEATURES_PATH, help="training feature set CSV")
    parser.add_argument("--split", type=Path, default=SPLIT_PATH, help="saved train/test split CSV")
    parser.add_argument("--scaler", type=Path, default=SCALER_PATH, help="saved scaler (.joblib)")
    parser.add_argument("--results", type=Path, default=RESULTS_PATH, help="tuning results JSON")
    parser.add_argument("--chart", type=Path, default=CHART_PATH, help="where to save the chart (.png)")
    parser.add_argument("--curve", type=Path, default=CURVE_PATH, help="where to save the curve (.json)")
    parser.add_argument(
        "--cutoffs",
        type=float,
        nargs=2,
        metavar=("LOWER", "UPPER"),
        help="two cut-offs to mark on the chart",
    )
    args = parser.parse_args(argv)
    cutoffs = sorted(args.cutoffs) if args.cutoffs else []
    if any(not 0 <= cutoff <= 1 for cutoff in cutoffs):
        parser.error("cut-offs must be between 0 and 1")

    try:
        settings = chosen_settings(args.results)
        training = load_training_set(args.features, args.split, args.scaler)
    except (PipelineError, FinalModelError) as error:
        print(f"Precision/recall stopped: {error}", file=sys.stderr)
        return 1
    features = training.features.loc[:, list(FINAL_FEATURES)]
    scores = out_of_fold_scores(features, training.labels, training.hostnames, settings)
    labels = training.labels.to_numpy()

    result = {
        "source": f"out-of-fold scores, {FOLDS} host-grouped folds of the training rows, seed {SEED}",
        "model": f"gradient boosting, {settings_text(settings)}",
        "training_rows": len(labels),
        "phishing_rows": int((labels == PHISHING).sum()),
        "average_precision": round(float(average_precision_score(labels, scores, pos_label=PHISHING)), DECIMALS),
        "marked_cutoffs": cutoffs,
        "curve": curve_table(labels, scores),
    }
    args.curve.parent.mkdir(parents=True, exist_ok=True)
    args.curve.write_text(json.dumps(result, indent=2) + "\n")
    args.chart.parent.mkdir(parents=True, exist_ok=True)
    chart(labels, scores, cutoffs).savefig(args.chart, dpi=CHART_DPI)
    print(f"Scored {len(labels):,} training rows out of fold with {settings_text(settings)}")
    print(f"Average precision {result['average_precision']:.3f}")
    print(f"Saved {args.chart} and {args.curve}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

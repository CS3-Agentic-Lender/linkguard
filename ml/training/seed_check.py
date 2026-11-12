"""Check the tuning result is stable: score the before and after settings with several seeds.

The tuning search uses one seed (0) for the folds and the model. A different seed gives a
different fold split and different randomness inside gradient boosting (its early-stopping
hold-out). So a gain seen with seed 0 could be luck. This script scores the before and the
after settings again with seeds 0 to 4, each on its own host-grouped, stratified 5-fold split
of the training rows, and reports whether after beats before on every seed.

It only measures stability. It never picks a seed: choosing the seed that scores best would
be fitting to noise.

Reads ml/reports/tuning_results.json. Writes ml/reports/seed_check.json and
ml/reports/seed_check.md. The test split is never loaded.

Run from ml/:  uv run python -m training.seed_check
"""

import argparse
import json
import statistics
import sys
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold

from cleaning.labels import PHISHING
from ranking.final_list import FINAL_FEATURES
from training.classifiers import DECIMALS, FOLDS, model_pipeline
from training.pipeline import FEATURES_PATH, ML_DIR, SCALER_PATH, SPLIT_PATH, PipelineError, load_training_set
from training.tuning import RESULTS_PATH, SETTINGS, base_model, settings_text

SEEDS = (0, 1, 2, 3, 4)
OUTPUT_JSON = ML_DIR / "reports" / "seed_check.json"
OUTPUT_REPORT = ML_DIR / "reports" / "seed_check.md"


class SeedCheckError(Exception):
    """The tuning results are missing or cannot be read."""


def tuned_settings(results_path: Path) -> tuple[dict, dict]:
    """The before and the chosen settings from the tuning results."""
    if not results_path.is_file():
        raise SeedCheckError(f"The tuning results were not found at {results_path}. Run the tuning first.")
    try:
        results = json.loads(results_path.read_text())
        before = {name: results["before"][name] for name in SETTINGS}
        chosen = {name: results["chosen"][name] for name in SETTINGS}
    except (ValueError, KeyError, TypeError) as error:
        raise SeedCheckError(f"The tuning results at {results_path} could not be read ({error!r}).")
    return before, chosen


def seed_folds(labels: pd.Series, hosts: pd.Series, seed: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """Host-grouped, stratified folds of the training rows for one seed."""
    folds = StratifiedGroupKFold(n_splits=FOLDS, shuffle=True, random_state=seed)
    return list(folds.split(np.zeros(len(labels)), labels, groups=hosts))


def mean_roc_auc(features: pd.DataFrame, labels: pd.Series, folds, settings: dict, seed: int) -> float:
    """Mean held-out ROC-AUC over the folds, with the model's own randomness set by seed."""
    scores = []
    for learn, held_out in folds:
        pipe = model_pipeline(base_model().set_params(random_state=seed, **settings))
        pipe.fit(features.iloc[learn], labels.iloc[learn])
        phishing = list(pipe.classes_).index(PHISHING)
        scores.append(roc_auc_score(labels.iloc[held_out], pipe.predict_proba(features.iloc[held_out])[:, phishing]))
    return float(np.mean(scores))


def check(
    features: pd.DataFrame, labels: pd.Series, hosts: pd.Series, before: dict, after: dict, seeds=SEEDS
) -> list[dict]:
    """One entry per seed: the before and after mean ROC-AUC and their difference."""
    rows = []
    for seed in seeds:
        folds = seed_folds(labels, hosts, seed)
        before_score = mean_roc_auc(features, labels, folds, before, seed)
        after_score = mean_roc_auc(features, labels, folds, after, seed)
        rows.append(
            {
                "seed": seed,
                "before": round(before_score, DECIMALS),
                "after": round(after_score, DECIMALS),
                "difference": round(after_score - before_score, DECIMALS),
            }
        )
    return rows


def summary(rows: list[dict]) -> dict:
    differences = [row["difference"] for row in rows]
    return {
        "after_wins": sum(difference > 0 for difference in differences),
        "seeds": len(rows),
        "mean_difference": round(statistics.mean(differences), DECIMALS),
        "std_difference": round(statistics.stdev(differences), DECIMALS) if len(rows) > 1 else 0.0,
        "smallest_difference": min(differences),
        "largest_difference": max(differences),
    }


def report(result: dict) -> str:
    totals = result["summary"]
    same = result["before"] == result["after"]
    if same:
        verdict = "The tuning kept the default settings, so before and after are the same model on every seed."
    else:
        verdict = (
            f"After beats before on {totals['after_wins']} of {totals['seeds']} seeds. The mean gain is "
            f"{totals['mean_difference']:+.4f} ± {totals['std_difference']:.4f} "
            f"(smallest {totals['smallest_difference']:+.4f}, largest {totals['largest_difference']:+.4f})."
        )
        if abs(totals["mean_difference"]) <= totals["std_difference"]:
            verdict += " That is within the seed-to-seed noise: no consistent improvement across these five seeds."
        else:
            verdict += " That is larger than the seed-to-seed noise across these five seeds."
    return "\n".join(
        [
            "# Seed check for the tuned model",
            "",
            "**In-dataset cross-validation results, not real-world accuracy.**",
            "",
            f"- Before: {settings_text(result['before'])}.",
            f"- After: {settings_text(result['after'])}.",
            f"- Each seed makes its own host-grouped, stratified {FOLDS}-fold split of the "
            f"{result['training_rows']:,} training rows and sets the model's own randomness. The test rows were not used.",
            "- The check only measures stability. It never picks a seed.",
            "",
            "| Seed | Before ROC-AUC | After ROC-AUC | Difference |",
            "|---|---|---|---|",
            *(
                f"| {row['seed']} | {row['before']:.4f} | {row['after']:.4f} | {row['difference']:+.4f} |"
                for row in result["seeds"]
            ),
            "",
            verdict,
            "",
            "Made by `uv run python -m training.seed_check`.",
            "",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--features", type=Path, default=FEATURES_PATH, help="training feature set CSV")
    parser.add_argument("--split", type=Path, default=SPLIT_PATH, help="saved train/test split CSV")
    parser.add_argument("--scaler", type=Path, default=SCALER_PATH, help="saved scaler (.joblib)")
    parser.add_argument("--results", type=Path, default=RESULTS_PATH, help="tuning results JSON")
    parser.add_argument("--output", type=Path, default=OUTPUT_JSON, help="where to save the seed check JSON")
    parser.add_argument("--report", type=Path, default=OUTPUT_REPORT, help="where to save the Markdown report")
    args = parser.parse_args(argv)

    try:
        before, after = tuned_settings(args.results)
        training = load_training_set(args.features, args.split, args.scaler)
    except (PipelineError, SeedCheckError) as error:
        print(f"Seed check stopped: {error}", file=sys.stderr)
        return 1
    features = training.features.loc[:, list(FINAL_FEATURES)]
    rows = check(features, training.labels, training.hostnames, before, after)
    result = {
        "seeds": rows,
        "summary": summary(rows),
        "before": before,
        "after": after,
        "training_rows": len(training.rows),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    args.report.write_text(report(result))
    totals = result["summary"]
    print(f"After beats before on {totals['after_wins']} of {totals['seeds']} seeds")
    print(f"Mean ROC-AUC gain {totals['mean_difference']:+.4f} ± {totals['std_difference']:.4f}")
    print(f"Saved {args.output} and {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

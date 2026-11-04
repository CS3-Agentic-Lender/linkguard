"""Train the classifiers with hostname-grouped 5-fold cross-validation, on the training split only.

Every model sees the same training rows from the training pipeline, with only the 8 features
in the final feature list. The training rows are cut into 5 folds, grouped by host so no
website is in two folds, and stratified so each fold keeps the phishing share. Each fold's
model learns from 4 folds and is scored on the fifth. The test split is never loaded.

Inside each fold the scaler and the model sit in one scikit-learn Pipeline. So the scaler is
fitted on that fold's training rows only, and the held-out fold is only transformed.

For every model and fold it saves phishing recall, precision, F1, ROC-AUC and accuracy, on
the held-out fold and on the fold's own training rows, plus the held-out fold's confusion
counts. Phishing (label 1) is the positive class.

Writes ml/reports/cv_results.json. Run from ml/:  uv run python -m training.classifiers
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from cleaning.labels import LEGITIMATE, PHISHING
from ranking.final_list import FINAL_FEATURES
from training.pipeline import FEATURES_PATH, ML_DIR, SCALER_PATH, SPLIT_PATH, PipelineError, class_counts, load_training_set

SEED = 0  # fixed so the folds and every model give the same result on a second run
FOLDS = 5
MEASURES = ("recall", "precision", "f1", "roc_auc", "accuracy")
# The forest adds its trees' votes on several cores, so the last digit of a score can change
# between runs. Rounding keeps the saved file identical on every run.
DECIMALS = 6
OUTPUT_PATH = ML_DIR / "reports" / "cv_results.json"
MODELS = {
    "Baseline (most common class)": DummyClassifier(strategy="most_frequent"),
    "Logistic regression": LogisticRegression(max_iter=1000, random_state=SEED),
    "Logistic regression (balanced)": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=SEED),
    "Random forest": RandomForestClassifier(n_estimators=100, random_state=SEED, n_jobs=-1),
    # The fast version of gradient boosting: it bins each feature first, so it trains in seconds on 150,000 rows.
    "Gradient boosting": HistGradientBoostingClassifier(random_state=SEED),
}


def model_pipeline(model) -> Pipeline:
    """A fresh scaler and a fresh copy of the model, fitted together on one fold's training rows."""
    return Pipeline([("scale", StandardScaler()), ("model", clone(model))])


def fold_positions(labels: pd.Series, hosts: pd.Series) -> list[tuple[np.ndarray, np.ndarray]]:
    """(learning positions, held-out positions) for each fold, with no host on both sides."""
    folds = StratifiedGroupKFold(n_splits=FOLDS, shuffle=True, random_state=SEED)
    return list(folds.split(np.zeros(len(labels)), labels, groups=hosts))


def scores(truth: pd.Series, predicted: np.ndarray, phishing_score: np.ndarray) -> dict[str, float]:
    """The five measures, phishing as the positive class, rounded to DECIMALS places."""
    measures = {
        "recall": recall_score(truth, predicted, pos_label=PHISHING, zero_division=0),
        "precision": precision_score(truth, predicted, pos_label=PHISHING, zero_division=0),
        "f1": f1_score(truth, predicted, pos_label=PHISHING, zero_division=0),
        "roc_auc": roc_auc_score(truth, phishing_score),
        "accuracy": accuracy_score(truth, predicted),
    }
    return {name: round(float(value), DECIMALS) for name, value in measures.items()}


def _phishing_score(pipe: Pipeline, x: pd.DataFrame) -> np.ndarray:
    classes = list(pipe.classes_)
    return pipe.predict_proba(x)[:, classes.index(PHISHING)]


def cross_validate_models(features: pd.DataFrame, labels: pd.Series, hosts: pd.Series) -> dict[str, list[dict]]:
    """Per-fold scores and confusion counts for every model, keyed by model name."""
    positions = fold_positions(labels, hosts)
    results = {}
    for name, model in MODELS.items():
        folds = []
        for number, (learn, held_out) in enumerate(positions, start=1):
            pipe = model_pipeline(model).fit(features.iloc[learn], labels.iloc[learn])
            x_out, y_out = features.iloc[held_out], labels.iloc[held_out]
            predicted = pipe.predict(x_out)
            tn, fp, fn, tp = confusion_matrix(y_out, predicted, labels=[LEGITIMATE, PHISHING]).ravel()
            folds.append(
                {
                    "fold": number,
                    "cv": scores(y_out, predicted, _phishing_score(pipe, x_out)),
                    "train": scores(
                        labels.iloc[learn],
                        pipe.predict(features.iloc[learn]),
                        _phishing_score(pipe, features.iloc[learn]),
                    ),
                    "confusion": {"tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn)},
                }
            )
        results[name] = folds
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--features", type=Path, default=FEATURES_PATH, help="training feature set CSV")
    parser.add_argument("--split", type=Path, default=SPLIT_PATH, help="saved train/test split CSV")
    parser.add_argument("--scaler", type=Path, default=SCALER_PATH, help="saved scaler (.joblib)")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="where to save the results JSON")
    args = parser.parse_args(argv)

    try:
        training = load_training_set(args.features, args.split, args.scaler)
    except PipelineError as error:
        print(f"Training the classifiers stopped: {error}", file=sys.stderr)
        return 1
    features = training.features.loc[:, list(FINAL_FEATURES)]
    counts = class_counts(training.labels)
    results = {
        "features": list(FINAL_FEATURES),
        "folds": FOLDS,
        "seed": SEED,
        "training_rows": len(training.rows),
        "class_balance": {"phishing": counts[PHISHING], "legitimate": counts[LEGITIMATE]},
        "models": {
            name: {"folds": folds}
            for name, folds in cross_validate_models(features, training.labels, training.hostnames).items()
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n")
    for name, model in results["models"].items():
        recall = np.mean([fold["cv"]["recall"] for fold in model["folds"]])
        print(f"{name}: mean phishing recall {recall:.3f}")
    print(f"Saved {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

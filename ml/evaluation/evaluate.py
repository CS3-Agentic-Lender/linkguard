"""Score the one saved chosen model on the held-back test rows, once, and save the results.

This is the only code in ml/ that scores a model on the test rows. It reads four files that earlier
stories save and changes none of them:

- the feature set (ml/data/training_features.csv): row number, the ten hostname features in
  the extractor's order, the label (1 = phishing, 0 = legitimate) and the cleaned host;
- the shared split (ml/data/split.csv), which names each row "train" or "test";
- the scaler fitted on the training rows only (ml/models/scaler.joblib), used to transform;
- the saved chosen model (ml/models/model.joblib). It takes all ten scaled features and
  keeps the 8 final ones itself, as the backend uses it.

Nothing is fitted or tuned here. The test rows are scored once by that one model, and the
training rows are scored by the same model only so the two can be compared for over- and
underfitting. Before scoring, the run stops if any cleaned host has rows in both sets.

Phishing (label 1) is the positive class. Accuracy is reported but is not the headline:
a simple pattern rule scores over 99% on PhiUSIIL, so phishing recall is the main measure.

Writes ml/reports/evaluation_results.json and prints the scores.

The model and scaler files are pickles, and loading a pickle runs code. Only load the files
our own steps saved to ml/models/, never ones from anywhere else.

Run from ml/:  uv run python -m evaluation.evaluate
"""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve

from cleaning.labels import LABEL_COLUMN, LEGITIMATE, PHISHING
from features.hostname import FEATURE_NAMES
from splitting.split import SplitMismatchError, load_split
from training.model_comparison import CLASSES, OVERFIT_GAP, UNDERFIT_F1, scores_from_counts
from training.pipeline import (
    FEATURES_PATH,
    HOSTNAME_COLUMN,
    ML_DIR,
    ROW_COLUMN,
    SCALER_PATH,
    SPLIT_PATH,
    TEST,
    PipelineError,
    check_values,
    load_scaler,
    load_training_features,
    load_training_rows,
    load_training_set,
)

MODEL_PATH = ML_DIR / "models" / "model.joblib"
RESULTS_PATH = ML_DIR / "reports" / "evaluation_results.json"
DECIMALS = 6
LABEL = "In-dataset test results on the held-back PhiUSIIL test split, not real-world accuracy."


class EvaluationError(Exception):
    """An input is missing or wrong, or the split lets a host into both sets."""


@dataclass(frozen=True)
class ScoredRows:
    labels: np.ndarray
    predicted: np.ndarray
    phishing_scores: np.ndarray


def load_test_rows(features_path: Path, split_path: Path) -> np.ndarray:
    """Return the row numbers the saved split puts in the test set, in ascending order.

    The split is read with the split's own load_split, which checks it was made from this
    same feature set, host for host and row for row (split_check.json beside the split).
    Only the row and host columns of the feature set are read for that check.
    """
    load_training_rows(split_path)  # checks columns, set names, duplicates and row numbers
    hosts = pd.read_csv(
        features_path, usecols=[ROW_COLUMN, HOSTNAME_COLUMN], keep_default_na=False, dtype={HOSTNAME_COLUMN: str}
    ).set_index(ROW_COLUMN)[HOSTNAME_COLUMN]
    try:
        sets = load_split(split_path, hosts)
    except SplitMismatchError as error:
        raise EvaluationError(str(error)) from error
    rows = np.sort(sets.index[sets == TEST].to_numpy())
    if rows.size == 0:
        raise EvaluationError("The split file has no test rows.")
    return rows


def load_test_set(features_path: Path, split_path: Path, scaler) -> tuple[pd.DataFrame, np.ndarray]:
    """The test rows of the feature set and their features after the saved scaler's transform."""
    try:
        frame = load_training_features(features_path, load_test_rows(features_path, split_path))
        check_values(frame)
    except PipelineError as error:
        # The shared loader words its messages for training rows; these are the test rows.
        raise EvaluationError(f"While reading the test rows: {error}") from error
    scaled = np.asarray(scaler.transform(frame.loc[:, list(FEATURE_NAMES)]), dtype=float)
    return frame, scaled


def shared_hosts(train_hosts: pd.Series, test_hosts: pd.Series) -> set[str]:
    """The cleaned hosts that have rows in both the training and the test set."""
    return set(train_hosts) & set(test_hosts)


def check_no_shared_hosts(train_hosts: pd.Series, test_hosts: pd.Series) -> None:
    """Stop if a cleaned host is in both sets. A guard on the shared split, not a rebuild of it."""
    shared = shared_hosts(train_hosts, test_hosts)
    if shared:
        examples = ", ".join(sorted(shared)[:3])
        raise EvaluationError(
            f"{len(shared):,} cleaned hosts are in both the training and the test set (for example {examples}). "
            "The shared split must be rebuilt before the model can be evaluated."
        )


def load_model(model_path: Path):
    """Load the saved chosen model and check it can score the ten scaled features."""
    if not model_path.is_file():
        raise EvaluationError(
            f"The saved model was not found at {model_path}. It is saved by the step that fits the tuned model."
        )
    model = joblib.load(model_path)
    for needed in ("predict", "predict_proba", "classes_"):
        if not hasattr(model, needed):
            raise EvaluationError(f"The file at {model_path} is not a fitted classifier: it has no {needed}.")
    if sorted(np.asarray(model.classes_).tolist()) != sorted([LEGITIMATE, PHISHING]):
        raise EvaluationError(f"The saved model's classes must be {PHISHING} and {LEGITIMATE}, not {list(model.classes_)}.")
    if getattr(model, "n_features_in_", len(FEATURE_NAMES)) != len(FEATURE_NAMES):
        raise EvaluationError(
            f"The saved model takes {model.n_features_in_} features, but it must take all {len(FEATURE_NAMES)} scaled ones."
        )
    return model


def score(model, scaled: np.ndarray, labels: pd.Series) -> ScoredRows:
    phishing = list(model.classes_).index(PHISHING)
    return ScoredRows(
        labels=labels.to_numpy(),
        predicted=np.asarray(model.predict(scaled)),
        phishing_scores=np.asarray(model.predict_proba(scaled))[:, phishing],
    )


def counts(scored: ScoredRows) -> dict[str, int]:
    """True and false positives and negatives, with phishing as the positive class."""
    actual, predicted = scored.labels == PHISHING, scored.predicted == PHISHING
    return {
        "tp": int(np.sum(actual & predicted)),
        "fp": int(np.sum(~actual & predicted)),
        "fn": int(np.sum(actual & ~predicted)),
        "tn": int(np.sum(~actual & ~predicted)),
    }


def measures(scored: ScoredRows) -> dict:
    """Phishing recall, precision, F1, ROC-AUC, accuracy and the false alarm rate, with the counts."""
    confusion = counts(scored)
    result = scores_from_counts(confusion)
    if len(np.unique(scored.labels)) < 2:
        raise EvaluationError("ROC-AUC needs both phishing and legitimate rows.")
    result["roc_auc"] = float(roc_auc_score(scored.labels, scored.phishing_scores))
    legitimate = confusion["fp"] + confusion["tn"]
    # Read off the confusion matrix: the share of legitimate links wrongly flagged as phishing.
    result["false_alarm_rate"] = confusion["fp"] / legitimate if legitimate else 0.0
    result["missed_phishing_rate"] = 1 - result["recall"]
    return {"scores": {name: round(value, DECIMALS) for name, value in result.items()}, "confusion": confusion}


def confusion_matrix(confusion: dict[str, int]) -> dict:
    """Rows are the actual class and columns the predicted class, phishing first, named in words."""
    return {
        "rows": "actual",
        "columns": "predicted",
        "labels": list(CLASSES),
        "counts": [[confusion["tp"], confusion["fn"]], [confusion["fp"], confusion["tn"]]],
    }


def fit_note(train: dict, test: dict) -> str:
    """One line on whether the training-to-test gap points to overfitting, underfitting or neither.

    Uses the same limits as the model comparison, so the two reports judge fit the same way.
    """
    gaps = {name: train[name] - test[name] for name in ("recall", "f1")}
    if any(gap > OVERFIT_GAP for gap in gaps.values()):
        return (
            f"Overfitting: the training {', '.join(n for n, g in gaps.items() if g > OVERFIT_GAP)} "
            f"is more than {OVERFIT_GAP} above the test score."
        )
    if train["f1"] < UNDERFIT_F1:
        return f"Underfitting: the model's F1 on its own training rows is under {UNDERFIT_F1}."
    return (
        f"Neither: training and test recall and F1 are within {OVERFIT_GAP} of each other, "
        f"and the training F1 is {UNDERFIT_F1} or more."
    )


def class_counts(labels: np.ndarray) -> dict[str, int]:
    return {name: int(np.sum(labels == label)) for name, label in zip(CLASSES, (PHISHING, LEGITIMATE))}


def results(test: ScoredRows, train: ScoredRows, model_path: Path) -> dict:
    test_measures, train_measures = measures(test), measures(train)
    training = {name: train_measures["scores"][name] for name in ("recall", "f1")}
    return {
        "label": LABEL,
        "model": model_path.name,
        "positive_class": "phishing (label 1)",
        "decision": "the model's own predict(): phishing when its phishing score is above 0.5",
        "test_rows": int(test.labels.size),
        "test_class_counts": class_counts(test.labels),
        "test": test_measures["scores"],
        "confusion_matrix": confusion_matrix(test_measures["confusion"]),
        "training": training,
        "training_rows": int(train.labels.size),
        "fit_note": fit_note(training, test_measures["scores"]),
        # Kept so the ROC chart can be drawn from this file without loading the test rows again.
        "roc_curve": roc_points(test),
    }


def roc_points(scored: ScoredRows) -> dict[str, list[float]]:
    """The test ROC curve's corner points: false alarm rate and recall at each score threshold."""
    false_alarm, recall, _ = roc_curve(scored.labels, scored.phishing_scores, pos_label=PHISHING)
    return {
        "false_alarm_rate": [round(float(value), DECIMALS) for value in false_alarm],
        "recall": [round(float(value), DECIMALS) for value in recall],
    }


def evaluate(features_path: Path, split_path: Path, scaler_path: Path, model_path: Path) -> dict:
    scaler = load_scaler(scaler_path)
    training = load_training_set(features_path, split_path, scaler_path)
    test_frame, test_scaled = load_test_set(features_path, split_path, scaler)
    check_no_shared_hosts(training.hostnames, test_frame[HOSTNAME_COLUMN])
    model = load_model(model_path)
    return results(
        test=score(model, test_scaled, test_frame[LABEL_COLUMN]),
        train=score(model, training.scaled, training.labels),
        model_path=model_path,
    )


def summary(found: dict) -> str:
    test, training = found["test"], found["training"]
    lines = [
        found["label"],
        f"Test rows: {found['test_rows']:,} ({found['test_class_counts']['phishing']:,} phishing, "
        f"{found['test_class_counts']['legitimate']:,} legitimate)",
        f"Phishing recall (main measure): {test['recall']:.4f}",
        f"Precision:                      {test['precision']:.4f}",
        f"F1:                             {test['f1']:.4f}",
        f"ROC-AUC:                        {test['roc_auc']:.4f}",
        f"Accuracy:                       {test['accuracy']:.4f}",
        f"False alarm rate (legitimate):  {test['false_alarm_rate']:.4f}",
        f"Training recall / F1:           {training['recall']:.4f} / {training['f1']:.4f}",
        found["fit_note"],
    ]
    return "\n".join(lines)


def save_results(found: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(found, indent=2) + "\n")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--features", type=Path, default=FEATURES_PATH, help="feature set CSV")
    parser.add_argument("--split", type=Path, default=SPLIT_PATH, help="saved train/test split CSV")
    parser.add_argument("--scaler", type=Path, default=SCALER_PATH, help="saved scaler (.joblib)")
    parser.add_argument("--model", type=Path, default=MODEL_PATH, help="saved chosen model (.joblib)")
    parser.add_argument("--results", type=Path, default=RESULTS_PATH, help="where to save the results (.json)")
    args = parser.parse_args(argv)

    try:
        found = evaluate(args.features, args.split, args.scaler, args.model)
    except (PipelineError, EvaluationError) as error:
        print(f"Evaluation stopped: {error}", file=sys.stderr)
        return 1
    print(summary(found))
    print(f"Saved {save_results(found, args.results).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

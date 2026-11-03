"""Compare the cross-validated classifiers in one table and choose the model.

Reads ml/reports/cv_results.json, which the classifier training step saves. It holds each
model's scores on every one of the 5 host-grouped folds of the training rows, its scores
on the rows it trained on, and the counts of its held-out predictions. Writes:

- ml/reports/model_comparison.md: the mean and standard deviation over the folds of phishing
  recall, precision, F1, ROC-AUC and accuracy for every model and the baseline, with the
  training recall and F1 next to them, then the chosen model and why, a note on over- and
  underfitting, and the class balance note.
- ml/reports/confusion_matrices/<model>.png: one confusion matrix per model. It adds up the
  5 held-out folds, so every training row is predicted once, by a model that never saw it.

Phishing (label 1) is the positive class. These are in-dataset cross-validation results,
not real-world accuracy. Nothing here trains a model or reads the test rows.

Run from ml/:  uv run python -m training.model_comparison
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure
from sklearn.metrics import ConfusionMatrixDisplay

from ranking.final_list import FINAL_FEATURES

RESULTS_NAME = "cv_results.json"
REPORT_NAME = "model_comparison.md"
MATRIX_DIR_NAME = "confusion_matrices"
BASELINE = "Baseline (most common class)"
PLAIN_LR = "Logistic regression"
BALANCED_LR = "Logistic regression (balanced)"
# Simplest first. When models are close on recall and on F1, the first one here is chosen.
MODEL_NAMES = (BASELINE, PLAIN_LR, BALANCED_LR, "Random forest", "Gradient boosting")
METRICS = ("recall", "precision", "f1", "roc_auc", "accuracy")
COUNTS = ("tp", "fp", "fn", "tn")
CLASSES = ("phishing", "legitimate")
LABEL = "In-dataset cross-validation results, not real-world accuracy."
# Two mean scores this close count as a tie under the choosing rule.
CLOSE = 0.01
# Tiny slack so a gap of exactly CLOSE still counts, whatever the float rounding.
ROUNDING_TOLERANCE = 1e-9
# A model scoring this much higher on its training rows than in cross-validation looks overfit.
OVERFIT_GAP = 0.05
# A model whose F1 on its own training rows is under this cannot even fit them, so it looks underfit.
UNDERFIT_F1 = 0.70
CHART_DPI = 100
CHART_SIZE_INCHES = (5.6, 4.8)


class ModelComparisonError(Exception):
    """The results file is missing something, or its numbers do not add up."""


def _check_scores(name: str, fold: int, part: str, scores: dict) -> None:
    for metric in METRICS:
        if metric not in scores:
            raise ModelComparisonError(f"{name}, fold {fold}: the {part} scores have no {metric}.")
        if not 0 <= scores[metric] <= 1:
            raise ModelComparisonError(f"{name}, fold {fold}: the {part} {metric} is {scores[metric]}, not between 0 and 1.")


def check_results(results: dict) -> None:
    """Stop with a message naming the problem if the results file is not what this report expects."""
    if results.get("features") != list(FINAL_FEATURES):
        raise ModelComparisonError(f"The results were not trained on the final feature list {list(FINAL_FEATURES)}.")
    missing = [name for name in MODEL_NAMES if name not in results.get("models", {})]
    if missing:
        raise ModelComparisonError(f"The results have no {', '.join(missing)}.")
    folds = results["folds"]
    for name in MODEL_NAMES:
        model_folds = results["models"][name]["folds"]
        if [fold["fold"] for fold in model_folds] != list(range(1, folds + 1)):
            raise ModelComparisonError(f"{name} does not have exactly {folds} folds, numbered 1 to {folds}.")
        model_totals = dict.fromkeys(COUNTS, 0)
        for fold in model_folds:
            _check_scores(name, fold["fold"], "cross-validation", fold["cv"])
            _check_scores(name, fold["fold"], "training", fold["train"])
            for count in COUNTS:
                model_totals[count] += fold["confusion"][count]
        # Each training row sits in exactly one held-out fold, so the counts must add up to all of them.
        if sum(model_totals.values()) != results["training_rows"]:
            raise ModelComparisonError(
                f"{name}'s held-out predictions add up to {sum(model_totals.values()):,} rows, "
                f"but every training row ({results['training_rows']:,}) must be predicted once."
            )
        if model_totals["tp"] + model_totals["fn"] != results["class_balance"]["phishing"]:
            raise ModelComparisonError(f"{name}'s held-out predictions do not cover every training row's phishing label once.")
    balance = results["class_balance"]
    if balance["phishing"] + balance["legitimate"] != results["training_rows"]:
        raise ModelComparisonError("The class balance does not add up to every training row.")


def fold_scores(results: dict, part: str) -> dict[str, pd.DataFrame]:
    """Each model's scores on every fold, one row per fold. part is "cv" or "train"."""
    return {
        name: pd.DataFrame([fold[part] for fold in results["models"][name]["folds"]])[list(METRICS)]
        for name in MODEL_NAMES
    }


def mean_scores(results: dict, part: str) -> pd.DataFrame:
    """The mean of each score over the folds, one row per model in MODEL_NAMES order."""
    return pd.DataFrame({name: table.mean() for name, table in fold_scores(results, part).items()}).T


def score_table(results: dict) -> pd.DataFrame:
    """The cross-validation mean and standard deviation of each score, one row per model.

    The spread is the sample standard deviation of the fold scores.
    """
    columns = {}
    for name, table in fold_scores(results, "cv").items():
        columns[name] = {f"{metric} {kind}": getattr(table[metric], kind)() for metric in METRICS for kind in ("mean", "std")}
    return pd.DataFrame(columns).T


def choose_model(cv_means: pd.DataFrame) -> tuple[str, str]:
    """The chosen model and the reason, by the team's rule.

    The highest mean phishing recall wins. Models within CLOSE of it are split by F1.
    Models also within CLOSE on F1 go to the simplest. The baseline is never a candidate.
    """
    candidates = cv_means.drop(index=BASELINE)
    best_recall = candidates["recall"].max()
    close_on_recall = candidates[candidates["recall"] >= best_recall - CLOSE - ROUNDING_TOLERANCE]
    if len(close_on_recall) == 1:
        name = close_on_recall.index[0]
        runner = candidates.drop(index=name)["recall"].idxmax()
        reason = (
            f"It has the highest mean phishing recall, {best_recall:.3f}. "
            f"The next best is {runner} at {candidates.loc[runner, 'recall']:.3f}."
        )
        return name, reason
    tied = " and ".join(close_on_recall.index)
    best_f1 = close_on_recall["f1"].max()
    close_on_f1 = close_on_recall[close_on_recall["f1"] >= best_f1 - CLOSE - ROUNDING_TOLERANCE]
    name = close_on_f1.index[0]
    if len(close_on_f1) == 1:
        reason = (
            f"{tied} are within {CLOSE} of each other on mean phishing recall. "
            f"{name} has the highest F1 of them, {best_f1:.3f}."
        )
    else:
        reason = (
            f"{' and '.join(close_on_f1.index)} are within {CLOSE} of each other on both mean phishing recall and F1, "
            f"so the simpler model, {name}, is chosen."
        )
    return name, reason


def fit_note(train_means: pd.DataFrame, cv_means: pd.DataFrame) -> str:
    """One line saying which models look overfit or underfit, and why."""
    candidates = [name for name in train_means.index if name != BASELINE]
    overfit = []
    for name in candidates:
        gaps = {metric: train_means.loc[name, metric] - cv_means.loc[name, metric] for metric in ("recall", "f1")}
        metric = max(gaps, key=gaps.get)
        if gaps[metric] > OVERFIT_GAP:
            label = "recall" if metric == "recall" else "F1"
            overfit.append(f"{name} looks overfit. Its training {label} is {gaps[metric]:.3f} above its cross-validation {label}.")
    underfit = [
        f"{name} looks underfit. Its F1 on its own training rows is only {train_means.loc[name, 'f1']:.3f}."
        for name in candidates
        if train_means.loc[name, "f1"] < UNDERFIT_F1
    ]
    parts = overfit or [f"No model looks overfit. Every training score is within {OVERFIT_GAP} of the cross-validation score."]
    parts += underfit or [f"No model looks underfit. Every training F1 is {UNDERFIT_F1:.2f} or more."]
    parts.append("The baseline is left out, because it always predicts the same class.")
    return " ".join(parts)


def class_balance_note(results: dict, chosen: str, cv_means: pd.DataFrame) -> str:
    """The class balance of the training part, and whether the chosen model uses class weights and why."""
    balance = results["class_balance"]
    rows = results["training_rows"]
    share = {label: 100 * balance[label] / rows for label in CLASSES}
    plain, weighted = cv_means.loc[PLAIN_LR], cv_means.loc[BALANCED_LR]
    effect = (
        f"On logistic regression, class weights moved mean phishing recall from {plain['recall']:.3f} to {weighted['recall']:.3f} "
        f"and precision from {plain['precision']:.3f} to {weighted['precision']:.3f}."
    )
    lines = [
        f"The training part has {balance['phishing']:,} phishing ({share['phishing']:.1f}%) "
        f"and {balance['legitimate']:,} legitimate ({share['legitimate']:.1f}%) links. "
        "Every fold keeps about that share. No rows are resampled.",
        effect,
    ]
    if chosen == BALANCED_LR:
        lines.append('The chosen model uses class weights (class_weight="balanced"), because with them it came first by the rule above.')
    else:
        lines.append("The chosen model does not use class weights, because the weighted logistic regression did not come first by the rule above.")
    return " ".join(lines)


def confusion_matrix(model: dict) -> pd.DataFrame:
    """The held-out folds' counts added up. Rows are the actual class, columns the predicted class."""
    total = {count: sum(fold["confusion"][count] for fold in model["folds"]) for count in COUNTS}
    return pd.DataFrame(
        [[total["tp"], total["fn"]], [total["fp"], total["tn"]]],
        index=list(CLASSES),
        columns=list(CLASSES),
    )


def confusion_chart(name: str, matrix: pd.DataFrame) -> Figure:
    """The confusion matrix as a picture, with the classes named in words and a count in each cell."""
    figure = Figure(figsize=CHART_SIZE_INCHES, layout="constrained")
    axis = figure.subplots()
    display = ConfusionMatrixDisplay(confusion_matrix=matrix.to_numpy(), display_labels=list(CLASSES))
    display.plot(ax=axis, cmap="Blues", colorbar=False, values_format=",d")
    axis.set_xlabel("Predicted")
    axis.set_ylabel("Actual")
    axis.set_title(f"{name}\nHeld-out predictions from cross-validation on the training rows", fontsize="medium")
    return figure


def matrix_file_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") + ".png"


def _cell(table: pd.DataFrame, name: str, metric: str) -> str:
    return f"{table.loc[name, f'{metric} mean']:.3f} ± {table.loc[name, f'{metric} std']:.3f}"


def report(results: dict) -> str:
    """The comparison table and the notes under it, as a Markdown page."""
    table = score_table(results)
    cv_means, train_means = mean_scores(results, "cv"), mean_scores(results, "train")
    chosen, reason = choose_model(cv_means)
    features = ", ".join(f"`{name}`" for name in results["features"])
    lines = [
        "# Model comparison",
        "",
        f"**{LABEL}**",
        "",
        "## How it was made",
        "",
        f"- {results['training_rows']:,} training rows. They are the training part of the shared host-grouped split. The test rows were not used.",
        f"- Stratified {results['folds']}-fold cross-validation, grouped by host, with seed {results['seed']}. No host is in two folds.",
        "- Inside each fold the scaler and the model are fitted together on the fold's training rows only.",
        f"- The {len(results['features'])} final features: {features}.",
        "- Phishing (label 1) is the positive class. Each score is the mean over the folds ± the standard deviation.",
        "- The training columns are the mean score on the rows each fold's model trained on.",
        "",
        "## Cross-validation scores",
        "",
        "| Model | Phishing recall | Recall on training rows | Precision | F1 | F1 on training rows | ROC-AUC | Accuracy |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name in MODEL_NAMES:
        cells = [
            _cell(table, name, "recall"),
            f"{train_means.loc[name, 'recall']:.3f}",
            _cell(table, name, "precision"),
            _cell(table, name, "f1"),
            f"{train_means.loc[name, 'f1']:.3f}",
            _cell(table, name, "roc_auc"),
            _cell(table, name, "accuracy"),
        ]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "Phishing recall is the main measure. It is the share of phishing links the model catches. "
        "Accuracy comes last, because the dataset's legitimate links are mostly big sites' front pages, which makes it look higher than it is.",
        "",
        f"## Chosen model: {chosen}",
        "",
        reason,
        "",
        f"By the team's rule the highest mean phishing recall wins. If models are within {CLOSE} on recall, the highest F1 wins. "
        f"If they are also within {CLOSE} on F1, the simpler model wins. The baseline is not a candidate.",
        "",
        "## Over- and underfitting",
        "",
        fit_note(train_means, cv_means),
        "",
        "## Class balance and class weights",
        "",
        class_balance_note(results, chosen, cv_means),
        "",
        "## Confusion matrices",
        "",
        f"Each matrix adds up the {results['folds']} held-out folds. Every training row is predicted once, by the fold's model that did not train on it. "
        "Rows are the actual class and columns the predicted class.",
        "",
        *(f"![{name}]({MATRIX_DIR_NAME}/{matrix_file_name(name)})" for name in MODEL_NAMES),
        "",
        "Made by `uv run python -m training.model_comparison`.",
    ]
    return "\n".join(lines) + "\n"


def load_results(path: Path) -> dict:
    if not path.is_file():
        raise ModelComparisonError(f'{path} was not found. Make it with "uv run python -m training.classifiers".')
    results = json.loads(path.read_text())
    check_results(results)
    return results


def main(ml_dir: Path) -> int:
    """Write the comparison page and the confusion matrices. Returns 1 and saves nothing if the results are wrong."""
    reports_dir = ml_dir / "reports"
    try:
        results = load_results(reports_dir / RESULTS_NAME)
        page = report(results)
    except ModelComparisonError as error:
        print(f"Model comparison stopped: {error}")
        return 1
    matrix_dir = reports_dir / MATRIX_DIR_NAME
    matrix_dir.mkdir(parents=True, exist_ok=True)
    for name in MODEL_NAMES:
        confusion_chart(name, confusion_matrix(results["models"][name])).savefig(matrix_dir / matrix_file_name(name), dpi=CHART_DPI)
    report_path = reports_dir / REPORT_NAME
    report_path.write_text(page)
    print(page)
    print(f"Saved {report_path} and {len(MODEL_NAMES)} confusion matrices in {matrix_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parents[1]))

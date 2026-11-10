"""Draw the confusion matrix and the ROC curve from the saved evaluation results.

Reads ml/reports/evaluation_results.json, which the evaluation script saves, so the test
rows are never read again here. Writes:

- ml/reports/evaluation_confusion_matrix.png: actual class down the side, predicted class
  along the top, both named "phishing" and "legitimate", with a count in each cell. The
  phishing row's share in the first cell is the phishing recall.
- ml/reports/evaluation_roc_curve.png: recall against false alarm rate at every score
  threshold, with the ROC-AUC written on the chart.

Built on matplotlib's Figure directly, not pyplot, so it draws the same way in tests and
scripts without needing a screen.

Run from ml/ after the evaluation:  uv run python -m evaluation.charts
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from matplotlib.figure import Figure
from sklearn.metrics import ConfusionMatrixDisplay

from evaluation.evaluate import RESULTS_PATH
from training.pipeline import ML_DIR

CONFUSION_PATH = ML_DIR / "reports" / "evaluation_confusion_matrix.png"
ROC_PATH = ML_DIR / "reports" / "evaluation_roc_curve.png"
CHART_DPI = 100
CHART_SIZE_INCHES = (5.6, 4.8)
CURVE_COLOUR = "#2e5e8c"
CHANCE_COLOUR = "#8a8a8a"
SUBTITLE = "Chosen model on the held-back PhiUSIIL test split"


class ChartError(Exception):
    """The evaluation results are missing or do not hold what the charts need."""


def load_results(path: Path) -> dict:
    if not path.is_file():
        raise ChartError(f"The evaluation results were not found at {path}. Run `uv run python -m evaluation.evaluate` first.")
    try:
        results = json.loads(path.read_text())
        needed = (
            results["confusion_matrix"]["counts"],
            results["confusion_matrix"]["labels"],
            results["roc_curve"]["false_alarm_rate"],
            results["roc_curve"]["recall"],
            results["test"]["roc_auc"],
            results["test"]["recall"],
        )
    except (ValueError, KeyError, TypeError) as error:
        raise ChartError(f"The evaluation results at {path} could not be read ({error!r}). Run the evaluation again.")
    if any(value is None for value in needed):
        raise ChartError(f"The evaluation results at {path} have an empty value. Run the evaluation again.")
    return results


def confusion_chart(results: dict) -> Figure:
    """The test confusion matrix, classes named in words and a count in each cell."""
    matrix = results["confusion_matrix"]
    figure = Figure(figsize=CHART_SIZE_INCHES, layout="constrained")
    axis = figure.subplots()
    display = ConfusionMatrixDisplay(confusion_matrix=np.array(matrix["counts"]), display_labels=matrix["labels"])
    display.plot(ax=axis, cmap="Blues", colorbar=False, values_format=",d")
    axis.set_xlabel("Predicted")
    axis.set_ylabel("Actual")
    recall = results["test"]["recall"]
    axis.set_title(f"Confusion matrix (test rows)\n{SUBTITLE}\nPhishing recall {recall:.3f}", fontsize="medium")
    return figure


def roc_chart(results: dict) -> Figure:
    """The test ROC curve with the ROC-AUC written on it."""
    curve, auc = results["roc_curve"], results["test"]["roc_auc"]
    figure = Figure(figsize=CHART_SIZE_INCHES, layout="constrained")
    axis = figure.subplots()
    axis.plot(curve["false_alarm_rate"], curve["recall"], color=CURVE_COLOUR, linewidth=2, label=f"Chosen model (ROC-AUC = {auc:.4f})")
    axis.plot([0, 1], [0, 1], color=CHANCE_COLOUR, linestyle="--", linewidth=1, label="Guessing (ROC-AUC = 0.5)")
    axis.text(0.55, 0.12, f"ROC-AUC = {auc:.4f}", fontsize="large", transform=axis.transAxes)
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1.01)
    axis.set_xlabel("False alarm rate (legitimate links flagged as phishing)")
    axis.set_ylabel("Phishing recall (phishing links caught)")
    axis.set_title(f"ROC curve (test rows)\n{SUBTITLE}", fontsize="medium")
    axis.legend(loc="lower right")
    return figure


def save_chart(figure: Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=CHART_DPI)
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, default=RESULTS_PATH, help="evaluation results JSON")
    parser.add_argument("--confusion", type=Path, default=CONFUSION_PATH, help="where to save the confusion matrix (.png)")
    parser.add_argument("--roc", type=Path, default=ROC_PATH, help="where to save the ROC curve (.png)")
    args = parser.parse_args(argv)
    try:
        results = load_results(args.results)
    except ChartError as error:
        print(f"Charts stopped: {error}", file=sys.stderr)
        return 1
    print(f"Saved {save_chart(confusion_chart(results), args.confusion).as_posix()}")
    print(f"Saved {save_chart(roc_chart(results), args.roc).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

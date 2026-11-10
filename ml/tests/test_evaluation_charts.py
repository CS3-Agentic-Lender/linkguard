"""Tests for the evaluation charts, drawn from a made-up results file."""

import json

import pytest

from evaluation.charts import ChartError, confusion_chart, load_results, main, roc_chart

RESULTS = {
    "test": {"recall": 0.75, "roc_auc": 0.958333},
    "confusion_matrix": {
        "rows": "actual",
        "columns": "predicted",
        "labels": ["phishing", "legitimate"],
        "counts": [[3, 1], [1, 5]],
    },
    "roc_curve": {"false_alarm_rate": [0.0, 0.0, 0.166667, 1.0], "recall": [0.0, 0.75, 1.0, 1.0]},
}


@pytest.fixture
def results_file(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(json.dumps(RESULTS))
    return path


def _texts(figure):
    axis = figure.axes[0]
    return [text.get_text() for text in axis.texts]


# Criterion 2: rows and columns are named in words, each cell shows a count, and the phishing row matches the recall.


def test_confusion_chart_names_classes_and_shows_counts():
    axis = confusion_chart(RESULTS).axes[0]
    assert [label.get_text() for label in axis.get_xticklabels()] == ["phishing", "legitimate"]
    assert [label.get_text() for label in axis.get_yticklabels()] == ["phishing", "legitimate"]
    assert (axis.get_xlabel(), axis.get_ylabel()) == ("Predicted", "Actual")
    assert sorted(_texts(confusion_chart(RESULTS))) == sorted(["3", "1", "1", "5"])


def test_confusion_chart_phishing_row_matches_recall():
    (caught, missed), _ = RESULTS["confusion_matrix"]["counts"]
    assert caught / (caught + missed) == RESULTS["test"]["recall"]
    assert "Phishing recall 0.750" in confusion_chart(RESULTS).axes[0].get_title()


# Criterion 3: the ROC curve is saved as a chart with the ROC-AUC written on it.


def test_roc_chart_has_the_auc_written_on_it():
    figure = roc_chart(RESULTS)
    assert "ROC-AUC = 0.9583" in _texts(figure)
    line = figure.axes[0].lines[0]
    assert list(line.get_xdata()) == RESULTS["roc_curve"]["false_alarm_rate"]
    assert list(line.get_ydata()) == RESULTS["roc_curve"]["recall"]


def test_main_saves_both_charts(results_file, tmp_path, capsys):
    confusion, roc = tmp_path / "cm.png", tmp_path / "roc.png"
    assert main([f"--results={results_file}", f"--confusion={confusion}", f"--roc={roc}"]) == 0
    for path in (confusion, roc):
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert "Saved" in capsys.readouterr().out


def test_missing_results_stop_with_a_plain_message(tmp_path, capsys):
    assert main([f"--results={tmp_path / 'none.json'}"]) == 1
    assert "were not found" in capsys.readouterr().err


def test_results_without_the_roc_points_are_refused(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(json.dumps({key: value for key, value in RESULTS.items() if key != "roc_curve"}))
    with pytest.raises(ChartError, match="could not be read"):
        load_results(path)

"""Tests for the precision/recall curve (ml/training/precision_recall.py).

They run on small made-up rows, because CI has no dataset. Their numbers say nothing about the
real model.
"""

import json

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from features.hostname import FEATURE_NAMES
from ranking.final_list import FINAL_FEATURES
from training.classifiers import FOLDS, fold_positions
from training.precision_recall import (
    CUTOFF_STEPS,
    TITLE,
    at_cutoff,
    chart,
    curve_table,
    main,
    out_of_fold_scores,
)

ROWS = 400
SETTINGS = {
    "learning_rate": 0.1,
    "max_iter": 20,
    "max_leaf_nodes": 7,
    "min_samples_leaf": 5,
}


def made_up_frame():
    generator = np.random.default_rng(0)
    host_number = np.arange(ROWS) // 4
    labels = (host_number % 3 == 0).astype(int)
    frame = pd.DataFrame({"row": range(ROWS)})
    for name in FEATURE_NAMES:
        frame[name] = generator.integers(0, 10, ROWS).astype(float)
    frame["HostnameLength"] = 10 + 4 * labels + generator.integers(0, 8, ROWS)
    frame["label"] = labels
    frame["host"] = [f"host{number}.example" for number in host_number]
    return frame


def training_parts():
    frame = made_up_frame()
    return frame.loc[:, list(FINAL_FEATURES)], frame["label"], frame["host"]


def write_inputs(folder):
    frame = made_up_frame()
    split = pd.DataFrame(
        {
            "row": range(ROWS),
            "set": np.where((np.arange(ROWS) // 4) % 5 == 4, "test", "train"),
        }
    )
    train = split["set"] == "train"
    paths = {
        "features": folder / "training_features.csv",
        "split": folder / "split.csv",
        "scaler": folder / "scaler.joblib",
        "results": folder / "tuning_results.json",
        "chart": folder / "reports" / "precision_recall.png",
        "curve": folder / "reports" / "precision_recall.json",
    }
    frame.to_csv(paths["features"], index=False)
    split.to_csv(paths["split"], index=False)
    joblib.dump(StandardScaler().fit(frame.loc[train, list(FEATURE_NAMES)]), paths["scaler"])
    paths["results"].write_text(json.dumps({"features": list(FINAL_FEATURES), "chosen": SETTINGS}))
    return paths, split


def arguments(paths):
    return [f"--{name}={path}" for name, path in paths.items()]


# Criterion 2: the curve comes from cross-validation predictions on the training rows.


def test_every_row_gets_one_score_from_a_model_that_never_saw_its_host(monkeypatch):
    features, labels, hosts = training_parts()
    fitted = []
    real_fit = Pipeline.fit

    def recording_fit(self, x, y=None, **kwargs):
        fitted.append(set(x.index))
        return real_fit(self, x, y, **kwargs)

    monkeypatch.setattr(Pipeline, "fit", recording_fit)

    scores = out_of_fold_scores(features, labels, hosts, SETTINGS)

    assert len(fitted) == FOLDS
    assert not np.isnan(scores).any() and ((scores >= 0) & (scores <= 1)).all()
    for (learn, held_out), learned_rows in zip(fold_positions(labels, hosts), fitted):
        assert learned_rows == set(features.index[learn])
        assert set(hosts.iloc[held_out]).isdisjoint(hosts.iloc[learn])


def test_the_folds_are_the_tuning_folds():
    from training import precision_recall, tuning

    assert precision_recall.fold_positions is tuning.fold_positions


def test_the_model_is_the_tuned_gradient_boosting(monkeypatch):
    features, labels, hosts = training_parts()
    models = []
    real_fit = Pipeline.fit

    def recording_fit(self, x, y=None, **kwargs):
        models.append(self.named_steps["model"].get_params())
        return real_fit(self, x, y, **kwargs)

    monkeypatch.setattr(Pipeline, "fit", recording_fit)

    out_of_fold_scores(features, labels, hosts, SETTINGS)

    for params in models:
        assert {name: params[name] for name in SETTINGS} == SETTINGS
        assert params["random_state"] == 0


def test_a_second_run_gives_the_same_scores():
    features, labels, hosts = training_parts()

    first = out_of_fold_scores(features, labels, hosts, SETTINGS)
    second = out_of_fold_scores(features, labels, hosts, SETTINGS)

    assert np.array_equal(first, second)


def test_main_reads_only_training_rows(tmp_path, monkeypatch):
    paths, split = write_inputs(tmp_path)
    seen = {}
    from training import precision_recall

    real = precision_recall.out_of_fold_scores

    def watching(features, labels, hosts, settings):
        seen["rows"] = set(features.index)
        seen["columns"] = list(features.columns)
        seen["settings"] = settings
        return real(features, labels, hosts, settings)

    monkeypatch.setattr(precision_recall, "out_of_fold_scores", watching)

    assert main(arguments(paths)) == 0

    assert seen["rows"] == set(split.loc[split["set"] == "train", "row"])
    assert seen["columns"] == list(FINAL_FEATURES)
    assert seen["settings"] == SETTINGS


# The numbers on the curve.


def test_recall_and_precision_at_a_cutoff_match_sklearn():
    labels = np.array([1, 1, 1, 0, 0, 0, 1, 0])
    scores = np.array([0.9, 0.6, 0.3, 0.7, 0.2, 0.1, 0.5, 0.5])

    point = at_cutoff(labels, scores, 0.5)

    predicted = (scores >= 0.5).astype(int)
    assert point["recall"] == pytest.approx(recall_score(labels, predicted))
    assert point["precision"] == pytest.approx(precision_score(labels, predicted))
    assert point["flagged_share"] == pytest.approx(5 / 8)


def test_a_score_exactly_at_the_cutoff_counts_as_phishing():
    point = at_cutoff(np.array([1, 0]), np.array([0.4, 0.1]), 0.4)

    assert point["recall"] == 1.0 and point["precision"] == 1.0


def test_the_table_covers_every_cutoff_from_0_to_1():
    labels = np.array([1, 0, 1, 0])
    table = curve_table(labels, np.array([0.8, 0.3, 0.6, 0.1]))

    assert [row["cutoff"] for row in table] == list(CUTOFF_STEPS)
    assert table[0]["cutoff"] == 0.0 and table[-1]["cutoff"] == 1.0
    assert table[0]["recall"] == 1.0 and table[0]["flagged_share"] == 1.0
    recalls = [row["recall"] for row in table]
    assert recalls == sorted(recalls, reverse=True)


def test_nothing_flagged_gives_precision_one_and_recall_zero():
    point = at_cutoff(np.array([1, 0]), np.array([0.2, 0.1]), 0.9)

    assert point == {
        "cutoff": 0.9,
        "recall": 0.0,
        "precision": 1.0,
        "flagged_share": 0.0,
    }


# Criteria 1 and 3: one command saves a titled, labelled chart that can mark two cut-offs.


def test_the_chart_has_a_title_and_labelled_axes():
    figure = chart(np.array([1, 0, 1, 0]), np.array([0.8, 0.3, 0.6, 0.1]))
    axis = figure.axes[0]

    assert axis.get_title() == TITLE
    assert "recall" in axis.get_xlabel().lower()
    assert "precision" in axis.get_ylabel().lower()


def test_the_chart_marks_each_cutoff_as_a_labelled_point():
    labels = np.array([1, 1, 0, 0, 1, 0])
    scores = np.array([0.9, 0.6, 0.7, 0.2, 0.3, 0.1])

    axis = chart(labels, scores, cutoffs=(0.25, 0.65)).axes[0]

    markers = [line for line in axis.get_lines() if line.get_marker() == "o"]
    assert len(markers) == 2
    for line, cutoff in zip(markers, (0.25, 0.65)):
        point = at_cutoff(labels, scores, cutoff)
        assert (line.get_xdata()[0], line.get_ydata()[0]) == (
            point["recall"],
            point["precision"],
        )
    labels_text = [text.get_text() for text in axis.texts]
    assert any("cut-off 0.25" in text for text in labels_text) and any("cut-off 0.65" in text for text in labels_text)


def test_the_chart_marks_nothing_when_no_cutoffs_are_given():
    axis = chart(np.array([1, 0, 1, 0]), np.array([0.8, 0.3, 0.6, 0.1])).axes[0]

    assert not [line for line in axis.get_lines() if line.get_marker() == "o"]


def test_main_saves_the_chart_and_the_curve(tmp_path, capsys):
    paths, split = write_inputs(tmp_path)

    assert main([*arguments(paths), "--cutoffs", "0.7", "0.2"]) == 0

    assert paths["chart"].read_bytes().startswith(b"\x89PNG")
    saved = json.loads(paths["curve"].read_text())
    assert saved["training_rows"] == int((split["set"] == "train").sum())
    assert saved["marked_cutoffs"] == [0.2, 0.7]
    assert len(saved["curve"]) == len(CUTOFF_STEPS)
    assert 0 <= saved["average_precision"] <= 1
    assert "Saved" in capsys.readouterr().out


def test_main_rejects_a_cutoff_outside_0_to_1(tmp_path):
    paths, _ = write_inputs(tmp_path)

    with pytest.raises(SystemExit):
        main([*arguments(paths), "--cutoffs", "0.2", "1.5"])


def test_main_stops_cleanly_without_the_tuning_results(tmp_path, capsys):
    paths, _ = write_inputs(tmp_path)
    paths["results"].unlink()

    assert main(arguments(paths)) == 1

    assert "Precision/recall stopped" in capsys.readouterr().err
    assert not paths["chart"].exists() and not paths["curve"].exists()

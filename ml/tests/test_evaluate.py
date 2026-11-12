"""Tests for the evaluation script, on a small made-up sample with known answers.

CI has no dataset or saved model, so each test writes its own tiny feature set, split,
scaler and model to a temporary folder. The numbers are made up and say nothing about how
the real model does.
"""

import ast
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

from cleaning.labels import LABEL_COLUMN
from evaluation import evaluate as evaluation
from evaluation.evaluate import (
    EvaluationError,
    ScoredRows,
    check_no_shared_hosts,
    confusion_matrix,
    fit_note,
    load_model,
    main,
    measures,
)
from features.hostname import FEATURE_NAMES
from splitting.split import save_split
from training.model_comparison import OVERFIT_GAP
from training.pipeline import HOSTNAME_COLUMN, ROW_COLUMN

ML_DIR = Path(__file__).resolve().parent.parent
N_ROWS = 40
# Hosts 1, 4 and 13 are phishing and 2, 6 and 9 legitimate, so the test set holds both classes.
TEST_HOSTS = {f"host{n}.example" for n in (1, 2, 4, 6, 9, 13)}


def made_up_rows() -> pd.DataFrame:
    """Row, ten features, label and host. Two rows per host; every third host is phishing."""
    rng = np.random.default_rng(1)
    frame = pd.DataFrame({ROW_COLUMN: range(N_ROWS)})
    hosts = [f"host{row // 2}.example" for row in range(N_ROWS)]
    labels = [1 if (row // 2) % 3 == 1 else 0 for row in range(N_ROWS)]
    for name in FEATURE_NAMES:
        frame[name] = rng.random(N_ROWS)
    # One feature carries the label with some noise, so a model can learn it but not perfectly.
    frame[FEATURE_NAMES[0]] = np.array(labels) * 2.0 + rng.normal(0, 0.8, N_ROWS)
    frame[LABEL_COLUMN] = labels
    frame[HOSTNAME_COLUMN] = hosts
    return frame


def write_inputs(folder: Path, frame: pd.DataFrame, test_hosts: set[str] = TEST_HOSTS) -> dict[str, Path]:
    """Write the feature set, the split by host, a scaler and a model fitted on the training rows."""
    paths = {name: folder / file for name, file in
             (("features", "features.csv"), ("split", "split.csv"), ("scaler", "scaler.joblib"),
              ("model", "model.joblib"), ("results", "results.json"))}
    frame.to_csv(paths["features"], index=False)
    sets = ["test" if host in test_hosts else "train" for host in frame[HOSTNAME_COLUMN]]
    hosts = frame.set_index(ROW_COLUMN)[HOSTNAME_COLUMN]
    save_split(pd.Series(sets, index=hosts.index, name="set"), hosts, paths["split"])
    train = frame[[s == "train" for s in sets]]
    scaler = StandardScaler().fit(train[list(FEATURE_NAMES)])
    joblib.dump(scaler, paths["scaler"])
    model = LogisticRegression().fit(scaler.transform(train[list(FEATURE_NAMES)]), train[LABEL_COLUMN])
    joblib.dump(model, paths["model"])
    return paths


def run(paths: dict[str, Path]) -> int:
    return main([f"--{name}={path}" for name, path in paths.items()])


@pytest.fixture
def inputs(tmp_path):
    return write_inputs(tmp_path, made_up_rows())


# Criterion 1: the script prints the five measures for the test set and saves them.


def test_measures_on_known_answers():
    # 4 phishing, 6 legitimate: 3 phishing caught, 1 missed, 1 legitimate wrongly flagged.
    scored = ScoredRows(
        labels=np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 0]),
        predicted=np.array([1, 1, 1, 0, 1, 0, 0, 0, 0, 0]),
        phishing_scores=np.array([0.9, 0.8, 0.7, 0.3, 0.6, 0.2, 0.1, 0.1, 0.05, 0.0]),
    )
    found = measures(scored)
    assert found["confusion"] == {"tp": 3, "fp": 1, "fn": 1, "tn": 5}
    scores = found["scores"]
    assert scores["recall"] == 0.75
    assert scores["precision"] == 0.75
    assert scores["f1"] == 0.75
    assert scores["accuracy"] == 0.8
    assert scores["false_alarm_rate"] == round(1 / 6, 6)
    assert scores["missed_phishing_rate"] == 0.25
    # 24 phishing-legitimate pairs; only the 0.3 phishing row is out-ranked, by the 0.6 legitimate row.
    assert scores["roc_auc"] == round(23 / 24, 6)


def test_script_prints_and_saves_the_test_measures(inputs, capsys):
    assert run(inputs) == 0
    printed = capsys.readouterr().out
    for words in ("Phishing recall", "Precision", "F1", "ROC-AUC", "Accuracy"):
        assert words in printed
    saved = json.loads(inputs["results"].read_text())
    for name in ("recall", "precision", "f1", "roc_auc", "accuracy"):
        assert name in saved["test"]


def test_saved_measures_match_scikit_learn(inputs):
    run(inputs)
    saved = json.loads(inputs["results"].read_text())
    frame = made_up_rows()
    test = frame[frame[HOSTNAME_COLUMN].isin(TEST_HOSTS)]
    scaler, model = joblib.load(inputs["scaler"]), joblib.load(inputs["model"])
    scaled = scaler.transform(test[list(FEATURE_NAMES)])
    predicted, actual = model.predict(scaled), test[LABEL_COLUMN]
    expected = {
        "recall": recall_score(actual, predicted, pos_label=1),
        "precision": precision_score(actual, predicted, pos_label=1, zero_division=0),
        "f1": f1_score(actual, predicted, pos_label=1),
        "accuracy": accuracy_score(actual, predicted),
        "roc_auc": roc_auc_score(actual, model.predict_proba(scaled)[:, 1]),
    }
    for name, value in expected.items():
        assert saved["test"][name] == pytest.approx(value, abs=1e-6)
    assert saved["test_rows"] == len(test)


def test_missing_model_stops_with_a_plain_message(inputs, capsys):
    inputs["model"].unlink()
    assert run(inputs) == 1
    assert "saved model was not found" in capsys.readouterr().err


def test_a_split_made_from_other_data_stops_the_evaluation(tmp_path, capsys):
    paths = write_inputs(tmp_path, made_up_rows())
    rebuilt = made_up_rows()
    rebuilt[HOSTNAME_COLUMN] = rebuilt[HOSTNAME_COLUMN].str.replace("example", "example.ie")
    rebuilt.to_csv(paths["features"], index=False)
    assert run(paths) == 1
    assert "different cleaned data" in capsys.readouterr().err


def test_a_file_that_is_not_a_classifier_is_refused(tmp_path):
    path = tmp_path / "model.joblib"
    joblib.dump(StandardScaler().fit([[0.0], [1.0]]), path)
    with pytest.raises(EvaluationError, match="not a fitted classifier"):
        load_model(path)


# Criterion 2: the confusion matrix names the classes in words, holds counts, and its phishing row gives the recall.


def test_confusion_matrix_names_classes_and_matches_recall(inputs):
    run(inputs)
    saved = json.loads(inputs["results"].read_text())
    matrix = saved["confusion_matrix"]
    assert matrix["labels"] == ["phishing", "legitimate"]
    assert (matrix["rows"], matrix["columns"]) == ("actual", "predicted")
    (caught, missed), (false_alarms, correct) = matrix["counts"]
    assert all(isinstance(count, int) for count in (caught, missed, false_alarms, correct))
    assert caught + missed + false_alarms + correct == saved["test_rows"]
    assert caught / (caught + missed) == pytest.approx(saved["test"]["recall"], abs=1e-6)


def test_confusion_matrix_layout():
    assert confusion_matrix({"tp": 3, "fp": 1, "fn": 1, "tn": 5})["counts"] == [[3, 1], [1, 5]]


# Criterion 4: no cleaned host is in both the test and the training set.


def test_no_cleaned_host_is_in_both_sets(inputs):
    frame = pd.read_csv(inputs["features"])
    split = pd.read_csv(inputs["split"])
    hosts = frame.set_index(ROW_COLUMN)[HOSTNAME_COLUMN]
    train_hosts = set(hosts[split.loc[split["set"] == "train", "row"]])
    test_hosts = set(hosts[split.loc[split["set"] == "test", "row"]])
    assert not train_hosts & test_hosts
    check_no_shared_hosts(pd.Series(sorted(train_hosts)), pd.Series(sorted(test_hosts)))


def test_a_host_in_both_sets_stops_the_evaluation(tmp_path, capsys):
    frame = made_up_rows()
    paths = write_inputs(tmp_path, frame)
    split = pd.read_csv(paths["split"])
    # Move one row of a test host into training, so that host is in both sets.
    first_test_row = split.index[split["set"] == "test"][0]
    split.loc[first_test_row, "set"] = "train"
    split.to_csv(paths["split"], index=False)
    assert run(paths) == 1
    assert "in both the training and the test set" in capsys.readouterr().err
    assert not paths["results"].exists()


def test_shared_host_guard_names_the_overlap():
    with pytest.raises(EvaluationError, match="1 cleaned hosts"):
        check_no_shared_hosts(pd.Series(["a.ie", "b.ie"]), pd.Series(["b.ie", "c.ie"]))


# Criterion 5: training recall and F1 sit next to the test values, with a one-line fit note.


def test_results_hold_training_scores_and_a_fit_note(inputs):
    run(inputs)
    saved = json.loads(inputs["results"].read_text())
    assert set(saved["training"]) == {"recall", "f1"}
    assert saved["training_rows"] + saved["test_rows"] == N_ROWS
    assert "\n" not in saved["fit_note"]
    assert saved["fit_note"].split(":")[0] in {"Overfitting", "Underfitting", "Neither"}


@pytest.mark.parametrize(
    ("train", "test", "verdict"),
    [
        ({"recall": 0.99, "f1": 0.99}, {"recall": 0.99 - OVERFIT_GAP - 0.01, "f1": 0.97}, "Overfitting"),
        ({"recall": 0.60, "f1": 0.60}, {"recall": 0.58, "f1": 0.59}, "Underfitting"),
        ({"recall": 0.97, "f1": 0.96}, {"recall": 0.95, "f1": 0.95}, "Neither"),
    ],
)
def test_fit_note(train, test, verdict):
    assert fit_note(train, test).startswith(verdict)


# Criterion 6: the evaluation script is the only ml/ code that picks out the test rows, and it scores one model.


SPLIT_NAMES = {"TEST", "TEST_SET", "SETS", "load_split"}

# Every ml/ module that names the test set or reads the whole split, and why. Only the evaluation
# script scores a model on test rows; any new module that names the test set fails this test until
# it is added here with its reason.
KNOWN_SPLIT_READERS = {
    "evaluation/evaluate.py": "scores the one saved chosen model on the test rows",
    "evaluation/charts.py": "reads the saved test scores from the results file; never reads rows or loads a model",
    "splitting/split.py": "makes, saves and checks the split",
    "training/pipeline.py": "names the test set only to refuse unknown set names; reads training rows only",
    "ranking/training_split.py": "names the test set only to refuse unknown set names; keeps training rows only",
    "leakage/conflicting_hosts.py": "data audit from an earlier story: counts hosts with both labels per set; no model",
}


def _names_the_test_set(tree: ast.AST) -> bool:
    """True if the code mentions the test set's name ("test", TEST, TEST_SET, SETS) or calls load_split."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "test":
            return True
        if isinstance(node, ast.Name) and node.id in SPLIT_NAMES:
            return True
        if isinstance(node, ast.Attribute) and node.attr in SPLIT_NAMES:
            return True
        if isinstance(node, ast.alias) and node.name in SPLIT_NAMES:
            return True
    return False


def test_only_the_evaluation_script_scores_the_test_rows():
    found = set()
    for path in ML_DIR.rglob("*.py"):
        relative = path.relative_to(ML_DIR)
        if relative.parts[0] in {"tests", ".venv"}:
            continue
        if _names_the_test_set(ast.parse(path.read_text(encoding="utf-8"))):
            found.add(relative.as_posix())
    assert found == set(KNOWN_SPLIT_READERS)
    # Of these, only the evaluation script makes predictions with a model.
    scorers = {name for name in found if ".predict" in (ML_DIR / name).read_text(encoding="utf-8")}
    assert scorers == {"evaluation/evaluate.py"}


def test_the_evaluation_loads_one_model(inputs, monkeypatch):
    loaded = []
    real_load = evaluation.load_model
    monkeypatch.setattr(evaluation, "load_model", lambda path: loaded.append(path) or real_load(path))
    assert run(inputs) == 0
    assert loaded == [inputs["model"]]

"""Tests for scoring the saved model on the outside test set.

CI has no outside CSVs, dataset or saved model, so each test writes tiny made-up ones to a
temporary folder. The links are made up (example.top style) and are never opened: a guard
makes any socket connection fail the test, which is how the tests show no network request
is made.
"""

import ast
import json
import socket
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from evaluation import evaluate, outside
from evaluation.evaluate import EvaluationError, ScoredRows
from evaluation.outside import (
    TABLE,
    drops,
    risk_level,
    risk_levels,
    load_outside_links,
    main,
    mistakes_by_host,
    outside_features,
    table,
)
from features.hostname import FEATURE_NAMES, extract_features

ML_DIR = Path(__file__).resolve().parent.parent

LEGIT = ["https://shop.example/basket?id=1", "https://news.example/today/", "https://www.mail.example/inbox"]
PHISHING = [
    "http://secure-login-0001.verify-account.top/x",
    "http://update-bank-9931.confirm-id.top/login",
    "http://182.20.4.9/paypal/",
]
PHIUSIIL_SCORES = {
    "recall": 0.5,
    "precision": 0.8,
    "f1": 0.6,
    "accuracy": 0.7,
    "roc_auc": 0.8,
    "false_alarm_rate": 0.05,
    "missed_phishing_rate": 0.5,
}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("A test tried to open a network connection.")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def write_inputs(folder: Path, legit=LEGIT, phishing=PHISHING) -> dict[str, Path]:
    """Outside CSVs, a feature set, a scaler and model fitted on the same links, and saved PhiUSIIL scores."""
    paths = {
        "legit": folder / "legit.csv",
        "phishing": folder / "phishing.csv",
        "features": folder / "features.csv",
        "scaler": folder / "scaler.joblib",
        "model": folder / "model.joblib",
        "phiusiil": folder / "evaluation_results.json",
        "cutoffs": folder / "cutoffs.json",
        "results": folder / "outside_results.json",
    }
    paths["cutoffs"].write_text(json.dumps({"lower": 0.2, "upper": 0.6}))
    pd.DataFrame({"url": legit, "label": 0, "source": "made up"}).to_csv(paths["legit"], index=False)
    pd.DataFrame({"url": phishing, "label": 1, "source": "made up"}).to_csv(paths["phishing"], index=False)
    training = pd.DataFrame([extract_features(link) for link in LEGIT + PHISHING], columns=list(FEATURE_NAMES))
    labels = [0] * len(LEGIT) + [1] * len(PHISHING)
    scaler = StandardScaler().fit(training)
    joblib.dump(scaler, paths["scaler"])
    joblib.dump(LogisticRegression().fit(scaler.transform(training), labels), paths["model"])
    pd.DataFrame({"host": ["shop.example", "other.example"]}).to_csv(paths["features"], index=False)
    paths["phiusiil"].write_text(json.dumps({"test": PHIUSIIL_SCORES}))
    return paths


def run(paths: dict[str, Path]) -> int:
    return main([f"--{name}={path}" for name, path in paths.items()])


# Criterion 1: features from the link text only, no network request


def test_the_scoring_code_imports_nothing_that_can_reach_the_network():
    tree = ast.parse((ML_DIR / "evaluation" / "outside.py").read_text())
    imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not imported & {"urllib", "requests", "http", "httpx", "socket", "aiohttp", "webbrowser"}


def test_a_full_run_opens_no_connection(tmp_path):
    # The autouse guard fails the test if anything connects.
    assert run(write_inputs(tmp_path)) == 0


def test_features_come_from_the_live_apps_extractor():
    links = pd.DataFrame({"url": LEGIT, "label": 0})
    features, _ = outside_features(links)
    assert list(features.columns) == list(FEATURE_NAMES)
    assert features.iloc[0].to_dict() == pytest.approx(extract_features(LEGIT[0]))


def test_a_link_the_extractor_cannot_read_is_left_out_and_counted():
    links = pd.DataFrame({"url": ["https://ok.example/", "http://[bad/x", "   "], "label": 0})
    features, unreadable = outside_features(links)
    assert list(features.index) == [0]
    assert unreadable == 2


# Criterion 2: one table, outside next to PhiUSIIL


def test_the_results_have_every_measure_for_both_sets(tmp_path):
    paths = write_inputs(tmp_path)
    assert run(paths) == 0
    saved = json.loads(paths["results"].read_text())
    for name in ("recall", "precision", "f1", "roc_auc", "false_alarm_rate"):
        assert name in saved["outside"]
        assert saved["phiusiil_test"][name] == PHIUSIIL_SCORES[name]
    assert saved["outside_class_counts"] == {"phishing": 3, "legitimate": 3}
    assert sum(map(sum, saved["confusion_matrix"]["counts"])) == 6


def test_the_printed_table_shows_both_sets_side_by_side(tmp_path, capsys):
    assert run(write_inputs(tmp_path)) == 0
    printed = capsys.readouterr().out
    assert "| Measure | Outside set | PhiUSIIL test split | Change (points, + is better) |" in printed
    for _, title in TABLE:
        assert f"| {title} |" in printed


def test_a_higher_false_alarm_rate_counts_as_a_drop():
    scores = {name: 0.5 for name, _ in TABLE}
    worse = dict(scores, false_alarm_rate=0.7, recall=0.3)
    gaps = drops(worse, scores)
    assert gaps["false_alarm_rate"] == pytest.approx(20)
    assert gaps["recall"] == pytest.approx(20)
    assert gaps["precision"] == 0


def test_drops_over_ten_points_are_listed(tmp_path):
    paths = write_inputs(tmp_path)
    worse = dict(PHIUSIIL_SCORES, recall=1.0, roc_auc=1.0, f1=1.0, precision=1.0, accuracy=1.0, false_alarm_rate=0.0)
    paths["phiusiil"].write_text(json.dumps({"test": worse}))
    assert run(paths) == 0
    saved = json.loads(paths["results"].read_text())
    assert set(saved["big_drops"]) == {name for name, gap in saved["drop_points"].items() if gap > 10}


def test_the_results_file_holds_no_links(tmp_path):
    paths = write_inputs(tmp_path)
    assert run(paths) == 0
    text = paths["results"].read_text()
    for link in LEGIT + PHISHING:
        assert link not in text
    assert "http" not in text


def test_mistakes_are_split_by_whether_the_host_is_in_phiusiil():
    scored = ScoredRows(
        labels=np.array([0, 0, 1, 1]), predicted=np.array([1, 1, 0, 1]), phishing_scores=np.array([0.9, 0.8, 0.1, 0.9])
    )
    links = pd.Series(["https://www.known.example/a", "https://new.example/", "http://bad.top/", "http://worse.top/"])
    found = mistakes_by_host(links, scored, {"known.example"})
    assert found["host_in_phiusiil"] == {"legitimate": 1, "false_alarms": 1, "phishing": 0, "missed": 0}
    assert found["new_host"] == {"legitimate": 1, "false_alarms": 1, "phishing": 2, "missed": 1}


# Criterion 3: the evaluation script's scoring is reused, not copied


def test_scoring_reuses_the_evaluation_script():
    for name in ("load_model", "score", "measures", "confusion_matrix", "counts"):
        assert getattr(outside, name) is getattr(evaluate, name)
    tree = ast.parse((ML_DIR / "evaluation" / "outside.py").read_text())
    defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert not defined & {"score", "measures", "counts", "roc_auc_score", "load_model"}


# Inputs


def test_a_missing_outside_file_says_how_to_collect_it(tmp_path):
    paths = write_inputs(tmp_path)
    paths["legit"].unlink()
    with pytest.raises(EvaluationError, match="outside test set"):
        load_outside_links(paths["legit"], paths["phishing"])


def test_a_file_with_the_wrong_label_is_refused(tmp_path):
    paths = write_inputs(tmp_path, legit=LEGIT)
    pd.DataFrame({"url": LEGIT, "label": 1}).to_csv(paths["legit"], index=False)
    with pytest.raises(EvaluationError, match="label 0"):
        load_outside_links(paths["legit"], paths["phishing"])


def test_an_empty_link_cell_is_counted_as_unreadable(tmp_path):
    paths = write_inputs(tmp_path)
    pd.DataFrame({"url": LEGIT + [""], "label": 0}).to_csv(paths["legit"], index=False)
    links = load_outside_links(paths["legit"], paths["phishing"])
    _, unreadable = outside_features(links)
    assert unreadable == 1


def test_main_stops_cleanly_when_the_phiusiil_results_are_missing(tmp_path, capsys):
    paths = write_inputs(tmp_path)
    paths["phiusiil"].unlink()
    assert run(paths) == 1
    assert "evaluation.evaluate" in capsys.readouterr().err


def test_the_output_is_in_reports_and_the_inputs_in_the_ignored_data_folder():
    assert outside.OUTSIDE_RESULTS_PATH.parent == ML_DIR / "reports"
    assert outside.LEGIT_PATH.is_relative_to(ML_DIR / "data")
    assert outside.PHISHING_PATH.is_relative_to(ML_DIR / "data")


# Risk levels the app shows


@pytest.mark.parametrize(
    ("score", "level"),
    [(0.0, "Safe"), (0.19, "Safe"), (0.2, "Suspicious"), (0.59, "Suspicious"), (0.6, "High risk"), (1.0, "High risk")],
)
def test_risk_levels_use_the_backends_rule(score, level):
    assert risk_level(score, 0.2, 0.6) == level


def test_each_link_lands_in_one_risk_level():
    scored = ScoredRows(
        labels=np.array([1, 1, 0, 0]), predicted=np.array([1, 0, 0, 1]), phishing_scores=np.array([0.9, 0.3, 0.1, 0.7])
    )
    found = risk_levels(scored, 0.2, 0.6)
    assert found["phishing"] == {"Safe": 0, "Suspicious": 1, "High risk": 1}
    assert found["legitimate"] == {"Safe": 1, "Suspicious": 0, "High risk": 1}
    assert found["cutoffs"] == {"lower": 0.2, "upper": 0.6}


def test_a_full_run_saves_and_prints_the_risk_levels(tmp_path, capsys):
    paths = write_inputs(tmp_path)
    assert run(paths) == 0
    saved = json.loads(paths["results"].read_text())["risk_levels"]
    assert sum(saved["phishing"].values()) == len(PHISHING)
    assert sum(saved["legitimate"].values()) == len(LEGIT)
    assert "| Links | Safe | Suspicious | High risk |" in capsys.readouterr().out


def test_the_cut_offs_are_the_ones_the_backend_reads():
    assert outside.CUTOFFS_PATH == ML_DIR / "models" / "cutoffs.json"
    backend = (ML_DIR.parent / "backend" / "app" / "risk.py").read_text()
    assert 'CUTOFFS_FILE = "cutoffs.json"' in backend


def test_bad_cut_offs_stop_the_run(tmp_path, capsys):
    paths = write_inputs(tmp_path)
    paths["cutoffs"].write_text(json.dumps({"lower": 0.7, "upper": 0.6}))
    assert run(paths) == 1
    assert "lower below upper" in capsys.readouterr().err

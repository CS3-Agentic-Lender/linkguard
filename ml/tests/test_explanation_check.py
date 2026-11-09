"""Tests for the reasons hand check (ml/training/explanation_check.py).

They use a scaler and a model fitted on small made-up rows, because CI has no dataset or
model file. Their numbers say nothing about the real model.
"""

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from features.explain import (
    KEEP_STEP,
    MODEL_STEP,
    linear_contributions,
    model_coefficients,
)
from features.hostname import FEATURE_NAMES, extract_features
from ranking.final_list import FINAL_FEATURES
from training import explanation_check
from training.explanation_check import (
    SAMPLE_LINKS,
    explain,
    main,
    report,
    slowest_scan_seconds,
)

# Made-up hosts, only handled as text: half look like plain names, half are long and full of digits.
MADE_UP_LINKS = [f"https://shop{n}.example.com/" for n in range(40)] + [
    f"https://login-{n}-verify-{n * 7}-account.example.net/" for n in range(40)
]


@pytest.fixture(scope="module")
def scaler_and_model():
    frame = pd.DataFrame([extract_features(link) for link in MADE_UP_LINKS], columns=list(FEATURE_NAMES))
    labels = np.array([0] * 40 + [1] * 40)
    scaler = StandardScaler().fit(frame)
    keep = [FEATURE_NAMES.index(name) for name in FINAL_FEATURES]
    model = Pipeline(
        [
            (KEEP_STEP, ColumnTransformer([("final", "passthrough", keep)], remainder="drop")),
            (MODEL_STEP, LogisticRegression(solver="liblinear", class_weight="balanced", C=0.01)),
        ]
    ).fit(scaler.transform(frame), labels)
    return scaler, model


@pytest.fixture()
def saved(tmp_path, scaler_and_model):
    scaler, model = scaler_and_model
    paths = {"scaler": tmp_path / "scaler.joblib", "model": tmp_path / "model.joblib", "report": tmp_path / "check.md"}
    joblib.dump(scaler, paths["scaler"])
    joblib.dump(model, paths["model"])
    return paths


def arguments(paths):
    return [f"--{name}={path}" for name, path in paths.items()]


def test_the_sample_links_are_five_made_up_ones():
    assert len(SAMPLE_LINKS) == 5
    assert all(".example" in link or "192.0.2." in link for link in SAMPLE_LINKS)


def test_the_explanation_shows_every_model_feature_and_the_picked_reasons(scaler_and_model):
    scaler, model = scaler_and_model

    entry = explain(SAMPLE_LINKS[1], scaler, model)

    assert list(entry["contributions"]) == list(FINAL_FEATURES)
    assert entry["contributions"] == linear_contributions(model_coefficients(model), entry["scaled"])
    assert all(entry["contributions"][name] > 0 for name in entry["reasons"])
    assert 0 <= entry["score"] <= 1


def test_the_report_marks_each_feature_and_lists_the_reasons(scaler_and_model):
    entries = [explain(link, *scaler_and_model) for link in SAMPLE_LINKS]

    text = report(entries, slowest=0.004)

    for link in SAMPLE_LINKS:
        assert f"### `{link}`" in text
    assert "never shown" in text  # the two watched features are always in the table
    assert "4.0 ms**, under the 2 s limit" in text


def test_each_feature_left_out_says_why():
    # A hand-made explanation: one feature for each way of being left out.
    scaled = {
        "IsDomainIP": 1.0,
        "NoOfDigitsInHostname": 1.0,
        "DigitRatioInHostname": 1.0,
        "NoOfSpecialCharsInHostname": 1.0,
        "HostnameLength": -1.0,
        "LetterRatioInHostname": -1.0,  # its sentence is about a smaller share of letters
        "TLDLength": 1.0,
        "NoOfSubDomain": 1.0,
    }
    contributions = {
        "IsDomainIP": 3.0,
        "NoOfDigitsInHostname": 2.5,
        "DigitRatioInHostname": 2.0,  # smaller of the two digit features
        "NoOfSpecialCharsInHostname": 1.5,
        "HostnameLength": 1.2,  # pushed up, but the name is shorter than average
        "LetterRatioInHostname": 1.1,  # pushed up and true, but fourth
        "TLDLength": 5.0,
        "NoOfSubDomain": -1.0,
    }
    entry = {"reasons": ("IsDomainIP", "NoOfDigitsInHostname", "NoOfSpecialCharsInHostname")}
    entry |= {"scaled": scaled, "contributions": contributions}

    labels = {name: explanation_check.why_shown_or_not(name, entry) for name in scaled}

    assert labels == {
        "IsDomainIP": "**Reason 1**",
        "NoOfDigitsInHostname": "**Reason 2**",
        "NoOfSpecialCharsInHostname": "**Reason 3**",
        "DigitRatioInHostname": "the other digit reason pushed more",
        "HostnameLength": "its sentence is not true for this link",
        "LetterRatioInHostname": "not in the top 3",
        "TLDLength": "never shown",
        "NoOfSubDomain": "never shown",
    }


def test_a_feature_that_lowered_the_score_says_so():
    entry = {"reasons": (), "scaled": {"HostnameLength": 1.0}, "contributions": {"HostnameLength": -0.5}}

    assert explanation_check.why_shown_or_not("HostnameLength", entry) == "lowered the score"


def test_the_report_says_when_a_scan_is_over_the_limit(scaler_and_model):
    text = report([explain(SAMPLE_LINKS[0], *scaler_and_model)], slowest=2.5)

    assert "OVER the 2 s limit" in text


def test_a_scan_with_reasons_is_timed(scaler_and_model):
    seconds = slowest_scan_seconds(SAMPLE_LINKS[0], *scaler_and_model, runs=3)

    assert 0 < seconds < 2


def test_main_writes_the_report(saved, monkeypatch, capsys):
    monkeypatch.setattr(explanation_check, "TIMING_RUNS", 3)

    assert main(arguments(saved)) == 0

    assert saved["report"].read_text().startswith("# Reasons hand check")
    assert "Slowest scan" in capsys.readouterr().out


def test_main_stops_with_a_message_when_the_model_is_missing(saved, capsys):
    saved["model"].unlink()

    assert main(arguments(saved)) == 1

    assert not saved["report"].exists()
    assert "training.final_model" in capsys.readouterr().err

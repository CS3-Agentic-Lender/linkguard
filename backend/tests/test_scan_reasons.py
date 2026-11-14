import dataclasses
import json
import logging
import time

import joblib
import pytest
from fastapi.testclient import TestClient
from features.explain import MAX_REASONS, reasons_for_link
from features.hostname import FEATURE_NAMES
from features.reasons import REASON_SENTENCES, reason_for
from sklearn.linear_model import LogisticRegression

from app import model as model_module
from app.main import app
from app.model import MODEL_FILE, ModelFileWrong, scaled_features
from app.risk import CUTOFFS_FILE

# Made-up links on reserved names and documentation addresses, only ever handled as text.
# With the fixture model and the agreed cut-offs, the first is Safe and the others High risk.
SAFE_LINK = "https://login.example/verify"
RISKY_LINK = "https://paypa1-support-2024.example/verify"
RISKY_WITHOUT_REASONS = "https://my-bank.example.co.uk"
LINKS = [
    SAFE_LINK,
    RISKY_LINK,
    RISKY_WITHOUT_REASONS,
    "https://192.0.2.10/account",
    "https://login-verify-account.example.com.secure-check.example/pay",
    "https://shop.example.net/basket",
]

# The reasons story's limit for a scan with reasons.
LIMIT_SECONDS = 2

# Words that must never reach the page (the reasons story, criterion 3).
TECHNICAL_WORDS = ("feature", "shap", "probability", "model", *(name.lower() for name in FEATURE_NAMES))


def scan(client, link):
    response = client.post("/scan", json={"url": link})
    assert response.status_code == 200
    return response.json()


def expected_reasons(client, link):
    """The sentences the shared reasons code picks for this link, worked out separately."""
    loaded = client.app.state.model
    scaled = dict(zip(FEATURE_NAMES, scaled_features(loaded, link)))
    return [reason_for(name) for name in reasons_for_link(loaded.model, loaded.explainer, scaled)]


def test_a_safe_link_gets_no_reasons_and_is_not_explained(client):
    calls = []
    loaded = client.app.state.model

    def counting_explainer(values):
        calls.append(values)
        return loaded.explainer(values)

    client.app.state.model = dataclasses.replace(loaded, explainer=counting_explainer)
    reply = scan(client, SAFE_LINK)

    assert reply["risk_level"] == "Safe"
    assert reply["reasons"] == []
    assert calls == []


def test_a_high_risk_link_gets_the_reasons_that_raised_its_score(client):
    reply = scan(client, RISKY_LINK)

    assert reply["risk_level"] == "High risk"
    assert reply["reasons"] == expected_reasons(client, RISKY_LINK)
    assert reply["reasons"] == ["Much of the website name is numbers or symbols, not letters."]


def test_a_suspicious_link_gets_its_reasons_too(fixture_model_dir):
    # The fixture model scores this link about 0.93, so these cut-offs make it Suspicious.
    (fixture_model_dir / CUTOFFS_FILE).write_text(json.dumps({"lower": 0.5, "upper": 0.95}), encoding="utf-8")

    with TestClient(app) as client:
        reply = scan(client, RISKY_LINK)

        assert reply["risk_level"] == "Suspicious"
        assert reply["reasons"] == expected_reasons(client, RISKY_LINK)
        assert reply["reasons"] != []


def test_a_scan_keeps_its_score_when_the_reasons_fail(client, caplog):
    def broken_explainer(values):
        return [1.0]  # one push for eight kept features, so the shared code raises ValueError

    client.app.state.model = dataclasses.replace(client.app.state.model, explainer=broken_explainer)
    with caplog.at_level(logging.WARNING, logger="app.reasons"):
        response = client.post("/scan", json={"url": RISKY_LINK})

    assert response.status_code == 200
    reply = response.json()
    assert reply["risk_level"] == "High risk"
    assert 0 <= reply["score"] <= 1
    assert reply["reasons"] == []
    assert "Couldn't work out the reasons for a High risk link" in caplog.text


def test_a_risky_link_can_have_no_reasons(client):
    # Then the page shows its general sentence instead (the reasons story's PO call).
    reply = scan(client, RISKY_WITHOUT_REASONS)

    assert reply["risk_level"] == "High risk"
    assert reply["reasons"] == []


@pytest.mark.parametrize("link", LINKS)
def test_reasons_are_up_to_three_plain_sentences(client, link):
    reply = scan(client, link)

    assert len(reply["reasons"]) <= MAX_REASONS
    assert len(set(reply["reasons"])) == len(reply["reasons"])
    for sentence in reply["reasons"]:
        assert sentence in REASON_SENTENCES.values()
        assert not any(word in sentence.lower() for word in TECHNICAL_WORDS)


def test_the_explainer_is_built_once_at_startup(fixture_model_dir, monkeypatch):
    builds = []
    real_tree_explainer = model_module.tree_explainer

    def counting_tree_explainer(model):
        builds.append(model)
        return real_tree_explainer(model)

    monkeypatch.setattr(model_module, "tree_explainer", counting_tree_explainer)

    with TestClient(app) as client:
        assert len(builds) == 1
        for link in LINKS:
            scan(client, link)

        assert len(builds) == 1


def test_a_scan_with_reasons_takes_under_two_seconds(client):
    slowest = 0.0
    for _ in range(10):
        started = time.perf_counter()
        reply = scan(client, RISKY_LINK)
        slowest = max(slowest, time.perf_counter() - started)

    assert reply["reasons"] != []
    assert slowest < LIMIT_SECONDS


def test_startup_stops_if_the_model_is_not_the_saved_shape(fixture_model_dir):
    # A model without the keep-the-final-features step can't be explained.
    joblib.dump(LogisticRegression().fit([[0.0] * 10, [1.0] * 10], [0, 1]), fixture_model_dir / MODEL_FILE)

    with pytest.raises(ModelFileWrong, match="saved model's shape") as stopped:
        with TestClient(app):
            pass

    assert str(fixture_model_dir / MODEL_FILE) in str(stopped.value)

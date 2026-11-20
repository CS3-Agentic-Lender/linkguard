import json
import socket

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient
from features.hostname import FEATURE_NAMES, extract_features
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.main import app
from app.model import MODEL_DIR_VARIABLE, MODEL_FILE, SCALER_FILE
from app.risk import CUTOFFS_FILE

# Made-up links on reserved names, only ever handled as text. Label 1 is phishing.
SAMPLE_ROWS = [
    ("https://example.com", 0),
    ("https://www.example.org", 0),
    ("https://shop.example.net/basket", 0),
    ("https://login-verify-account.example.com.secure-check.example/pay", 1),
    ("https://192.0.2.10/account", 1),
    ("https://paypa1-support-2024.example/verify", 1),
]

# The two features the final feature list drops, as ml/ranking/final_list.py says.
# The saved model leaves them out itself, so the fixture model does too.
DROPPED = ("NoOfLettersInHostname", "SpecialCharRatioInHostname")
KEPT = [FEATURE_NAMES.index(name) for name in FEATURE_NAMES if name not in DROPPED]

# The cut-offs the team agreed, in the shape the cut-offs story saves them.
CUTOFFS = {"lower": 0.20, "upper": 0.60}

LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def fixture_scaler_and_model():
    """A small scaler and model shaped like the saved ones, fitted on the sample rows.

    Like the real files: the scaler knows the feature names in order, because the
    training code fits it on a table, and the model is a Pipeline that keeps the
    final features, then gradient boosting.
    """
    rows = [[extract_features(link)[name] for name in FEATURE_NAMES] for link, _ in SAMPLE_ROWS]
    labels = [label for _, label in SAMPLE_ROWS]
    scaler = StandardScaler().fit(rows)
    model = Pipeline(
        [
            ("keep_final_features", ColumnTransformer([("final", "passthrough", KEPT)], remainder="drop")),
            ("model", HistGradientBoostingClassifier(min_samples_leaf=1, max_iter=20, random_state=0)),
        ]
    ).fit(scaler.transform(rows), labels)
    scaler.feature_names_in_ = np.array(FEATURE_NAMES, dtype=object)
    return scaler, model


@pytest.fixture
def fixture_model_dir(tmp_path, monkeypatch):
    """The fixture scaler, model and cut-offs, saved like the real files.

    Nothing here is committed: the files live in pytest's temporary folder.
    """
    scaler, model = fixture_scaler_and_model()
    joblib.dump(scaler, tmp_path / SCALER_FILE)
    joblib.dump(model, tmp_path / MODEL_FILE)
    (tmp_path / CUTOFFS_FILE).write_text(json.dumps(CUTOFFS), encoding="utf-8")
    monkeypatch.setenv(MODEL_DIR_VARIABLE, str(tmp_path))
    return tmp_path


@pytest.fixture
def client(fixture_model_dir):
    """A test client for the app, started with the fixture model."""
    with TestClient(app) as started:
        yield started


@pytest.fixture
def no_network(monkeypatch):
    """Fail the test if anything tries to open an outgoing connection.

    Loopback is still allowed: on Windows the event loop that runs the test
    client connects a socket to itself on 127.0.0.1 when it starts.
    """
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def check(host):
        if host not in LOOPBACK:
            raise AssertionError(f"a network connection was attempted to {host}")

    def connect(sock, address):
        check(address[0])
        return real_connect(sock, address)

    def connect_ex(sock, address):
        check(address[0])
        return real_connect_ex(sock, address)

    def getaddrinfo(host, *args, **kwargs):
        check(host)
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)

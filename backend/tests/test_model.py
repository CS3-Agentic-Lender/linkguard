import joblib
import pytest
from fastapi.testclient import TestClient
from features.hostname import FEATURE_NAMES, extract_features
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from app import model as model_module
from app.main import app
from app.model import (
    DEFAULT_MODEL_DIR,
    MODEL_DIR_VARIABLE,
    MODEL_FILE,
    SCALER_FILE,
    ModelFileMissing,
    load_model,
)

# Made-up links on reserved names, only ever handled as text. Label 1 is phishing.
SAMPLE_ROWS = [
    ("https://example.com", 0),
    ("https://www.example.org", 0),
    ("https://shop.example.net/basket", 0),
    ("https://login-verify-account.example.com.secure-check.example/pay", 1),
    ("https://192.0.2.10/account", 1),
    ("https://paypa1-support-2024.example/verify", 1),
]

LINK = "https://login.example/verify"


@pytest.fixture
def fixture_model_dir(tmp_path, monkeypatch):
    """A small scaler and model fitted on the sample rows, saved like the real files.

    Nothing here is committed: the files live in pytest's temporary folder.
    """
    rows = [[extract_features(link)[name] for name in FEATURE_NAMES] for link, _ in SAMPLE_ROWS]
    labels = [label for _, label in SAMPLE_ROWS]
    scaler = StandardScaler().fit(rows)
    model = LogisticRegression().fit(scaler.transform(rows), labels)
    joblib.dump(scaler, tmp_path / SCALER_FILE)
    joblib.dump(model, tmp_path / MODEL_FILE)
    monkeypatch.setenv(MODEL_DIR_VARIABLE, str(tmp_path))
    return tmp_path


@pytest.fixture
def load_calls(monkeypatch):
    """Records every file joblib loads, while still loading it."""
    calls = []
    real_load = joblib.load

    def counting_load(path, *args, **kwargs):
        calls.append(path)
        return real_load(path, *args, **kwargs)

    monkeypatch.setattr(model_module.joblib, "load", counting_load)
    return calls


def test_loads_the_scaler_and_model_once_at_startup(fixture_model_dir, load_calls):
    with TestClient(app) as client:
        # Both files are already loaded before the first /scan call.
        assert [path.name for path in load_calls] == [SCALER_FILE, MODEL_FILE]

        for _ in range(3):
            assert client.post("/scan", json={"url": LINK}).status_code == 200

        # Several calls later, nothing has been loaded again.
        assert len(load_calls) == 2
        assert isinstance(app.state.model.scaler, StandardScaler)
        assert isinstance(app.state.model.model, LogisticRegression)


@pytest.mark.parametrize("missing", [SCALER_FILE, MODEL_FILE])
def test_startup_stops_and_names_a_missing_file(fixture_model_dir, load_calls, missing):
    (fixture_model_dir / missing).unlink()

    with pytest.raises(ModelFileMissing, match=missing) as stopped:
        with TestClient(app):
            pass

    assert str(fixture_model_dir / missing) in str(stopped.value)
    # Neither file is loaded once one is known to be missing.
    assert load_calls == []


def test_startup_names_the_first_missing_file_when_both_are_gone(tmp_path, monkeypatch):
    monkeypatch.setenv(MODEL_DIR_VARIABLE, str(tmp_path))

    with pytest.raises(ModelFileMissing, match=SCALER_FILE):
        with TestClient(app):
            pass


def test_load_model_reads_the_given_folder(fixture_model_dir):
    loaded = load_model(fixture_model_dir)

    assert isinstance(loaded.scaler, StandardScaler)
    assert isinstance(loaded.model, LogisticRegression)


def test_default_folder_is_ml_models_as_the_ml_readme_says(monkeypatch):
    monkeypatch.delenv(MODEL_DIR_VARIABLE, raising=False)

    assert model_module.model_dir() == DEFAULT_MODEL_DIR
    assert DEFAULT_MODEL_DIR.parts[-2:] == ("ml", "models")

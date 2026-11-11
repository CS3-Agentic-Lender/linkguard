import joblib
import pytest
from fastapi.testclient import TestClient
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app import model as model_module
from app.main import app
from app.model import (
    DEFAULT_MODEL_DIR,
    MODEL_DIR_VARIABLE,
    MODEL_FILE,
    SCALER_FILE,
    ModelFileMissing,
    ModelFileWrong,
    load_model,
)
from conftest import fixture_scaler_and_model

LINK = "https://login.example/verify"


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
        assert isinstance(app.state.model.model, Pipeline)


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
    # The same shape as the saved model: keep the final features, then the model.
    assert isinstance(loaded.model, Pipeline)
    assert list(loaded.model.named_steps) == ["keep_final_features", "model"]


def test_startup_stops_if_the_scaler_expects_another_feature_order(tmp_path, monkeypatch):
    scaler, model = fixture_scaler_and_model()
    scaler.feature_names_in_ = np.array(list(reversed(scaler.feature_names_in_)), dtype=object)
    joblib.dump(scaler, tmp_path / SCALER_FILE)
    joblib.dump(model, tmp_path / MODEL_FILE)
    monkeypatch.setenv(MODEL_DIR_VARIABLE, str(tmp_path))

    with pytest.raises(ModelFileWrong, match="different order") as stopped:
        with TestClient(app):
            pass

    assert str(tmp_path / SCALER_FILE) in str(stopped.value)


def test_default_folder_is_ml_models_as_the_ml_readme_says(monkeypatch):
    monkeypatch.delenv(MODEL_DIR_VARIABLE, raising=False)

    assert model_module.model_dir() == DEFAULT_MODEL_DIR
    assert DEFAULT_MODEL_DIR.parts[-2:] == ("ml", "models")

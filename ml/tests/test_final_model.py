"""Tests for saving the final model (ml/training/final_model.py).

They run on small made-up rows, because CI has no dataset or model file. Their numbers say
nothing about the real model.
"""

import json
import subprocess

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from features.hostname import FEATURE_NAMES
from ranking.final_list import FINAL_FEATURES
from training.final_model import (
    CHECK_ROWS,
    MODEL_PATH,
    FinalModelError,
    build_model,
    check_rows,
    chosen_settings,
    load_check,
    main,
    save_checked,
    save_model,
)
from training.pipeline import ML_DIR

ROWS = 200
SETTINGS = {"C": 0.01, "l1_ratio": 0.0}


def made_up_frame():
    generator = np.random.default_rng(0)
    host_number = np.arange(ROWS) // 4
    labels = (host_number % 3 == 0).astype(int)
    frame = pd.DataFrame({"row": range(ROWS)})
    for name in FEATURE_NAMES:
        frame[name] = generator.integers(0, 10, ROWS).astype(float)
    frame["HostnameLength"] = 10 + 6 * labels + generator.integers(0, 6, ROWS)
    frame["label"] = labels
    frame["host"] = [f"host{number}.example" for number in host_number]
    return frame


def write_inputs(folder, chosen=SETTINGS, features=FINAL_FEATURES):
    frame = made_up_frame()
    split = pd.DataFrame({"row": range(ROWS), "set": np.where((np.arange(ROWS) // 4) % 5 == 4, "test", "train")})
    train = split["set"] == "train"
    paths = {
        "features": folder / "training_features.csv",
        "split": folder / "split.csv",
        "scaler": folder / "scaler.joblib",
        "results": folder / "tuning_results.json",
        "model": folder / "models" / "model.joblib",
    }
    frame.to_csv(paths["features"], index=False)
    split.to_csv(paths["split"], index=False)
    joblib.dump(StandardScaler().fit(frame.loc[train, list(FEATURE_NAMES)]), paths["scaler"])
    paths["results"].write_text(json.dumps({"features": list(features), "chosen": chosen}))
    return paths, frame, split


def arguments(paths):
    return [f"--{name}={path}" for name, path in paths.items()]


def fitted(frame):
    scaled = StandardScaler().fit_transform(frame[list(FEATURE_NAMES)])
    return build_model(SETTINGS).fit(scaled, frame["label"].to_numpy()), scaled


# Criterion 4: one file at the README's path, never ready to commit.


def test_the_model_file_is_in_ml_models_as_the_readme_says():
    assert MODEL_PATH == ML_DIR / "models" / "model.joblib"
    assert "`ml/models/model.joblib`" in (ML_DIR / "README.md").read_text()


def test_git_ignores_the_model_and_scaler_files():
    for path in (MODEL_PATH, ML_DIR / "models" / "scaler.joblib"):
        ignored = subprocess.run(["git", "check-ignore", "-q", str(path)], cwd=ML_DIR, check=False)
        assert ignored.returncode == 0, f"{path} is not ignored by git"


def test_main_saves_one_model_file(tmp_path, capsys):
    paths, _, _ = write_inputs(tmp_path)

    assert main(arguments(paths)) == 0

    assert [file.name for file in paths["model"].parent.iterdir()] == ["model.joblib"]
    assert "Load check passed" in capsys.readouterr().out


# The saved model: tuned settings, the 8 final features out of the ten scaled ones.


def test_the_model_uses_the_tuned_settings_and_fixed_class_weight():
    model = build_model({"C": 10.0, "l1_ratio": 1.0})

    estimator = model.named_steps["model"]
    assert isinstance(estimator, LogisticRegression)
    assert estimator.C == 10.0 and estimator.l1_ratio == 1.0
    assert estimator.class_weight == "balanced"
    assert estimator.solver == "liblinear"


def test_the_model_takes_ten_scaled_features_and_keeps_only_the_final_eight():
    frame = made_up_frame()
    model, scaled = fitted(frame)

    assert model.named_steps["model"].n_features_in_ == len(FINAL_FEATURES)
    keep = [FEATURE_NAMES.index(name) for name in FINAL_FEATURES]
    np.testing.assert_array_equal(model.named_steps["keep_final_features"].transform(scaled), scaled[:, keep])


def test_dropped_features_do_not_change_the_prediction():
    frame = made_up_frame()
    model, scaled = fitted(frame)
    changed = scaled.copy()
    for name in set(FEATURE_NAMES) - set(FINAL_FEATURES):
        changed[:, FEATURE_NAMES.index(name)] = 999.0

    np.testing.assert_array_equal(model.predict_proba(scaled), model.predict_proba(changed))


def test_main_fits_on_training_rows_only(tmp_path, monkeypatch):
    paths, _, split = write_inputs(tmp_path)
    fitted_rows = []
    real_fit = Pipeline.fit

    def recording_fit(self, x, y=None, **kwargs):
        fitted_rows.append(len(x))
        return real_fit(self, x, y, **kwargs)

    monkeypatch.setattr(Pipeline, "fit", recording_fit)

    assert main(arguments(paths)) == 0

    assert fitted_rows == [int((split["set"] == "train").sum())]


# Criterion 5: a fresh Python session gives the same predictions as before saving.


def test_load_check_passes_for_a_saved_model(tmp_path):
    model, scaled = fitted(made_up_frame())
    path = save_model(model, tmp_path / "model.joblib")

    load_check(path, scaled[:CHECK_ROWS], model)  # raises if anything differs


def test_load_check_catches_a_file_that_predicts_differently(tmp_path):
    frame = made_up_frame()
    model, scaled = fitted(frame)
    other = build_model({"C": 0.001, "l1_ratio": 1.0}).fit(scaled, 1 - frame["label"].to_numpy())
    path = save_model(other, tmp_path / "model.joblib")

    with pytest.raises(FinalModelError, match="different"):
        load_check(path, scaled[:CHECK_ROWS], model)


def test_load_check_catches_a_file_that_will_not_load(tmp_path):
    model, scaled = fitted(made_up_frame())
    path = tmp_path / "model.joblib"
    path.write_text("not a model")

    with pytest.raises(FinalModelError, match="fresh Python session"):
        load_check(path, scaled[:CHECK_ROWS], model)


def test_a_file_that_fails_the_check_is_not_left_where_the_backend_loads(tmp_path, monkeypatch):
    model, scaled = fitted(made_up_frame())
    path = tmp_path / "model.joblib"

    def failing_check(file, rows, fitted_model):
        raise FinalModelError("different")

    monkeypatch.setattr("training.final_model.load_check", failing_check)

    with pytest.raises(FinalModelError):
        save_checked(model, path, scaled[:CHECK_ROWS])

    assert list(tmp_path.iterdir()) == []


def test_the_check_rows_are_spread_over_the_training_set():
    scaled = np.arange(1000, dtype=float).reshape(-1, 1)

    rows = check_rows(scaled)

    assert len(rows) == CHECK_ROWS
    assert rows[0, 0] == 0 and rows[-1, 0] == 999


# Stopping with a message.


def test_main_stops_when_the_tuning_results_are_missing(tmp_path, capsys):
    paths, _, _ = write_inputs(tmp_path)
    paths["results"].unlink()

    assert main(arguments(paths)) == 1

    assert not paths["model"].exists()
    assert "training.tuning" in capsys.readouterr().err


def test_main_stops_when_the_results_use_another_feature_list(tmp_path, capsys):
    paths, _, _ = write_inputs(tmp_path, features=FEATURE_NAMES)

    assert main(arguments(paths)) == 1

    assert not paths["model"].exists()
    assert "final feature list" in capsys.readouterr().err


def test_main_stops_cleanly_when_the_results_file_is_broken(tmp_path, capsys):
    paths, _, _ = write_inputs(tmp_path)
    paths["results"].write_text("{not json")

    assert main(arguments(paths)) == 1

    assert not paths["model"].exists()
    assert "could not be read" in capsys.readouterr().err


def test_chosen_settings_reads_c_and_l1_ratio(tmp_path):
    paths, _, _ = write_inputs(tmp_path, chosen={"C": 100, "l1_ratio": 1})

    assert chosen_settings(paths["results"]) == {"C": 100.0, "l1_ratio": 1.0}

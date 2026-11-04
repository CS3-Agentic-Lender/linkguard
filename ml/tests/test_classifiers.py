import json

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from features.hostname import FEATURE_NAMES
from ranking.final_list import FINAL_FEATURES
from training import classifiers
from training.classifiers import (
    FOLDS,
    MEASURES,
    MODELS,
    cross_validate_models,
    fold_positions,
    main,
)

ROWS = 400


def made_up_rows(rows: int = ROWS):
    """Made-up training rows: 8 rows per host, HostnameLength follows the label, the rest is noise."""
    generator = np.random.default_rng(0)
    host_number = np.arange(rows) // 8
    labels = pd.Series(host_number % 3 == 0, dtype=int, index=range(rows))
    features = pd.DataFrame(index=range(rows))
    for name in FINAL_FEATURES:
        features[name] = generator.integers(0, 10, rows).astype(float)
    features["HostnameLength"] = 10 + 15 * labels + generator.integers(0, 4, rows)
    hosts = pd.Series([f"host{number}.example" for number in host_number], index=range(rows))
    return features, labels, hosts


def test_folds_keep_every_host_on_one_side_and_test_every_row_once():
    _, labels, hosts = made_up_rows()

    positions = fold_positions(labels, hosts)

    assert len(positions) == FOLDS
    tested = np.concatenate([held_out for _, held_out in positions])
    assert sorted(tested) == list(range(ROWS))
    for learn, held_out in positions:
        assert set(hosts.iloc[learn]).isdisjoint(hosts.iloc[held_out])


def test_folds_are_the_same_on_every_run():
    _, labels, hosts = made_up_rows()

    first, second = fold_positions(labels, hosts), fold_positions(labels, hosts)

    for (a_learn, a_out), (b_learn, b_out) in zip(first, second):
        assert list(a_learn) == list(b_learn) and list(a_out) == list(b_out)


def test_every_model_has_five_folds_of_scores_and_counts():
    results = cross_validate_models(*made_up_rows())

    assert list(results) == list(MODELS)
    assert len(MODELS) >= 4  # at least three classifiers and the baseline
    for folds in results.values():
        assert [fold["fold"] for fold in folds] == list(range(1, FOLDS + 1))
        for fold in folds:
            assert set(fold["cv"]) == set(MEASURES) == set(fold["train"])
            assert set(fold["confusion"]) == {"tp", "fp", "fn", "tn"}


def test_confusion_counts_cover_every_row_exactly_once():
    features, labels, hosts = made_up_rows()

    results = cross_validate_models(features, labels, hosts)

    for folds in results.values():
        totals = {key: sum(fold["confusion"][key] for fold in folds) for key in ("tp", "fp", "fn", "tn")}
        assert sum(totals.values()) == ROWS
        assert totals["tp"] + totals["fn"] == int(labels.sum())


def test_the_baseline_always_predicts_the_most_common_class():
    features, labels, hosts = made_up_rows()

    baseline = cross_validate_models(features, labels, hosts)["Baseline (most common class)"]

    # Legitimate is the most common class here, so it never flags a phishing link.
    assert all(fold["cv"]["recall"] == 0 for fold in baseline)
    assert all(fold["confusion"]["tp"] == 0 and fold["confusion"]["fp"] == 0 for fold in baseline)


def test_a_real_model_beats_the_baseline_on_recall():
    results = cross_validate_models(*made_up_rows())

    mean_recall = {name: np.mean([fold["cv"]["recall"] for fold in folds]) for name, folds in results.items()}
    assert mean_recall["Random forest"] > mean_recall["Baseline (most common class)"]


def test_a_second_run_gives_the_same_results():
    assert cross_validate_models(*made_up_rows()) == cross_validate_models(*made_up_rows())


def test_held_out_rows_never_reach_a_fit(monkeypatch):
    # Every fit records the row labels it was given. A held-out row in any fit would show up.
    features, labels, hosts = made_up_rows()
    fitted_rows = []
    real_fit = Pipeline.fit

    def recording_fit(self, x, y=None, **kwargs):
        fitted_rows.append(set(x.index))
        return real_fit(self, x, y, **kwargs)

    monkeypatch.setattr(Pipeline, "fit", recording_fit)

    cross_validate_models(features, labels, hosts)

    positions = fold_positions(labels, hosts)
    assert len(fitted_rows) == len(MODELS) * FOLDS
    for number, rows in enumerate(fitted_rows):
        _, held_out = positions[number % FOLDS]
        assert rows.isdisjoint(features.index[held_out])


def test_every_scaler_fit_sees_exactly_its_folds_training_rows(monkeypatch):
    # Every scaler fit anywhere is recorded, so a scaler fitted on all rows, or on a held-out
    # fold, would show up even if the Pipeline fits looked right.
    features, labels, hosts = made_up_rows()
    scaler_rows = []
    real_fit = StandardScaler.fit

    def recording_fit(self, x, y=None, **kwargs):
        scaler_rows.append(set(x.index))
        return real_fit(self, x, y, **kwargs)

    monkeypatch.setattr(StandardScaler, "fit", recording_fit)

    cross_validate_models(features, labels, hosts)

    positions = fold_positions(labels, hosts)
    assert len(scaler_rows) == len(MODELS) * FOLDS
    for number, rows in enumerate(scaler_rows):
        learn, _ = positions[number % FOLDS]
        assert rows == set(features.index[learn])


def test_each_model_is_scaler_then_model_in_one_pipeline():
    for model in MODELS.values():
        pipe = classifiers.model_pipeline(model)
        assert isinstance(pipe.steps[0][1], StandardScaler)
        assert pipe.steps[1][1] is not model  # a fresh copy each time


def write_inputs(folder):
    """A feature set, a split and a scaler in the training pipeline's layout."""
    features, labels, hosts = made_up_rows()
    frame = pd.DataFrame({"row": range(ROWS)})
    for name in FEATURE_NAMES:
        frame[name] = features[name] if name in features else 1.0
    frame["label"] = labels
    frame["host"] = hosts
    host_number = np.arange(ROWS) // 8
    split = pd.DataFrame({"row": range(ROWS), "set": np.where(host_number % 5 == 4, "test", "train")})
    train = split["set"] == "train"
    paths = {
        "features": folder / "training_features.csv",
        "split": folder / "split.csv",
        "scaler": folder / "scaler.joblib",
        "output": folder / "cv_results.json",
    }
    frame.to_csv(paths["features"], index=False)
    split.to_csv(paths["split"], index=False)
    joblib.dump(StandardScaler().fit(frame.loc[train, list(FEATURE_NAMES)]), paths["scaler"])
    return paths, int(train.sum())


def arguments(paths):
    return [f"--{name}={path}" for name, path in paths.items()]


def test_main_writes_the_results_file_with_the_eight_features(tmp_path, capsys):
    paths, training_rows = write_inputs(tmp_path)

    code = main(arguments(paths))

    assert code == 0
    saved = json.loads(paths["output"].read_text())
    assert saved["features"] == list(FINAL_FEATURES)
    assert saved["folds"] == FOLDS and saved["seed"] == classifiers.SEED
    assert saved["training_rows"] == training_rows
    assert sum(saved["class_balance"].values()) == training_rows
    assert list(saved["models"]) == list(MODELS)
    assert "Saved" in capsys.readouterr().out


def test_main_stops_with_a_message_when_an_input_is_missing(tmp_path, capsys):
    paths, _ = write_inputs(tmp_path)
    paths["split"].unlink()

    code = main(arguments(paths))

    assert code == 1
    assert not paths["output"].exists()
    assert "Training the classifiers stopped:" in capsys.readouterr().err

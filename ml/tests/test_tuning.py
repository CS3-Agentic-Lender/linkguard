"""Tests for the tuning search (ml/training/tuning.py).

They run on small made-up rows, because CI has no dataset. Their numbers say nothing about
the real model.
"""

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from features.hostname import FEATURE_NAMES
from ranking.final_list import FINAL_FEATURES
from training import tuning
from training.classifiers import FOLDS, SEED, fold_positions
from training.tuning import (
    BEFORE,
    C_VALUES,
    L1_RATIOS,
    MEASURES,
    base_model,
    choose,
    combinations,
    main,
    report,
    run_search,
)

ROWS = 400


def made_up_rows(rows: int = ROWS):
    """8 rows per host. HostnameLength follows the label with some overlap, the rest is noise."""
    generator = np.random.default_rng(0)
    host_number = np.arange(rows) // 8
    labels = pd.Series(host_number % 3 == 0, dtype=int, index=range(rows))
    features = pd.DataFrame(index=range(rows))
    for name in FINAL_FEATURES:
        features[name] = generator.integers(0, 10, rows).astype(float)
    features["HostnameLength"] = 10 + 4 * labels + generator.integers(0, 8, rows)
    hosts = pd.Series([f"host{number}.example" for number in host_number], index=range(rows))
    return features, labels, hosts


# Criterion 1: the settings searched are the ones in the search space note.


def test_the_search_tries_the_settings_in_the_note():
    space = tuning.search_space()

    assert space["model__C"] == [0.001, 0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]
    assert space["model__l1_ratio"] == [0.0, 1.0]
    assert set(space) == {"model__C", "model__l1_ratio"}  # class weight and solver are not searched


def test_class_weight_and_solver_stay_fixed():
    model = base_model()

    assert isinstance(model, LogisticRegression)
    assert model.class_weight == "balanced"
    assert model.solver == "liblinear"
    assert model.random_state == SEED


def test_the_before_settings_are_in_the_grid():
    assert BEFORE["C"] in C_VALUES and BEFORE["l1_ratio"] in L1_RATIOS


# Criterion 2: training set only, stratified 5-fold, fixed seed, no held-out row in a fit.


def test_the_search_uses_the_model_comparisons_folds():
    features, labels, hosts = made_up_rows()

    search = run_search(features, labels, hosts, n_jobs=1)

    expected = fold_positions(labels, hosts)
    assert len(search.cv) == FOLDS
    for (learn, held_out), (want_learn, want_out) in zip(search.cv, expected):
        assert list(learn) == list(want_learn) and list(held_out) == list(want_out)


def test_held_out_rows_never_reach_a_fit_and_every_scaler_sees_only_its_fold(monkeypatch):
    features, labels, hosts = made_up_rows()
    fitted_rows, scaler_rows = [], []
    real_pipeline_fit, real_scaler_fit = Pipeline.fit, StandardScaler.fit

    def recording_pipeline_fit(self, x, y=None, **kwargs):
        fitted_rows.append(set(x.index))
        return real_pipeline_fit(self, x, y, **kwargs)

    def recording_scaler_fit(self, x, y=None, **kwargs):
        scaler_rows.append(set(x.index))
        return real_scaler_fit(self, x, y, **kwargs)

    monkeypatch.setattr(Pipeline, "fit", recording_pipeline_fit)
    monkeypatch.setattr(StandardScaler, "fit", recording_scaler_fit)

    run_search(features, labels, hosts, n_jobs=1)

    learning_sets = [set(features.index[learn]) for learn, _ in fold_positions(labels, hosts)]
    combinations_tried = len(C_VALUES) * len(L1_RATIOS)
    assert len(fitted_rows) == combinations_tried * FOLDS  # refit=False: no fit on every row
    assert all(rows in learning_sets for rows in fitted_rows)
    assert all(rows in learning_sets for rows in scaler_rows)


def test_main_passes_only_training_rows_to_the_search(tmp_path, monkeypatch):
    paths, split = write_inputs(tmp_path)
    seen = {}
    real_search = tuning.run_search

    def watching_search(features, labels, hosts, n_jobs=-1):
        seen["rows"] = set(features.index)
        seen["columns"] = list(features.columns)
        return real_search(features, labels, hosts, n_jobs=1)

    monkeypatch.setattr(tuning, "run_search", watching_search)

    assert main(arguments(paths)) == 0

    training_rows = set(split.loc[split["set"] == "train", "row"])
    assert seen["rows"] == training_rows
    assert seen["rows"].isdisjoint(set(split.loc[split["set"] == "test", "row"]))
    assert seen["columns"] == list(FINAL_FEATURES)


def test_a_second_run_gives_the_same_scores():
    features, labels, hosts = made_up_rows()

    first = combinations(run_search(features, labels, hosts, n_jobs=1))
    second = combinations(run_search(features, labels, hosts, n_jobs=1))

    assert first == second


# Criterion 3: before and after scores in one table, in the comparison's layout.


def scored(c, l1_ratio, f2):
    row = {"C": c, "l1_ratio": l1_ratio}
    for measure in MEASURES:
        row[measure] = {"mean": f2 if measure == "f2" else 0.5, "std": 0.01, "folds": [0.5] * FOLDS}
    return row


def test_the_highest_mean_f2_is_chosen():
    rows = [scored(1.0, 0.0, 0.60), scored(10.0, 1.0, 0.70), scored(0.1, 0.0, 0.65)]

    assert choose(rows)["C"] == 10.0


def test_on_a_tie_the_smaller_c_wins():
    rows = [scored(10.0, 0.0, 0.70), scored(0.1, 0.0, 0.70), scored(1.0, 0.0, 0.70)]

    assert choose(rows)["C"] == 0.1


def test_a_tiny_f2_difference_still_decides_and_is_not_rounded_away():
    rows = [scored(0.1, 0.0, 0.7000001), scored(10.0, 0.0, 0.7000004)]

    assert choose(rows)["C"] == 10.0


def test_the_saved_scores_are_rounded_to_six_places():
    rows = tuning.rounded([scored(1.0, 0.0, 0.123456789)])

    assert rows[0]["f2"]["mean"] == 0.123457
    assert rows[0]["C"] == 1.0


def test_every_combination_has_every_measure():
    features, labels, hosts = made_up_rows()

    rows = combinations(run_search(features, labels, hosts, n_jobs=1))

    assert len(rows) == len(C_VALUES) * len(L1_RATIOS)
    for row in rows:
        assert set(MEASURES) <= set(row)
        for measure in MEASURES:
            assert len(row[measure]["folds"]) == FOLDS
            assert 0 <= row[measure]["mean"] <= 1


def test_the_report_has_the_before_and_after_table_in_the_comparison_layout():
    rows = [scored(c, r, 0.6) for c in C_VALUES for r in L1_RATIOS]
    rows[3] = scored(0.01, 1.0, 0.8)
    results = {
        "features": list(FINAL_FEATURES),
        "folds": FOLDS,
        "seed": SEED,
        "training_rows": 100,
        "before": dict(BEFORE),
        "chosen": {"C": 0.01, "l1_ratio": 1.0},
        "combinations": rows,
    }

    text = report(results)

    assert "| Model | Phishing recall | Precision | F1 | ROC-AUC | Accuracy | F2 |" in text
    assert "| Before tuning (C = 1, l2) |" in text
    assert "| After tuning (C = 0.01, l1) |" in text
    assert "not real-world accuracy" in text


# Running it as a command.


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
        "results": folder / "tuning_results.json",
        "report": folder / "tuning.md",
    }
    frame.to_csv(paths["features"], index=False)
    split.to_csv(paths["split"], index=False)
    joblib.dump(StandardScaler().fit(frame.loc[train, list(FEATURE_NAMES)]), paths["scaler"])
    return paths, split


def arguments(paths):
    return [f"--{name}={path}" for name, path in paths.items()]


def test_main_writes_the_results_and_the_report(tmp_path, monkeypatch, capsys):
    paths, split = write_inputs(tmp_path)
    monkeypatch.setattr(
        tuning, "run_search", lambda features, labels, hosts, n_jobs=-1: run_search(features, labels, hosts, n_jobs=1)
    )

    assert main(arguments(paths)) == 0

    saved = json.loads(paths["results"].read_text())
    assert saved["scoring"] == "f2"
    assert saved["seed"] == SEED and saved["folds"] == FOLDS
    assert saved["fixed"]["class_weight"] == "balanced"
    assert saved["training_rows"] == int((split["set"] == "train").sum())
    assert saved["before"] == BEFORE
    assert len(saved["combinations"]) == len(C_VALUES) * len(L1_RATIOS)
    assert paths["report"].read_text().startswith("# Tuning the chosen model")
    assert "Saved" in capsys.readouterr().out


def test_main_stops_with_a_message_when_an_input_is_missing(tmp_path, capsys):
    paths, _ = write_inputs(tmp_path)
    paths["split"].unlink()

    assert main(arguments(paths)) == 1

    assert not paths["results"].exists()
    assert "Tuning stopped:" in capsys.readouterr().err

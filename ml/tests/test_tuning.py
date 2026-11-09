"""Tests for the tuning search (ml/training/tuning.py).

They run on small made-up rows and a small grid, because CI has no dataset and the real grid
takes minutes. Their numbers say nothing about the real model.
"""

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from features.hostname import FEATURE_NAMES
from ranking.final_list import FINAL_FEATURES
from training import tuning
from training.classifiers import FOLDS, SEED, fold_positions
from training.tuning import (
    ALL_COMBINATIONS,
    BEFORE,
    CLOSE,
    MEASURES,
    SEARCH_SPACE,
    base_model,
    choose,
    combinations,
    main,
    report,
    run_search,
)

ROWS = 400
# A two-combination grid with every searched setting, so the tests stay fast.
SMALL_SPACE = {"learning_rate": (0.1, 0.3), "max_iter": (20,), "max_leaf_nodes": (7,), "min_samples_leaf": (5,)}
SMALL_BEFORE = {"learning_rate": 0.1, "max_iter": 20, "max_leaf_nodes": 7, "min_samples_leaf": 5}


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


def small_search(features, labels, hosts, n_jobs=-1):
    return run_search(features, labels, hosts, n_jobs=1, space=SMALL_SPACE)


# Criterion 1: the settings searched are the ones in the search space note.


def test_the_search_tries_the_settings_in_the_note():
    assert SEARCH_SPACE == {
        "learning_rate": (0.05, 0.1, 0.2),
        "max_iter": (100, 300),
        "max_leaf_nodes": (15, 31, 63),
        "min_samples_leaf": (20, 100),
    }
    assert len(ALL_COMBINATIONS) == 36
    assert tuning.search_space() == {f"model__{name}": list(values) for name, values in SEARCH_SPACE.items()}


def test_the_model_is_gradient_boosting_with_the_comparisons_fixed_settings():
    model = base_model()

    assert isinstance(model, HistGradientBoostingClassifier)
    assert model.random_state == SEED
    assert model.early_stopping == "auto"
    assert model.class_weight is None


def test_the_before_settings_are_scikit_learns_defaults_and_in_the_grid():
    defaults = HistGradientBoostingClassifier().get_params()

    assert all(defaults[name] == value for name, value in BEFORE.items())
    assert BEFORE in ALL_COMBINATIONS


def test_the_scoring_measure_is_roc_auc():
    assert tuning.SCORING_MEASURE == "roc_auc"


# Criterion 2: training set only, stratified 5-fold, fixed seed, no held-out row in a fit.


def test_the_search_uses_the_model_comparisons_folds():
    features, labels, hosts = made_up_rows()

    search = small_search(features, labels, hosts)

    for (learn, held_out), (want_learn, want_out) in zip(search.cv, fold_positions(labels, hosts)):
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

    small_search(features, labels, hosts)

    learning_sets = [set(features.index[learn]) for learn, _ in fold_positions(labels, hosts)]
    assert len(fitted_rows) == 2 * FOLDS  # refit=False: no fit on every row
    assert all(rows in learning_sets for rows in fitted_rows)
    assert all(rows in learning_sets for rows in scaler_rows)


def test_main_passes_only_training_rows_to_the_search(tmp_path, monkeypatch):
    paths, split = write_inputs(tmp_path)
    seen = {}

    def watching_search(features, labels, hosts, n_jobs=-1):
        seen["rows"] = set(features.index)
        seen["columns"] = list(features.columns)
        return small_search(features, labels, hosts)

    monkeypatch.setattr(tuning, "run_search", watching_search)
    monkeypatch.setattr(tuning, "BEFORE", SMALL_BEFORE)

    assert main(arguments(paths)) == 0

    assert seen["rows"] == set(split.loc[split["set"] == "train", "row"])
    assert seen["rows"].isdisjoint(set(split.loc[split["set"] == "test", "row"]))
    assert seen["columns"] == list(FINAL_FEATURES)


def test_a_second_run_gives_the_same_scores():
    features, labels, hosts = made_up_rows()

    assert combinations(small_search(features, labels, hosts)) == combinations(small_search(features, labels, hosts))


# Criterion 3: before and after scores in one table, in the comparison's layout.


def scored(roc_auc, learning_rate=0.1, max_iter=100, max_leaf_nodes=31, min_samples_leaf=20):
    row = {
        "learning_rate": learning_rate,
        "max_iter": max_iter,
        "max_leaf_nodes": max_leaf_nodes,
        "min_samples_leaf": min_samples_leaf,
    }
    for measure in MEASURES:
        row[measure] = {"mean": roc_auc if measure == "roc_auc" else 0.5, "std": 0.01, "folds": [0.5] * FOLDS}
    return row


def test_the_highest_mean_roc_auc_is_chosen_when_it_is_clearly_best():
    rows = [scored(0.80), scored(0.85, max_leaf_nodes=63), scored(0.82, max_leaf_nodes=15)]

    assert choose(rows)["max_leaf_nodes"] == 63


def test_within_close_of_the_best_the_simplest_wins():
    rows = [
        scored(0.8400, max_leaf_nodes=63, max_iter=300),
        scored(0.8400 - CLOSE / 2, max_leaf_nodes=15, max_iter=300),
        scored(0.8400 - CLOSE / 2, max_leaf_nodes=15, max_iter=100),
        scored(0.8400 - 2 * CLOSE, max_leaf_nodes=15, max_iter=100, min_samples_leaf=100),
    ]

    chosen = choose(rows)

    assert (chosen["max_leaf_nodes"], chosen["max_iter"], chosen["min_samples_leaf"]) == (15, 100, 20)


def test_a_gap_just_over_close_is_not_a_tie():
    rows = [scored(0.8400, max_leaf_nodes=63), scored(0.8400 - CLOSE - 0.0001, max_leaf_nodes=15)]

    assert choose(rows)["max_leaf_nodes"] == 63


def test_the_saved_scores_are_rounded_to_six_places():
    rows = tuning.rounded([scored(0.123456789)])

    assert rows[0]["roc_auc"]["mean"] == 0.123457
    assert rows[0]["max_leaf_nodes"] == 31


def test_every_combination_has_every_measure_and_its_settings():
    features, labels, hosts = made_up_rows()

    rows = combinations(small_search(features, labels, hosts))

    assert len(rows) == 2
    for row in rows:
        assert set(SEARCH_SPACE) <= set(row)
        for measure in MEASURES:
            assert len(row[measure]["folds"]) == FOLDS
            assert 0 <= row[measure]["mean"] <= 1


def test_the_report_has_the_before_and_after_table_in_the_comparison_layout():
    rows = [scored(0.80), scored(0.84, max_leaf_nodes=15)]
    results = {
        "features": list(FINAL_FEATURES),
        "folds": FOLDS,
        "seed": SEED,
        "training_rows": 100,
        "before": dict(BEFORE),
        "chosen": {"learning_rate": 0.1, "max_iter": 100, "max_leaf_nodes": 15, "min_samples_leaf": 20},
        "combinations": rows,
    }

    text = report(results)

    assert "| Model | Phishing recall | Precision | F1 | ROC-AUC | Accuracy | F2 |" in text
    assert "| Before tuning (learning rate 0.1, up to 100 trees, 31 leaves, min leaf 20) |" in text
    assert "| After tuning (learning rate 0.1, up to 100 trees, 15 leaves, min leaf 20) |" in text
    assert "Mean ROC-AUC changed by +0.040" in text
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
    monkeypatch.setattr(tuning, "run_search", small_search)
    monkeypatch.setattr(tuning, "BEFORE", SMALL_BEFORE)

    assert main(arguments(paths)) == 0

    saved = json.loads(paths["results"].read_text())
    assert saved["model"] == "HistGradientBoostingClassifier"
    assert saved["scoring"] == "roc_auc"
    assert saved["seed"] == SEED and saved["folds"] == FOLDS
    assert saved["training_rows"] == int((split["set"] == "train").sum())
    assert saved["before"] == SMALL_BEFORE
    assert set(saved["chosen"]) == set(SEARCH_SPACE)
    assert len(saved["combinations"]) == 2
    assert paths["report"].read_text().startswith("# Tuning the chosen model")
    assert "Saved" in capsys.readouterr().out


def test_main_stops_with_a_message_when_an_input_is_missing(tmp_path, capsys):
    paths, _ = write_inputs(tmp_path)
    paths["split"].unlink()

    assert main(arguments(paths)) == 1

    assert not paths["results"].exists()
    assert "Tuning stopped:" in capsys.readouterr().err

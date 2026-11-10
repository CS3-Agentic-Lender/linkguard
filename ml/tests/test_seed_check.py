"""Tests for the seed check (ml/training/seed_check.py), on small made-up rows."""

import json

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from features.hostname import FEATURE_NAMES
from ranking.final_list import FINAL_FEATURES
from training.classifiers import FOLDS
from training.seed_check import (
    SEEDS,
    SeedCheckError,
    check,
    main,
    report,
    seed_folds,
    summary,
    tuned_settings,
)

ROWS = 400
BEFORE = {"learning_rate": 0.1, "max_iter": 20, "max_leaf_nodes": 7, "min_samples_leaf": 5}
AFTER = {"learning_rate": 0.3, "max_iter": 20, "max_leaf_nodes": 7, "min_samples_leaf": 5}


def made_up_rows():
    generator = np.random.default_rng(0)
    host_number = np.arange(ROWS) // 8
    labels = pd.Series(host_number % 3 == 0, dtype=int, index=range(ROWS))
    features = pd.DataFrame(index=range(ROWS))
    for name in FINAL_FEATURES:
        features[name] = generator.integers(0, 10, ROWS).astype(float)
    features["HostnameLength"] = 10 + 4 * labels + generator.integers(0, 8, ROWS)
    hosts = pd.Series([f"host{number}.example" for number in host_number], index=range(ROWS))
    return features, labels, hosts


def test_it_uses_five_seeds():
    assert SEEDS == (0, 1, 2, 3, 4)


def test_each_seed_makes_its_own_host_grouped_split():
    _, labels, hosts = made_up_rows()

    splits = [seed_folds(labels, hosts, seed) for seed in (0, 1)]

    for folds in splits:
        assert len(folds) == FOLDS
        for learn, held_out in folds:
            assert set(hosts.iloc[learn]).isdisjoint(hosts.iloc[held_out])
    assert any(list(a[1]) != list(b[1]) for a, b in zip(*splits))


def test_held_out_rows_never_reach_a_fit(monkeypatch):
    features, labels, hosts = made_up_rows()
    fitted = []
    real_fit = Pipeline.fit

    def recording_fit(self, x, y=None, **kwargs):
        fitted.append(set(x.index))
        return real_fit(self, x, y, **kwargs)

    monkeypatch.setattr(Pipeline, "fit", recording_fit)

    check(features, labels, hosts, BEFORE, AFTER, seeds=(0, 1))

    learning = [set(features.index[learn]) for seed in (0, 1) for learn, _ in seed_folds(labels, hosts, seed)]
    assert len(fitted) == 2 * 2 * FOLDS
    assert all(rows in learning for rows in fitted)


def test_every_seed_gets_before_after_and_their_difference():
    features, labels, hosts = made_up_rows()

    rows = check(features, labels, hosts, BEFORE, AFTER, seeds=(0, 1))

    assert [row["seed"] for row in rows] == [0, 1]
    for row in rows:
        assert 0 <= row["before"] <= 1 and 0 <= row["after"] <= 1
        assert row["difference"] == pytest.approx(row["after"] - row["before"], abs=2e-6)


def test_a_second_run_gives_the_same_numbers():
    features, labels, hosts = made_up_rows()

    assert check(features, labels, hosts, BEFORE, AFTER, seeds=(0,)) == check(
        features, labels, hosts, BEFORE, AFTER, seeds=(0,)
    )


def test_a_second_run_is_the_same_with_early_stopping_switched_on(monkeypatch):
    # The real data is big enough to switch early stopping on; the made-up rows are not, so force it.
    import training.seed_check as seed_check
    from sklearn.ensemble import HistGradientBoostingClassifier

    monkeypatch.setattr(seed_check, "base_model", lambda: HistGradientBoostingClassifier(early_stopping=True))
    features, labels, hosts = made_up_rows()

    first = check(features, labels, hosts, BEFORE, AFTER, seeds=(3,))
    second = check(features, labels, hosts, BEFORE, AFTER, seeds=(3,))

    assert first == second


def test_summary_counts_wins_and_spread():
    rows = [{"difference": d} for d in (0.002, 0.001, -0.001, 0.003, 0.0)]

    totals = summary(rows)

    assert totals["after_wins"] == 3 and totals["seeds"] == 5
    assert totals["mean_difference"] == pytest.approx(0.001)
    assert totals["smallest_difference"] == -0.001 and totals["largest_difference"] == 0.003


def test_the_report_says_how_many_seeds_after_wins():
    rows = [{"seed": 0, "before": 0.83, "after": 0.84, "difference": 0.01}]
    result = {"seeds": rows, "summary": summary(rows), "before": BEFORE, "after": AFTER, "training_rows": 100}

    text = report(result)

    assert "| 0 | 0.8300 | 0.8400 | +0.0100 |" in text
    assert "After beats before on 1 of 1 seeds" in text
    assert "never picks a seed" in text


def test_the_report_says_when_the_gain_is_within_the_noise():
    rows = [
        {"seed": 0, "before": 0.83, "after": 0.8302, "difference": 0.0002},
        {"seed": 1, "before": 0.83, "after": 0.8297, "difference": -0.0003},
    ]
    result = {"seeds": rows, "summary": summary(rows), "before": BEFORE, "after": AFTER, "training_rows": 100}

    assert "no consistent improvement across these five seeds" in report(result)


def test_the_report_says_so_when_tuning_kept_the_defaults():
    rows = [{"seed": 0, "before": 0.83, "after": 0.83, "difference": 0.0}]
    result = {"seeds": rows, "summary": summary(rows), "before": BEFORE, "after": BEFORE, "training_rows": 100}

    assert "kept the default settings" in report(result)


def test_tuned_settings_stops_cleanly_on_a_missing_or_broken_file(tmp_path):
    with pytest.raises(SeedCheckError, match="not found"):
        tuned_settings(tmp_path / "missing.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    with pytest.raises(SeedCheckError, match="could not be read"):
        tuned_settings(broken)


def write_inputs(folder):
    features, labels, hosts = made_up_rows()
    frame = pd.DataFrame({"row": range(ROWS)})
    for name in FEATURE_NAMES:
        frame[name] = features[name] if name in features else 1.0
    frame["label"] = labels
    frame["host"] = hosts
    split = pd.DataFrame({"row": range(ROWS), "set": np.where((np.arange(ROWS) // 8) % 5 == 4, "test", "train")})
    train = split["set"] == "train"
    paths = {
        "features": folder / "training_features.csv",
        "split": folder / "split.csv",
        "scaler": folder / "scaler.joblib",
        "results": folder / "tuning_results.json",
        "output": folder / "seed_check.json",
        "report": folder / "seed_check.md",
    }
    frame.to_csv(paths["features"], index=False)
    split.to_csv(paths["split"], index=False)
    joblib.dump(StandardScaler().fit(frame.loc[train, list(FEATURE_NAMES)]), paths["scaler"])
    paths["results"].write_text(json.dumps({"before": BEFORE, "chosen": AFTER}))
    return paths, split


def test_main_checks_only_training_rows_and_saves_both_files(tmp_path, monkeypatch, capsys):
    paths, split = write_inputs(tmp_path)
    seen = {}
    import training.seed_check as seed_check

    real_check = seed_check.check

    def watching_check(features, labels, hosts, before, after, seeds=SEEDS):
        seen["rows"] = set(features.index)
        return real_check(features, labels, hosts, before, after, seeds=(0, 1))

    monkeypatch.setattr(seed_check, "check", watching_check)

    assert main([f"--{name}={path}" for name, path in paths.items()]) == 0

    assert seen["rows"] == set(split.loc[split["set"] == "train", "row"])
    saved = json.loads(paths["output"].read_text())
    assert len(saved["seeds"]) == 2 and saved["before"] == BEFORE and saved["after"] == AFTER
    assert paths["report"].read_text().startswith("# Seed check")
    assert "Saved" in capsys.readouterr().out

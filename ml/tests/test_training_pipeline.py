"""Tests for the training pipeline, on a small made-up sample.

CI has no dataset, so each test writes its own tiny feature set, split and scaler to a
temporary folder. The sample stands in for the files the earlier stories save; its
numbers are made up and say nothing about how a real model does.

Test rows hold a marker text instead of numbers. If the pipeline ever read a test row,
its feature columns would stop being numeric and the run would fail.
"""

import ast
import subprocess
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.preprocessing import StandardScaler

from cleaning.labels import LABEL_COLUMN
from features.hostname import FEATURE_NAMES
from leakage.excluded import EXCLUDED_FEATURES
from training import pipeline
from training.pipeline import (
    HOSTNAME_COLUMN,
    ROW_COLUMN,
    PipelineError,
    TrainingSet,
    class_counts,
    hand_to_classifiers,
    load_training_set,
    main,
)

ML_DIR = Path(__file__).resolve().parent.parent
TEST_ROW_MARKER = "TEST ROW - MUST NEVER BE READ"
N_ROWS = 20
TEST_ROWS = (2, 5, 11, 17)
TRAIN_ROWS = tuple(row for row in range(N_ROWS) if row not in TEST_ROWS)


def made_up_features(n_rows: int = N_ROWS) -> pd.DataFrame:
    """A made-up feature set in the feature set step's layout: row, ten features, label, hostname.

    Values follow a fixed pattern, not real links.
    """
    rng = np.random.default_rng(0)
    frame = pd.DataFrame({ROW_COLUMN: range(n_rows)})
    for name in FEATURE_NAMES:
        frame[name] = rng.integers(0, 30, size=n_rows)
    for ratio in ("LetterRatioInHostname", "DigitRatioInHostname", "SpecialCharRatioInHostname"):
        frame[ratio] = rng.random(n_rows)
    frame[LABEL_COLUMN] = [1 if row % 3 == 0 else 0 for row in range(n_rows)]
    frame[HOSTNAME_COLUMN] = [f"host{row // 2}.example" for row in range(n_rows)]
    return frame


def write_artifacts(folder: Path, frame: pd.DataFrame | None = None, split: pd.DataFrame | None = None):
    """Write a feature set, a split and a scaler fitted on the training rows only.

    Returns the three paths and the clean feature frame (before test rows were masked).
    """
    frame = made_up_features() if frame is None else frame
    if split is None:
        split = pd.DataFrame(
            {"row": range(len(frame)), "set": ["test" if row in TEST_ROWS else "train" for row in range(len(frame))]}
        )
    train_rows = split.loc[split["set"] == "train", "row"].to_numpy()

    # The split-and-scale step's job, done here only to make the fixture.
    scaler = StandardScaler().fit(frame.loc[train_rows, list(FEATURE_NAMES)])

    on_disk = frame.astype(object).copy()
    test_rows = split.loc[split["set"] == "test", "row"].to_numpy()
    on_disk.loc[test_rows, list(FEATURE_NAMES)] = TEST_ROW_MARKER

    paths = {
        "features": folder / "training_features.csv",
        "split": folder / "split.csv",
        "scaler": folder / "scaler.joblib",
    }
    on_disk.to_csv(paths["features"], index=False)
    split.to_csv(paths["split"], index=False)
    joblib.dump(scaler, paths["scaler"])
    return paths, frame


def load(paths) -> TrainingSet:
    return load_training_set(paths["features"], paths["split"], paths["scaler"])


@pytest.fixture
def artifacts(tmp_path):
    return write_artifacts(tmp_path)


# Criterion 1: one command runs the script from start to finish.


def test_one_command_runs_the_pipeline_end_to_end(artifacts):
    paths, _ = artifacts
    result = subprocess.run(
        [
            sys.executable, "-m", "training.pipeline",
            "--features", str(paths["features"]),
            "--split", str(paths["split"]),
            "--scaler", str(paths["scaler"]),
        ],
        cwd=ML_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert f"Training rows from the saved split: {len(TRAIN_ROWS)}" in result.stdout


def test_the_command_stops_with_a_clear_message_when_a_file_is_missing(artifacts, capsys):
    paths, _ = artifacts
    paths["split"].unlink()
    code = main(["--features", str(paths["features"]), "--split", str(paths["split"]), "--scaler", str(paths["scaler"])])
    assert code == 1
    assert "saved train/test split was not found" in capsys.readouterr().err


def test_default_paths_point_at_gitignored_places():
    assert pipeline.FEATURES_PATH.parent == ML_DIR / "data"
    assert pipeline.SPLIT_PATH.parent == ML_DIR / "data"
    assert pipeline.SCALER_PATH == ML_DIR / "models" / "scaler.joblib"
    result = subprocess.run(
        ["git", "check-ignore", str(pipeline.FEATURES_PATH), str(pipeline.SPLIT_PATH), str(pipeline.SCALER_PATH)],
        cwd=ML_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    assert len(result.stdout.split()) == 3


# Criterion 2: the training rows are exactly the saved split's; no new split, no scaler fit.


def test_training_rows_are_exactly_the_saved_training_rows(artifacts):
    paths, frame = artifacts
    training_set = load(paths)
    assert training_set.rows.tolist() == list(TRAIN_ROWS)
    assert training_set.features.index.tolist() == list(TRAIN_ROWS)
    pd.testing.assert_frame_equal(
        training_set.features.reset_index(drop=True),
        frame.loc[list(TRAIN_ROWS), list(FEATURE_NAMES)].reset_index(drop=True),
        check_dtype=False,
    )
    assert training_set.labels.tolist() == frame.loc[list(TRAIN_ROWS), LABEL_COLUMN].tolist()


def test_scaled_rows_are_the_saved_scaler_transform_and_the_scaler_is_unchanged(artifacts):
    paths, frame = artifacts
    saved = joblib.load(paths["scaler"])
    training_set = load(paths)
    expected = saved.transform(frame.loc[list(TRAIN_ROWS), list(FEATURE_NAMES)])
    np.testing.assert_array_equal(training_set.scaled, expected)
    reloaded = joblib.load(paths["scaler"])
    np.testing.assert_array_equal(reloaded.mean_, saved.mean_)
    np.testing.assert_array_equal(reloaded.scale_, saved.scale_)


def test_a_run_never_fits_a_scaler_or_makes_a_split(artifacts, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("the pipeline must not fit a scaler or split the data")

    for method in ("fit", "fit_transform", "partial_fit"):
        monkeypatch.setattr(StandardScaler, method, forbidden)
    import sklearn.model_selection as model_selection

    monkeypatch.setattr(model_selection, "train_test_split", forbidden)
    paths, _ = artifacts
    load(paths)


def test_the_code_has_no_split_or_scaler_fit():
    source = Path(pipeline.__file__).read_text()
    for banned in ("train_test_split", "ShuffleSplit", "GroupKFold", "StratifiedKFold", "Scaler(", "fit_transform", "partial_fit"):
        assert banned not in source, banned

    # The only .fit call is the one that hands the scaled training rows to each classifier.
    tree = ast.parse(source)
    fit_calls = []
    for function in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
        for node in ast.walk(function):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "fit":
                fit_calls.append(function.name)
    assert fit_calls == ["hand_to_classifiers"]


def test_every_classifier_gets_the_same_scaled_training_rows(artifacts):
    class Recorder(ClassifierMixin, BaseEstimator):
        def fit(self, X, y):
            self.seen_X_ = np.array(X)
            self.seen_y_ = np.array(y)
            return self

    paths, _ = artifacts
    training_set = load(paths)
    fitted = hand_to_classifiers({"first": Recorder(), "second": Recorder()}, training_set)
    assert set(fitted) == {"first", "second"}
    for model in fitted.values():
        np.testing.assert_array_equal(model.seen_X_, training_set.scaled)
        np.testing.assert_array_equal(model.seen_y_, training_set.labels.to_numpy())


def test_hand_to_classifiers_does_not_change_the_given_classifiers(artifacts):
    from sklearn.dummy import DummyClassifier

    paths, _ = artifacts
    given = DummyClassifier(strategy="most_frequent")
    fitted = hand_to_classifiers({"baseline": given}, load(paths))
    assert not hasattr(given, "classes_")
    assert fitted["baseline"] is not given


# Criterion 3: the test rows are never loaded or used.


def test_test_rows_are_never_loaded(artifacts):
    paths, _ = artifacts
    training_set = load(paths)
    assert not set(TEST_ROWS) & set(training_set.rows.tolist())
    assert not set(TEST_ROWS) & set(training_set.features.index)
    assert not set(TEST_ROWS) & set(training_set.labels.index)
    assert not set(TEST_ROWS) & set(training_set.hostnames.index)
    assert len(training_set.scaled) == len(TRAIN_ROWS)


def test_test_row_text_never_reaches_the_features(artifacts):
    paths, _ = artifacts
    # The file really holds the marker on the test rows ...
    assert TEST_ROW_MARKER in paths["features"].read_text()
    training_set = load(paths)
    # ... and none of it was read: every feature column came back numeric.
    for name in FEATURE_NAMES:
        assert pd.api.types.is_numeric_dtype(training_set.features[name])


def test_a_split_with_only_test_rows_stops(tmp_path):
    paths, _ = write_artifacts(tmp_path)
    pd.DataFrame({"row": range(N_ROWS), "set": ["test"] * N_ROWS}).to_csv(paths["split"], index=False)
    with pytest.raises(PipelineError, match="no training rows"):
        load(paths)


# Criterion 4: any excluded column in the feature matrix stops the run.


@pytest.mark.parametrize("column", sorted(EXCLUDED_FEATURES))
def test_an_excluded_column_in_the_feature_matrix_stops_the_run(tmp_path, column):
    frame = made_up_features()
    frame.insert(3, column, 1)
    paths, _ = write_artifacts(tmp_path)
    frame.to_csv(paths["features"], index=False)
    with pytest.raises(PipelineError, match=f"Excluded columns.*{column}"):
        load(paths)


def test_the_hostname_is_kept_for_grouping_but_is_not_a_feature(artifacts):
    paths, frame = artifacts
    training_set = load(paths)
    assert HOSTNAME_COLUMN not in training_set.features.columns
    assert training_set.scaled.shape[1] == len(FEATURE_NAMES)
    assert training_set.hostnames.tolist() == frame.loc[list(TRAIN_ROWS), HOSTNAME_COLUMN].tolist()


def test_a_missing_feature_stops_the_run(tmp_path):
    paths, frame = write_artifacts(tmp_path)
    frame.drop(columns="TLDLength").to_csv(paths["features"], index=False)
    with pytest.raises(PipelineError, match="Missing: \\['TLDLength'\\]"):
        load(paths)


def test_an_unexpected_extra_column_stops_the_run(tmp_path):
    paths, frame = write_artifacts(tmp_path)
    frame.assign(URLLength=5).to_csv(paths["features"], index=False)
    with pytest.raises(PipelineError, match="Not expected: \\['URLLength'\\]"):
        load(paths)


def test_features_in_the_wrong_order_stop_the_run(tmp_path):
    paths, frame = write_artifacts(tmp_path)
    swapped = list(FEATURE_NAMES)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    frame[[ROW_COLUMN] + swapped + [LABEL_COLUMN, HOSTNAME_COLUMN]].to_csv(paths["features"], index=False)
    with pytest.raises(PipelineError, match="wrong order"):
        load(paths)


@pytest.mark.parametrize("column", [ROW_COLUMN, LABEL_COLUMN, HOSTNAME_COLUMN])
def test_a_missing_row_label_or_host_column_stops_the_run(tmp_path, column):
    paths, frame = write_artifacts(tmp_path)
    frame.drop(columns=column).to_csv(paths["features"], index=False)
    with pytest.raises(PipelineError, match=f"no '{column}' column"):
        load(paths)


def test_the_row_number_is_not_a_feature(artifacts):
    paths, _ = artifacts
    training_set = load(paths)
    assert ROW_COLUMN not in training_set.features.columns
    assert training_set.features.index.name == ROW_COLUMN


def test_a_feature_set_out_of_step_with_the_split_stops_the_run(tmp_path):
    # As if the feature set had lost row 3: every later line moves up by one, but the
    # file still has enough lines for the row count check to pass.
    paths, frame = write_artifacts(tmp_path)
    shifted = frame.drop(index=3).reset_index(drop=True)
    shifted = pd.concat([shifted, frame.tail(1)], ignore_index=True)
    shifted.to_csv(paths["features"], index=False)
    with pytest.raises(PipelineError, match="out of step with the split: the line where row 3 should be holds row 4"):
        load(paths)


def test_non_whole_row_numbers_in_the_feature_set_stop_the_run(tmp_path):
    paths, frame = write_artifacts(tmp_path)
    frame[ROW_COLUMN] = frame[ROW_COLUMN] + 0.5
    frame.to_csv(paths["features"], index=False)
    with pytest.raises(PipelineError, match="row numbers must all be whole numbers"):
        load(paths)


# Criterion 5: the class counts are printed and show phishing as label 1.


def test_the_class_counts_are_printed_with_phishing_as_label_1(artifacts, capsys):
    paths, frame = artifacts
    code = main(["--features", str(paths["features"]), "--split", str(paths["split"]), "--scaler", str(paths["scaler"])])
    assert code == 0
    out = capsys.readouterr().out
    train_labels = frame.loc[list(TRAIN_ROWS), LABEL_COLUMN]
    assert f"label 1 = phishing: {(train_labels == 1).sum()}" in out
    assert f"label 0 = legitimate: {(train_labels == 0).sum()}" in out


def test_class_counts_put_phishing_first():
    assert class_counts(pd.Series([0, 1, 1, 0, 0])) == {1: 2, 0: 3}


# Bad values in the training rows.


def test_a_non_numeric_feature_value_stops_the_run(tmp_path):
    paths, frame = write_artifacts(tmp_path)
    broken = frame.astype(object)
    broken.loc[TRAIN_ROWS[0], "HostnameLength"] = "twelve"
    broken.to_csv(paths["features"], index=False)
    with pytest.raises(PipelineError, match="'HostnameLength' must be numbers only"):
        load(paths)


def test_a_blank_feature_value_stops_the_run(tmp_path):
    paths, frame = write_artifacts(tmp_path)
    broken = frame.astype(object)
    broken.loc[TRAIN_ROWS[0], "TLDLength"] = ""
    broken.to_csv(paths["features"], index=False)
    with pytest.raises(PipelineError, match="'TLDLength'"):
        load(paths)


def test_an_infinite_feature_value_stops_the_run(tmp_path):
    paths, frame = write_artifacts(tmp_path)
    frame.loc[TRAIN_ROWS[0], "DigitRatioInHostname"] = np.inf
    frame.to_csv(paths["features"], index=False)
    with pytest.raises(PipelineError, match="missing or infinite"):
        load(paths)


@pytest.mark.parametrize("bad_label", [2, -1])
def test_a_label_other_than_0_or_1_stops_the_run(tmp_path, bad_label):
    paths, frame = write_artifacts(tmp_path)
    frame.loc[TRAIN_ROWS[0], LABEL_COLUMN] = bad_label
    frame.to_csv(paths["features"], index=False)
    with pytest.raises(PipelineError, match="label must be 1"):
        load(paths)


# Problems with the saved split.


def test_a_split_with_unknown_set_names_stops(tmp_path):
    split = pd.DataFrame({"row": range(N_ROWS), "set": ["train"] * (N_ROWS - 1) + ["validation"]})
    paths, _ = write_artifacts(tmp_path, split=split)
    with pytest.raises(PipelineError, match="validation"):
        load(paths)


def test_a_split_with_wrong_columns_stops(tmp_path):
    paths, _ = write_artifacts(tmp_path)
    pd.DataFrame({"index": range(N_ROWS), "fold": ["train"] * N_ROWS}).to_csv(paths["split"], index=False)
    with pytest.raises(PipelineError, match="must have the columns"):
        load(paths)


def test_a_split_naming_a_row_twice_stops(tmp_path):
    paths, _ = write_artifacts(tmp_path)
    pd.DataFrame({"row": [0, 0, 1], "set": ["train", "train", "test"]}).to_csv(paths["split"], index=False)
    with pytest.raises(PipelineError, match="more than once"):
        load(paths)


def test_a_split_with_a_negative_row_stops(tmp_path):
    paths, _ = write_artifacts(tmp_path)
    pd.DataFrame({"row": [-1, 0], "set": ["train", "train"]}).to_csv(paths["split"], index=False)
    with pytest.raises(PipelineError, match="negative"):
        load(paths)


def test_a_split_with_non_whole_row_numbers_stops(tmp_path):
    paths, _ = write_artifacts(tmp_path)
    pd.DataFrame({"row": [0.5, 1.0], "set": ["train", "train"]}).to_csv(paths["split"], index=False)
    with pytest.raises(PipelineError, match="whole numbers"):
        load(paths)


def test_a_split_naming_rows_the_feature_set_does_not_have_stops(tmp_path):
    paths, _ = write_artifacts(tmp_path)
    pd.DataFrame({"row": [0, 1, N_ROWS + 5], "set": ["train"] * 3}).to_csv(paths["split"], index=False)
    with pytest.raises(PipelineError, match="only has 2 of them"):
        load(paths)


# Problems with the saved scaler.


@pytest.mark.parametrize("which", ["features", "split", "scaler"])
def test_each_missing_file_is_named(tmp_path, which):
    paths, _ = write_artifacts(tmp_path)
    paths[which].unlink()
    with pytest.raises(PipelineError, match="was not found"):
        load(paths)


def test_an_unfitted_scaler_stops(tmp_path):
    paths, _ = write_artifacts(tmp_path)
    joblib.dump(StandardScaler(), paths["scaler"])
    with pytest.raises(PipelineError, match="not been fitted"):
        load(paths)


def test_a_file_that_is_not_a_scaler_stops(tmp_path):
    paths, _ = write_artifacts(tmp_path)
    joblib.dump({"mean": 0}, paths["scaler"])
    with pytest.raises(PipelineError, match="not a scaler"):
        load(paths)


def test_a_scaler_fitted_on_another_number_of_features_stops(tmp_path):
    paths, frame = write_artifacts(tmp_path)
    joblib.dump(StandardScaler().fit(frame[list(FEATURE_NAMES[:4])]), paths["scaler"])
    with pytest.raises(PipelineError, match="fitted on 4 features"):
        load(paths)


def test_a_scaler_fitted_on_features_in_another_order_stops(tmp_path):
    paths, frame = write_artifacts(tmp_path)
    reordered = list(reversed(FEATURE_NAMES))
    joblib.dump(StandardScaler().fit(frame[reordered]), paths["scaler"])
    with pytest.raises(PipelineError, match="different order"):
        load(paths)


# Determinism.


def test_two_runs_give_identical_results(artifacts):
    paths, _ = artifacts
    first, second = load(paths), load(paths)
    np.testing.assert_array_equal(first.rows, second.rows)
    np.testing.assert_array_equal(first.scaled, second.scaled)
    pd.testing.assert_series_equal(first.labels, second.labels)

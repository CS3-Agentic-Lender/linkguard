import pandas as pd
import pytest

from features.hostname import FEATURE_NAMES
from splitting.split import SPLIT_CHECK_NAME, save_split
from ranking.training_split import (
    FEATURES_CSV_NAME,
    SPLIT_CSV_NAME,
    TrainingSplitError,
    load_inputs,
    training_split,
)


def feature_set(rows: list[int]) -> pd.DataFrame:
    """Made-up feature set rows: each feature is the row number, labels alternate."""
    frame = pd.DataFrame({"row": rows})
    for name in FEATURE_NAMES:
        frame[name] = [float(row) for row in rows]
    frame["label"] = [row % 2 for row in rows]
    frame["host"] = [f"host{row}.example" for row in rows]
    return frame


SPLIT = pd.DataFrame({"row": [0, 1, 2, 3, 4], "set": ["train", "test", "train", "test", "train"]})


def save_inputs(folder, features, split=SPLIT):
    """Write the feature set, and the split with its check file the way the split step saves them."""
    features.to_csv(folder / FEATURES_CSV_NAME, index=False)
    save_split(split.set_index("row")["set"], features.set_index("row")["host"], folder / SPLIT_CSV_NAME)


def test_keeps_only_the_training_rows_in_row_order():
    # The feature set is shuffled on purpose: rows are matched by number, not position.
    training = training_split(feature_set([4, 3, 2, 1, 0]), SPLIT)

    assert training["row"].tolist() == [0, 2, 4]
    assert list(training.columns) == ["row", *FEATURE_NAMES, "label"]


def test_test_rows_never_come_through():
    training = training_split(feature_set([0, 1, 2, 3, 4]), SPLIT)

    test_rows = set(SPLIT.loc[SPLIT["set"] == "test", "row"])
    assert test_rows.isdisjoint(training["row"])


def test_a_training_row_missing_from_the_feature_set_stops_the_run():
    with pytest.raises(TrainingSplitError, match="1 training rows are not in the feature set, for example row 2"):
        training_split(feature_set([0, 1, 3, 4]), SPLIT)


def test_a_missing_test_row_does_not_matter():
    training = training_split(feature_set([0, 2, 4]), SPLIT)

    assert training["row"].tolist() == [0, 2, 4]


@pytest.mark.parametrize(
    ("features", "split", "message"),
    [
        (feature_set([0, 1, 2, 3, 4]).drop(columns="label"), SPLIT, "feature set is missing the columns"),
        (feature_set([0, 1, 2, 3, 4]), SPLIT.drop(columns="set"), "split is missing the columns"),
        (feature_set([0, 1, 2, 3, 4]), SPLIT.replace("test", "holdout"), "set names other than"),
        (feature_set([0, 1, 2, 3, 4]), pd.concat([SPLIT, SPLIT.head(1)]), "split lists the same row"),
        (feature_set([0, 0, 1, 2, 3, 4]), SPLIT, "feature set lists the same row"),
        (feature_set([0, 1, 2, 3, 4]), SPLIT.replace("train", "test"), "no training rows"),
    ],
)
def test_a_broken_input_stops_with_a_plain_message(features, split, message):
    with pytest.raises(TrainingSplitError, match=message):
        training_split(features, split)


def test_a_missing_value_in_a_training_row_stops_the_run():
    features = feature_set([0, 1, 2, 3, 4])
    features.loc[features["row"] == 2, FEATURE_NAMES[0]] = float("nan")

    with pytest.raises(TrainingSplitError, match="missing values"):
        training_split(features, SPLIT)


def test_loads_both_files_from_the_data_folder(tmp_path):
    save_inputs(tmp_path, feature_set([0, 1, 2, 3, 4]))

    features, split = load_inputs(tmp_path)

    assert training_split(features, split)["row"].tolist() == [0, 2, 4]


@pytest.mark.parametrize(("present", "absent", "hint"), [
    (SPLIT_CSV_NAME, FEATURES_CSV_NAME, "featureset.build"),
    (FEATURES_CSV_NAME, SPLIT_CSV_NAME, "splitting.build"),
])
def test_a_missing_file_names_the_step_that_makes_it(tmp_path, present, absent, hint):
    (tmp_path / present).touch()

    with pytest.raises(TrainingSplitError, match=f"{absent} was not found.*{hint}"):
        load_inputs(tmp_path)


@pytest.mark.parametrize("broken", [FEATURES_CSV_NAME, SPLIT_CSV_NAME])
def test_an_empty_file_stops_with_a_plain_message(tmp_path, broken):
    save_inputs(tmp_path, feature_set([0, 1, 2, 3, 4]))
    (tmp_path / broken).write_text("")

    with pytest.raises(TrainingSplitError, match=f"{broken} could not be read"):
        load_inputs(tmp_path)


def test_a_split_made_from_different_cleaned_data_stops_the_run(tmp_path):
    save_inputs(tmp_path, feature_set([0, 1, 2, 3, 4]))
    # The cleaned data was rebuilt since the split was made: row 2 now has another host.
    rebuilt = feature_set([0, 1, 2, 3, 4])
    rebuilt.loc[rebuilt["row"] == 2, "host"] = "other.example"
    rebuilt.to_csv(tmp_path / FEATURES_CSV_NAME, index=False)

    with pytest.raises(TrainingSplitError, match="made from different cleaned data"):
        load_inputs(tmp_path)


def test_a_missing_check_file_stops_the_run(tmp_path):
    save_inputs(tmp_path, feature_set([0, 1, 2, 3, 4]))
    (tmp_path / SPLIT_CHECK_NAME).unlink()

    with pytest.raises(TrainingSplitError, match=f"{SPLIT_CHECK_NAME} is missing"):
        load_inputs(tmp_path)

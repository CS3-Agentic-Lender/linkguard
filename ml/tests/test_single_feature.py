import numpy as np
import pandas as pd
import pytest

from leakage.single_feature import numeric_feature_columns, single_feature_accuracy

ROWS = 200
rng = np.random.default_rng(0)
label = np.tile([0, 1], ROWS // 2)

# Made-up sample: one column gives the label away, one is noise, one is right 90% of the time.
SAMPLE = pd.DataFrame(
    {
        "URL": [f"https://site{i}.example" for i in range(ROWS)],
        "Answer": label * 10,
        "Noise": rng.random(ROWS),
        "Mostly": np.where(np.arange(ROWS) % 10 == 0, 1 - label, label),
        "label": label,
    }
)


def test_numeric_feature_columns_skip_text_and_the_label():
    assert numeric_feature_columns(SAMPLE) == ["Answer", "Noise", "Mostly"]


def test_scores_every_column_sorted_high_to_low():
    table = single_feature_accuracy(SAMPLE, ["Noise", "Mostly", "Answer"])

    assert table["Column"].tolist() == ["Answer", "Mostly", "Noise"]
    assert table["Accuracy (%)"].is_monotonic_decreasing


def test_one_split_on_a_column_that_gives_the_answer_away_scores_100():
    table = single_feature_accuracy(SAMPLE, ["Answer", "Mostly"]).set_index("Column")

    assert table.loc["Answer", "Accuracy (%)"] == pytest.approx(100)
    assert table.loc["Mostly", "Accuracy (%)"] == pytest.approx(90)


def test_marks_only_columns_over_95_percent():
    table = single_feature_accuracy(SAMPLE, ["Answer", "Mostly", "Noise"]).set_index("Column")

    assert table["Over 95%"].to_dict() == {"Answer": True, "Mostly": False, "Noise": False}


def test_gives_the_same_numbers_when_run_again():
    first = single_feature_accuracy(SAMPLE, ["Noise", "Mostly"])
    second = single_feature_accuracy(SAMPLE, ["Noise", "Mostly"])

    pd.testing.assert_frame_equal(first, second)


def test_refuses_a_column_that_is_missing_or_not_numeric():
    with pytest.raises(ValueError, match="URL"):
        single_feature_accuracy(SAMPLE, ["URL"])
    with pytest.raises(ValueError, match="Missing"):
        single_feature_accuracy(SAMPLE, ["Missing"])

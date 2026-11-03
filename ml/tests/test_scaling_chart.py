import pandas as pd
import pytest

from splitting.scaling_chart import BIN_COUNT, scaling_chart

BEFORE = pd.DataFrame(
    {"HostnameLength": [10, 20, 30, 40], "IsDomainIP": [0, 0, 1, 0]},
)
AFTER = pd.DataFrame(
    {"HostnameLength": [-1.3, -0.4, 0.4, 1.3], "IsDomainIP": [-0.6, -0.6, 1.7, -0.6]},
)


def test_draws_one_row_per_feature_with_before_and_after_side_by_side():
    figure = scaling_chart(BEFORE, AFTER)

    axes = figure.get_axes()
    assert len(axes) == 2 * len(BEFORE.columns)
    titles = [axis.get_title() for axis in axes]
    assert titles == [
        "HostnameLength: before",
        "HostnameLength: after",
        "IsDomainIP: before",
        "IsDomainIP: after",
    ]


def test_each_panel_counts_every_training_row():
    figure = scaling_chart(BEFORE, AFTER)

    for axis in figure.get_axes():
        bars = axis.patches
        assert len(bars) == BIN_COUNT
        assert sum(bar.get_height() for bar in bars) == len(BEFORE)


def test_axes_are_labelled_in_words():
    figure = scaling_chart(BEFORE, AFTER)

    before_axis, after_axis = figure.get_axes()[:2]
    assert before_axis.get_xlabel() == "Original value"
    assert after_axis.get_xlabel() == "Scaled value (mean 0, spread 1)"
    assert before_axis.get_ylabel() == "Training rows"


def test_rejects_before_and_after_with_different_columns():
    with pytest.raises(ValueError, match="same columns"):
        scaling_chart(BEFORE, AFTER[["HostnameLength"]])


def test_saves_as_an_image(tmp_path):
    figure = scaling_chart(BEFORE, AFTER)

    path = tmp_path / "chart.png"
    figure.savefig(path)

    assert path.read_bytes().startswith(b"\x89PNG")

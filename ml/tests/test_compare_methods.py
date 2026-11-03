import matplotlib.colors
import numpy as np
import pandas as pd
import pytest

from features.hostname import FEATURE_NAMES
from ranking.compare_methods import DROPPED_COLOUR, METHODS, WATCH_COLOUR, comparison_chart, ordinal, pca_weights, rank_table, usefulness


def made_up_table(score_column: str, order: list[str]) -> pd.DataFrame:
    """A ranking table like the methods return: Rank, Feature, score, highest first."""
    scores = np.linspace(1.0, 0.1, len(order))
    return pd.DataFrame({"Rank": range(1, len(order) + 1), "Feature": order, score_column: scores})


FORWARD = list(FEATURE_NAMES)
BACKWARD = list(reversed(FEATURE_NAMES))


def rankings() -> dict[str, pd.DataFrame]:
    return {
        "Mutual information": made_up_table("Score", FORWARD),
        "Forest (built-in)": made_up_table("Importance", BACKWARD),
        "Forest (held-out hosts)": made_up_table("Accuracy drop", FORWARD),
        "PCA weight": made_up_table("Weight", BACKWARD),
    }


def test_rank_table_has_one_row_per_feature_and_one_column_per_method():
    table = rank_table(rankings())

    assert sorted(table.index) == sorted(FEATURE_NAMES)
    assert list(table.columns) == list(METHODS)
    assert table.loc[FEATURE_NAMES[0], "Mutual information"] == 1
    assert table.loc[FEATURE_NAMES[0], "Forest (built-in)"] == 10


def test_rank_table_is_ordered_by_average_rank_with_ties_in_extractor_order():
    # Forward and backward rankings give every feature the same average rank of 5.5.
    table = rank_table(rankings())

    assert list(table.index) == list(FEATURE_NAMES)


def test_rank_table_refuses_a_ranking_that_misses_a_feature():
    broken = rankings()
    broken["PCA weight"] = broken["PCA weight"].iloc[:9]

    with pytest.raises(ValueError, match="PCA weight"):
        rank_table(broken)


def test_pca_weights_weigh_each_loading_by_its_components_variance():
    # Two components over three features: the first holds 75% of the variance.
    loadings = np.array([[1.0, 0.0, 0.0], [0.0, -1.0, 0.0]])
    ratios = np.array([0.75, 0.25])

    weights = pca_weights(loadings, ratios, ["a", "b", "c"])

    assert weights["Feature"].tolist() == ["a", "b", "c"]
    assert weights["Weight"].tolist() == pytest.approx([0.75, 0.25, 0.0])
    assert weights["Rank"].tolist() == [1, 2, 3]


def test_ordinal_places():
    assert [ordinal(place) for place in (1, 2, 3, 4, 10)] == ["1st", "2nd", "3rd", "4th", "10th"]


def test_usefulness_ignores_pca_and_runs_from_10_to_1():
    ranks = rank_table(rankings())
    # The first feature came 1st, 10th and 1st in the label methods, whatever PCA says.
    assert usefulness(ranks)[FEATURE_NAMES[0]] == pytest.approx(11 - 4)


def test_chart_has_one_bar_per_feature_with_places_and_colours():
    ranks = rank_table(rankings())
    dropped, watch = {FEATURE_NAMES[1]}, {FEATURE_NAMES[2]}

    figure = comparison_chart(ranks, dropped, watch)
    axes = figure.axes[0]

    assert axes.get_xlabel().startswith("How useful")
    assert axes.get_ylabel() == "Feature"
    assert "Longer bar = more useful" in axes.get_title()
    assert len(axes.patches) == len(FEATURE_NAMES)
    labels = [tick.get_text() for tick in axes.get_yticklabels()]
    colours = {label: bar.get_facecolor() for label, bar in zip(labels, axes.patches)}
    assert matplotlib.colors.to_hex(colours[FEATURE_NAMES[1]]) == DROPPED_COLOUR
    assert matplotlib.colors.to_hex(colours[FEATURE_NAMES[2]]) == WATCH_COLOUR
    assert "came 1st, 10th, 1st" in [text.get_text() for text in axes.texts]

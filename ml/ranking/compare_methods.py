"""Put the four feature rankings side by side, so the final list can say where they agree.

The four rankings are mutual information, the forest's built-in importance, the forest's
importance on held-out training hosts, and each feature's weight in PCA. Every method is
turned into ranks 1 to 10, because their raw scores are on different scales.

The chart only uses the three methods that look at the label. A feature's PCA weight is its loading on each main component, ignoring the sign, times the
share of the variance that component explains, added up over the main components. PCA never
looks at the label, so this column says which features carry the spread of the data, not
which ones predict phishing.
"""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from features.hostname import FEATURE_NAMES

METHODS = ("Mutual information", "Forest (built-in)", "Forest (held-out hosts)", "PCA weight")
# PCA never looks at the label, so the chart and the choice only use the other three.
LABEL_METHODS = METHODS[:3]
CHART_SIZE_INCHES = (8, 5.6)
CHART_DPI = 100
CHART_TITLE = (
    "Each method puts the 10 features in order, 1st to 10th\n"
    "Longer bar = more useful\n"
    "Blue = keep, orange = keep but watch, grey = dropped (a copy)"
)
KEEP_COLOUR = "#1f4e8c"
WATCH_COLOUR = "#e0a030"
DROPPED_COLOUR = "#bbbbbb"


def pca_weights(loadings: np.ndarray, ratios: np.ndarray, names: list[str]) -> pd.DataFrame:
    """Rank, Feature and Weight from the main components' loadings and their variance shares.

    loadings has one row per main component and one column per feature.
    """
    weight = (np.abs(loadings) * ratios[:, None]).sum(axis=0)
    table = pd.DataFrame({"Feature": names, "Weight": weight})
    table = table.sort_values("Weight", ascending=False, kind="stable").reset_index(drop=True)
    table.insert(0, "Rank", range(1, len(table) + 1))
    return table


def rank_table(rankings: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per feature and one rank column per method, ordered by the average rank.

    Ties in the average keep the extractor's feature order.
    """
    columns = {}
    for method in METHODS:
        ranking = rankings[method]
        if sorted(ranking["Feature"]) != sorted(FEATURE_NAMES):
            raise ValueError(f"The {method} ranking does not have exactly the ten features.")
        columns[method] = ranking.set_index("Feature")["Rank"]
    table = pd.DataFrame(columns).loc[list(FEATURE_NAMES)]
    order = table.mean(axis=1).sort_values(kind="stable").index
    return table.loc[order]


def ordinal(place: int) -> str:
    """1st, 2nd, 3rd, 4th ... 10th."""
    return f"{place}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(place, 'th') }"


def usefulness(ranks: pd.DataFrame) -> pd.Series:
    """How useful each feature is across the methods that look at the label: 10 if it came 1st in all, 1 if last in all."""
    return len(FEATURE_NAMES) + 1 - ranks[list(LABEL_METHODS)].mean(axis=1)


def comparison_chart(ranks: pd.DataFrame, dropped: set[str], watch: set[str]) -> Figure:
    """One bar per feature, longest first. Each bar says the places it came in the label methods.

    Grey bars are dropped features, orange bars are kept but watched, blue bars are kept.
    """
    scores = usefulness(ranks).sort_values(ascending=True, kind="stable")
    colours = [DROPPED_COLOUR if name in dropped else WATCH_COLOUR if name in watch else KEEP_COLOUR for name in scores.index]
    figure, axes = plt.subplots(figsize=CHART_SIZE_INCHES, dpi=CHART_DPI)
    bars = axes.barh(list(scores.index), list(scores), color=colours)
    for bar, name in zip(bars, scores.index):
        places = ", ".join(ordinal(int(ranks.loc[name, method])) for method in LABEL_METHODS)
        axes.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2, f"came {places}", va="center", fontsize=9)
    axes.set_xlim(0, len(FEATURE_NAMES) + 2)
    axes.set_xlabel("How useful (10 = came 1st in every method, 1 = came last in every method)")
    axes.set_ylabel("Feature")
    axes.set_title(CHART_TITLE)
    figure.tight_layout()
    return figure

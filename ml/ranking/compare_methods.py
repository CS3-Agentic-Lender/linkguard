"""Put the four feature rankings side by side, so the final list can say where they agree.

The four rankings are mutual information, the forest's built-in importance, the forest's
importance on held-out training hosts, and each feature's weight in PCA. Every method is
turned into ranks 1 to 10, because their raw scores are on different scales.

A feature's PCA weight is its loading on each main component, ignoring the sign, times the
share of the variance that component explains, added up over the main components. PCA never
looks at the label, so this column says which features carry the spread of the data, not
which ones predict phishing.
"""

import textwrap

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from features.hostname import FEATURE_NAMES

METHODS = ("Mutual information", "Forest (built-in)", "Forest (held-out hosts)", "PCA weight")
CHART_SIZE_INCHES = (8, 5.6)
CHART_DPI = 100
LABEL_WIDTH = 12  # characters per line for method names under the grid
TITLE_WIDTH = 60  # characters per line for the takeaway


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


def comparison_chart(ranks: pd.DataFrame, takeaway: str) -> Figure:
    """A grid of ranks, features down the side and methods across. Darker means ranked higher."""
    figure, axes = plt.subplots(figsize=CHART_SIZE_INCHES, dpi=CHART_DPI)
    values = ranks.to_numpy()
    axes.imshow(values, cmap="Blues_r", vmin=1, vmax=len(FEATURE_NAMES) + 3, aspect="auto")
    for row in range(values.shape[0]):
        for column in range(values.shape[1]):
            rank = int(values[row, column])
            axes.text(column, row, str(rank), ha="center", va="center", color="white" if rank <= 4 else "black")
    axes.set_xticks(range(len(ranks.columns)), labels=[textwrap.fill(name, LABEL_WIDTH) for name in ranks.columns])
    axes.set_yticks(range(len(ranks.index)), labels=list(ranks.index))
    axes.set_xlabel("Method")
    axes.set_ylabel("Feature")
    axes.set_title(textwrap.fill(takeaway, TITLE_WIDTH))
    figure.tight_layout()
    return figure

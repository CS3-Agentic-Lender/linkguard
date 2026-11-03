"""Run PCA on the ten hostname features, on the scaled training split only.

PCA finds the directions in which the training rows spread out the most. Each
direction is a component: a weighted mix of the ten features. The first component
explains the most variance, the second the next most, and so on. When a few
components explain nearly all of it, the features overlap a lot.

The rows are scaled with the saved scaler, which is only used to transform. It is
never fitted again, so the scale still comes from the training rows the split made.
PCA ignores the label, so its weights are a guide to which features to keep, not
the decision. The components are never used as model inputs.

No cross-validation happens here, so there is no Pipeline. Any later cross-validation
puts the scaler and PCA in one scikit-learn Pipeline, fitted on each fold's training part.

Writes ml/reports/pca.md and ml/reports/pca_explained_variance.png.
Run from ml/:  uv run python -m ranking.pca
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from features.hostname import FEATURE_NAMES
from ranking.training_split import TrainingSplitError, load_inputs, training_split
from splitting.scaling import SCALER_FILE_NAME, load_scaler, scale

SEED = 0  # with the full solver the fit has no randomness, but the seed is fixed anyway
TARGET_SHARE = 0.95
TARGET_PERCENT = 95
# Adding up shares can land a hair under the target through float rounding alone
# (0.69 + 0.18 + 0.08 gives 0.9499999999999998). Anything this close counts as reached.
ROUNDING_TOLERANCE = 1e-9
MARKED_PER_COMPONENT = 2
REPORT_NAME = "pca.md"
CHART_NAME = "pca_explained_variance.png"
CHART_TITLE = "How much of the variance the first components explain"
CHART_DPI = 100
CHART_SIZE_INCHES = (8, 4.8)
LINE_COLOUR = "#2e8b57"
TARGET_COLOUR = "#5b7a99"
GRID_COLOUR = "#e0e0e0"


class PcaError(Exception):
    """The saved scaler cannot be used on this training split."""


def component_names(count: int) -> list[str]:
    return [f"PC{number}" for number in range(1, count + 1)]


def fit_pca(features: pd.DataFrame, split: pd.DataFrame, scaler: StandardScaler) -> PCA:
    """PCA with all ten components, fitted on the scaled training rows.

    Takes the whole feature set and the split, and drops the test rows itself, so no
    caller can hand it test rows by mistake. The scaler is only used to transform.
    """
    training = training_split(features, split)[list(FEATURE_NAMES)]
    if list(getattr(scaler, "feature_names_in_", [])) != list(FEATURE_NAMES):
        raise PcaError(f"The saved scaler was not fitted on the ten feature columns {list(FEATURE_NAMES)}, in that order.")
    # The split and the scaler are saved together, so a scaler that saw a different
    # number of rows was fitted on other data and would scale these rows wrongly.
    if scaler.n_samples_seen_ != len(training):
        raise PcaError(
            f"The saved scaler was fitted on {int(scaler.n_samples_seen_):,} rows, but the training split has "
            f'{len(training):,}. Make both again with "uv run python -m splitting.build".'
        )
    pca = PCA(n_components=len(FEATURE_NAMES), svd_solver="full", random_state=SEED)
    return pca.fit(scale(scaler, training))


def variance_table(pca: PCA) -> pd.DataFrame:
    """Component, Variance % and Cumulative % for each component, first component first."""
    shares = 100 * pca.explained_variance_ratio_
    return pd.DataFrame(
        {
            "Component": component_names(len(shares)),
            "Variance %": shares,
            "Cumulative %": np.cumsum(shares),
        }
    )


def components_to_reach(ratios: np.ndarray, share: float = TARGET_SHARE) -> int:
    """The fewest components whose explained variance adds up to at least share."""
    return int(np.flatnonzero(np.cumsum(ratios) >= share - ROUNDING_TOLERANCE)[0]) + 1


def takeaway(pca: PCA) -> str:
    """One line saying how many components reach 95% of the variance."""
    count = components_to_reach(pca.explained_variance_ratio_)
    reached = 100 * pca.explained_variance_ratio_[:count].sum()
    total = len(pca.explained_variance_ratio_)
    return f"It takes {count} of the {total} components to reach {TARGET_PERCENT}% of the variance ({reached:.1f}% in all)."


def loadings_table(pca: PCA, count: int) -> pd.DataFrame:
    """Each feature's signed weight on the first count components: features as rows, components as columns."""
    return pd.DataFrame(pca.components_[:count].T, index=list(pca.feature_names_in_), columns=component_names(count))


def marked_features(loadings: pd.DataFrame) -> dict[str, list[str]]:
    """For each component, the two features with the largest weight, ignoring the sign.

    A tie keeps the feature order, so the result never changes between runs.
    """
    return {
        component: weights.abs().sort_values(ascending=False, kind="stable").index[:MARKED_PER_COMPONENT].tolist()
        for component, weights in loadings.items()
    }


def variance_chart(pca: PCA) -> Figure:
    """Cumulative explained variance against the number of components, with a dashed line at 95%."""
    numbers = np.arange(1, len(pca.explained_variance_ratio_) + 1)
    cumulative = 100 * np.cumsum(pca.explained_variance_ratio_)
    figure = Figure(figsize=CHART_SIZE_INCHES, layout="constrained")
    axis = figure.subplots()
    axis.axhline(TARGET_PERCENT, color=TARGET_COLOUR, linestyle="--", linewidth=1.5)
    axis.text(numbers[-1], TARGET_PERCENT - 1.5, f"{TARGET_PERCENT}%", color="#333333", ha="right", va="top")
    axis.plot(numbers, cumulative, color=LINE_COLOUR, linewidth=2, marker="o", markersize=7)
    axis.set_xticks(numbers)
    axis.set_ylim(0, 105)
    axis.set_yticks(range(0, 101, 10))
    axis.set_xlabel("Number of components")
    axis.set_ylabel("Cumulative explained variance (%)")
    axis.set_title(takeaway(pca), fontsize="medium")
    axis.grid(color=GRID_COLOUR, linewidth=0.8)
    axis.set_axisbelow(True)
    axis.spines[["top", "right"]].set_visible(False)
    figure.suptitle(CHART_TITLE)
    return figure


def _weight(value: float) -> str:
    text = f"{value:.2f}"
    return "0.00" if text == "-0.00" else text


def _loadings_rows(loadings: pd.DataFrame, marked: dict[str, list[str]]) -> list[str]:
    rows = []
    for feature, weights in loadings.iterrows():
        cells = [
            f"**{_weight(value)}**" if feature in marked[component] else _weight(value)
            for component, value in weights.items()
        ]
        marked_on = [component for component in loadings.columns if feature in marked[component]]
        rows.append(f"| `{feature}` | " + " | ".join(cells) + f" | {', '.join(marked_on) or '-'} |")
    return rows


def report(pca: PCA) -> str:
    """The variance table, the chart, the loadings table and what they mean, as a Markdown page."""
    variance = variance_table(pca)
    count = components_to_reach(pca.explained_variance_ratio_)
    loadings = loadings_table(pca, count)
    marked = marked_features(loadings)
    main_components = "PC1" if count == 1 else f"PC1 to PC{count}"
    lines = [
        "# PCA on the ten hostname features",
        "",
        "## How it was made",
        "",
        f"- Training rows: {pca.n_samples_:,}. Test rows are dropped before anything is fitted.",
        "- The rows are scaled with the saved scaler (`ml/models/scaler.joblib`). It is only used to transform. It is never fitted again.",
        f"- PCA keeps all {pca.n_components_} components. It uses scikit-learn's full solver with seed {SEED}, so a second run gives the same result.",
        "",
        "## Explained variance",
        "",
        "| Component | Variance % | Cumulative % |",
        "|---|---|---|",
        *(f"| {name} | {share:.2f} | {total:.2f} |" for name, share, total in variance.itertuples(index=False)),
        "",
        f"![Cumulative explained variance]({CHART_NAME})",
        "",
        f"**Takeaway:** {takeaway(pca)}",
        "",
        "## Loadings on the main components",
        "",
        f"The main components are the fewest that reach {TARGET_PERCENT}% of the variance. Here that is {main_components}.",
        "Each cell is a feature's weight on a component. The sign only gives the direction.",
        f"On each component the {MARKED_PER_COMPONENT} features with the largest weight, ignoring the sign, are in bold.",
        "The last column lists the components a feature is marked on.",
        "",
        "| Feature | " + " | ".join(loadings.columns) + " | Marked on |",
        "|---|" + "---|" * (count + 1),
        *_loadings_rows(loadings, marked),
        "",
        "## What this means",
        "",
        "- PCA ignores the label. The weights show how the features overlap, not which ones find phishing.",
        "  They are a guide for the final feature list, not the decision.",
        "- Two of the ten features follow exactly from the others. `HostnameLength` is the letters plus the digits plus the special characters.",
        "  The three ratios add up to 1. So the ten features hold only eight independent values, and the last two components explain nothing.",
        "- The components are never used as model inputs. The model keeps the real features.",
        "- No cross-validation happens here. Any later cross-validation puts the scaler and PCA in one scikit-learn Pipeline.",
        "  That Pipeline is fitted on each fold's training part only.",
        "",
        "Made by `uv run python -m ranking.pca`.",
    ]
    return "\n".join(lines) + "\n"


def _load_saved_scaler(path: Path) -> StandardScaler:
    if not path.is_file():
        raise PcaError(f'{path} was not found. Make it with "uv run python -m splitting.build" (see ml/README.md).')
    return load_scaler(path)


def main(ml_dir: Path) -> int:
    """Fit PCA on the training split and save the report and chart. Returns 1 and saves nothing if the inputs are wrong."""
    try:
        features, split = load_inputs(ml_dir / "data")
        scaler = _load_saved_scaler(ml_dir / "models" / SCALER_FILE_NAME)
        pca = fit_pca(features, split, scaler)
    except (TrainingSplitError, PcaError) as error:
        print(f"PCA stopped: {error}")
        return 1
    reports_dir = ml_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    chart_path = reports_dir / CHART_NAME
    variance_chart(pca).savefig(chart_path, dpi=CHART_DPI)
    page = report(pca)
    report_path = reports_dir / REPORT_NAME
    report_path.write_text(page)
    print(page)
    print(f"Saved {report_path} and {chart_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parents[1]))

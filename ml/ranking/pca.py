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
"""

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from features.hostname import FEATURE_NAMES
from ranking.training_split import training_split
from splitting.scaling import scale

SEED = 0  # with the full solver the fit has no randomness, but the seed is fixed anyway
TARGET_SHARE = 0.95


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
    return int(np.flatnonzero(np.cumsum(ratios) >= share)[0]) + 1

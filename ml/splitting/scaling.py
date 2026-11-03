"""Put the numeric features on a common scale, fitted on the training set only.

StandardScaler moves each feature to mean 0 and spread 1. It suits the ten
hostname features: they are counts and ratios with no hard upper limit, and
models such as logistic regression train badly when one feature (for example
HostnameLength, in the tens) dwarfs another (a ratio between 0 and 1).

The scaler only ever learns from training rows. Test rows are transformed with
what it learned, never fitted, so nothing about the test set leaks into training.
The saved file goes in ml/models/, where *.joblib files are gitignored.
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.preprocessing import StandardScaler

SCALER_FILE_NAME = "scaler.joblib"


def fit_scaler(train_features: pd.DataFrame) -> StandardScaler:
    """Return a scaler fitted on the training rows only."""
    return StandardScaler().fit(train_features)


def scale(scaler: StandardScaler, features: pd.DataFrame) -> pd.DataFrame:
    """Return a scaled copy of features, keeping its index and column names."""
    expected = list(scaler.feature_names_in_)
    if list(features.columns) != expected:
        raise ValueError(f"Expected the columns {expected}, in that order.")
    values = scaler.transform(features)
    return pd.DataFrame(values, index=features.index, columns=features.columns)


def save_scaler(scaler: StandardScaler, path: Path) -> Path:
    """Write the fitted scaler to path, creating its folder if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(scaler, path)
    return path


def load_scaler(path: Path) -> StandardScaler:
    """Read a scaler written by save_scaler()."""
    return joblib.load(path)

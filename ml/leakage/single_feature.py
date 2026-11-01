"""Score how well each numeric column predicts the label on its own.

Single-feature accuracy is the 5-fold cross-validated accuracy of a decision tree
with one split (the best single threshold) trained on that column alone. A column
over 95% is flagged: it may be restating the label rather than a warning sign.
"""

import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.tree import DecisionTreeClassifier

from cleaning.labels import LABEL_COLUMN

FOLDS = 5
SEED = 0  # fixed so a second run gives the same folds and numbers
LEAKY_ACCURACY_PERCENT = 95


def numeric_feature_columns(rows: pd.DataFrame) -> list[str]:
    """Every numeric column except the label, in file order."""
    return [
        column
        for column in rows.columns
        if column != LABEL_COLUMN and pd.api.types.is_numeric_dtype(rows[column])
    ]


def _check_columns(rows: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in rows.columns]
    if missing:
        raise ValueError(f"Columns not in the data: {missing}")
    not_numeric = [column for column in columns if not pd.api.types.is_numeric_dtype(rows[column])]
    if not_numeric:
        raise ValueError(f"Columns are not numeric: {not_numeric}")


def _one_split_accuracy(feature: pd.DataFrame, label: pd.Series) -> float:
    stump = DecisionTreeClassifier(max_depth=1, random_state=SEED)
    folds = StratifiedKFold(n_splits=FOLDS, shuffle=True, random_state=SEED)
    return float(cross_val_score(stump, feature, label, cv=folds, scoring="accuracy").mean())


def single_feature_accuracy(rows: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """One row per column with its accuracy in percent and whether it is over 95%, sorted high to low."""
    _check_columns(rows, columns)
    label = rows[LABEL_COLUMN]
    scores = [
        {"Column": column, "Accuracy (%)": _one_split_accuracy(rows[[column]], label) * 100}
        for column in columns
    ]
    table = pd.DataFrame(scores, columns=["Column", "Accuracy (%)"])
    table = table.assign(**{"Over 95%": table["Accuracy (%)"] > LEAKY_ACCURACY_PERCENT})
    return table.sort_values(["Accuracy (%)", "Column"], ascending=[False, True]).reset_index(drop=True)

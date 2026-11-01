"""Split the cleaned rows into legitimate and phishing, in the cleaned label coding."""

import pandas as pd

from cleaning.labels import LABEL_COLUMN, LEGITIMATE, PHISHING


def split_by_class(rows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (legitimate, phishing). Stops if either class is missing, since every check compares the two."""
    if LABEL_COLUMN not in rows.columns:
        raise ValueError(f"Missing column {LABEL_COLUMN!r}.")
    legitimate = rows[rows[LABEL_COLUMN] == LEGITIMATE]
    phishing = rows[rows[LABEL_COLUMN] == PHISHING]
    if legitimate.empty or phishing.empty:
        raise ValueError("The leakage checks need both legitimate and phishing rows.")
    return legitimate, phishing

"""Save the cleaned data to ml/data/ and read it back.

The file is a CSV without the row index. It is read back with
keep_default_na=False and no na_values, so text such as "" (a blanked title),
"na" (Namibia's domain) or "NULL" (a real title) stays as text instead of
becoming a missing value. ml/data/ is gitignored, so the file is never committed.
"""

from pathlib import Path

import pandas as pd

CLEANED_CSV_NAME = "phiusiil_cleaned.csv"


def save_cleaned(rows: pd.DataFrame, path: Path) -> Path:
    """Write the cleaned rows to path, creating its folder if needed. The data is not changed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(path, index=False)
    return path


def load_cleaned(path: Path) -> pd.DataFrame:
    """Read a file written by save_cleaned() without turning any text into missing values."""
    return pd.read_csv(path, keep_default_na=False)

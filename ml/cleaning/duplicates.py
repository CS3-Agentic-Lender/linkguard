"""Remove rows whose URL appears more than once.

Rule (from the "remove duplicate and invalid rows" story's spec):
- A duplicate is a row whose URL exactly matches another row's. Keep the first copy.
- If copies of the same URL carry different labels, the label can't be trusted,
  so every copy is removed and counted separately.
- Rows with a missing URL are left for the missing-values check.
"""

from dataclasses import dataclass

import pandas as pd

URL_COLUMN = "URL"
LABEL_COLUMN = "label"


@dataclass(frozen=True)
class DuplicateResult:
    cleaned: pd.DataFrame
    rows_before: int
    duplicate_rows_removed: int
    conflicting_urls: int
    conflicting_rows_removed: int

    @property
    def rows_after(self) -> int:
        return len(self.cleaned)


def remove_duplicate_urls(rows: pd.DataFrame) -> DuplicateResult:
    """Return a new frame with duplicate URLs removed. The input is not changed."""
    missing = [column for column in (URL_COLUMN, LABEL_COLUMN) if column not in rows.columns]
    if missing:
        raise ValueError(f"Cannot remove duplicates: missing column(s) {missing}.")

    has_url = rows[URL_COLUMN].notna()

    labels_per_url = rows.loc[has_url].groupby(URL_COLUMN)[LABEL_COLUMN].nunique()
    conflicting = labels_per_url[labels_per_url > 1].index
    is_conflicting = rows[URL_COLUMN].isin(conflicting)

    without_conflicts = rows.loc[~is_conflicting]
    is_extra_copy = without_conflicts.duplicated(URL_COLUMN, keep="first") & has_url.loc[~is_conflicting]
    cleaned = without_conflicts.loc[~is_extra_copy].copy()

    return DuplicateResult(
        cleaned=cleaned,
        rows_before=len(rows),
        duplicate_rows_removed=int(is_extra_copy.sum()),
        conflicting_urls=len(conflicting),
        conflicting_rows_removed=int(is_conflicting.sum()),
    )

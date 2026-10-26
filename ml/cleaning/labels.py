"""Recode the label so 1 means phishing and 0 means legitimate.

The raw PhiUSIIL file uses the reverse (1 = legitimate, 0 = phishing). Every
LinkGuard model uses the recoded label, so this runs once, after the other
cleaning steps: new label = 1 - raw label.
"""

from dataclasses import dataclass

import pandas as pd

LABEL_COLUMN = "label"
PHISHING = 1
LEGITIMATE = 0


@dataclass(frozen=True)
class LabelResult:
    recoded: pd.DataFrame
    phishing: int
    legitimate: int


def recode_label(rows: pd.DataFrame) -> LabelResult:
    """Return a new frame with the label flipped. The input is not changed."""
    if LABEL_COLUMN not in rows.columns:
        raise ValueError(f"Cannot recode: missing column {LABEL_COLUMN!r}.")

    raw_label = rows[LABEL_COLUMN]
    unexpected = sorted(raw_label[~raw_label.isin([0, 1])].unique().tolist())
    if unexpected:
        raise ValueError(f"Label must be 0 or 1 before recoding, found {unexpected}. Run the value checks first.")

    recoded = rows.assign(**{LABEL_COLUMN: 1 - raw_label})
    new_label = recoded[LABEL_COLUMN]
    return LabelResult(
        recoded=recoded,
        phishing=int((new_label == PHISHING).sum()),
        legitimate=int((new_label == LEGITIMATE).sum()),
    )

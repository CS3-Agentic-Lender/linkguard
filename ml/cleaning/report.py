"""Run every cleaning step in order and summarise the row counts.

run_cleaning() always starts from the raw data, so running it again gives the
same numbers, and the label is recoded exactly once per run.
"""

from dataclasses import dataclass

import pandas as pd

from cleaning.duplicates import DuplicateResult, remove_duplicate_urls
from cleaning.labels import LabelResult, recode_label
from cleaning.values import ValueResult, clean_values


@dataclass(frozen=True)
class CleaningStep:
    name: str
    rows_before: int
    rows_after: int

    @property
    def rows_removed(self) -> int:
        return self.rows_before - self.rows_after


@dataclass(frozen=True)
class CleaningRun:
    duplicates: DuplicateResult
    values: ValueResult
    labels: LabelResult

    @property
    def cleaned(self) -> pd.DataFrame:
        return self.labels.recoded

    @property
    def steps(self) -> tuple[CleaningStep, ...]:
        return (
            CleaningStep("1. Duplicate URLs", self.duplicates.rows_before, self.duplicates.rows_after),
            CleaningStep(
                "2. Missing, empty and out-of-range values", self.values.rows_before, self.values.rows_after
            ),
            CleaningStep("3. Recode the label", len(self.values.cleaned), len(self.labels.recoded)),
        )


def run_cleaning(raw: pd.DataFrame) -> CleaningRun:
    """Run steps 1 to 3 on the raw data. The input is not changed."""
    duplicates = remove_duplicate_urls(raw)
    values = clean_values(duplicates.cleaned)
    labels = recode_label(values.cleaned)
    return CleaningRun(duplicates=duplicates, values=values, labels=labels)


def steps_table(steps: tuple[CleaningStep, ...]) -> pd.DataFrame:
    """One row per step with rows before, after and removed, plus a total row."""
    if not steps:
        raise ValueError("A cleaning report needs at least one step.")
    for previous, step in zip(steps, steps[1:]):
        if step.rows_before != previous.rows_after:
            raise ValueError(
                f"Step {step.name!r} starts with {step.rows_before:,} rows, "
                f"but the step before it ended with {previous.rows_after:,}."
            )

    rows = [
        {"Step": s.name, "Rows before": s.rows_before, "Rows after": s.rows_after, "Rows removed": s.rows_removed}
        for s in steps
    ]
    total = {
        "Step": "Total",
        "Rows before": steps[0].rows_before,
        "Rows after": steps[-1].rows_after,
        "Rows removed": steps[0].rows_before - steps[-1].rows_after,
    }
    return pd.DataFrame([*rows, total])

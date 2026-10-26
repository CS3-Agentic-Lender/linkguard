"""Count and fix missing, empty and out-of-range values.

Rules (from the "remove duplicate and invalid rows" story's spec, with column
groups and ranges from the import story's data dictionary):
- Out of range: a count below 0, a ratio or rate outside 0 to 1, a score outside
  0 to 100, a 0/1 column holding anything else, a label other than 0 or 1.
- Missing: no value at all. Empty: text that is blank once spaces are stripped.
- Title placeholder: the raw file writes the text "0" as the title of pages that
  have no title (HasTitle = 0). It counts as empty and is fixed by blanking the
  title, so the row is kept.
- Every other missing, empty or out-of-range value removes its row, because the
  model can't use a row with a broken feature or label.
"""

from dataclasses import dataclass

import pandas as pd

COUNT_COLUMNS = (
    "URLLength", "DomainLength", "TLDLength", "NoOfSubDomain", "NoOfObfuscatedChar",
    "NoOfLettersInURL", "NoOfDegitsInURL", "NoOfEqualsInURL", "NoOfQMarkInURL",
    "NoOfAmpersandInURL", "NoOfOtherSpecialCharsInURL", "LineOfCode", "LargestLineLength",
    "NoOfURLRedirect", "NoOfSelfRedirect", "NoOfPopup", "NoOfiFrame", "NoOfImage",
    "NoOfCSS", "NoOfJS", "NoOfSelfRef", "NoOfEmptyRef", "NoOfExternalRef",
)
RATIO_COLUMNS = (
    "ObfuscationRatio", "LetterRatioInURL", "DegitRatioInURL", "SpacialCharRatioInURL",
    "CharContinuationRate", "TLDLegitimateProb", "URLCharProb",
)
SCORE_COLUMNS = ("URLSimilarityIndex", "DomainTitleMatchScore", "URLTitleMatchScore")
ZERO_ONE_COLUMNS = (
    "IsDomainIP", "HasObfuscation", "IsHTTPS", "HasTitle", "HasFavicon", "Robots",
    "IsResponsive", "HasDescription", "HasExternalFormSubmit", "HasSocialNet",
    "HasSubmitButton", "HasHiddenFields", "HasPasswordField", "Bank", "Pay", "Crypto",
    "HasCopyrightInfo", "label",
)

MAX_SCORE = 100
NO_TITLE_PLACEHOLDER = "0"
PROBLEM_KINDS = ("missing", "empty", "out_of_range")


@dataclass(frozen=True)
class ValueResult:
    cleaned: pd.DataFrame
    problems: pd.DataFrame
    rows_before: int
    rows_removed: int
    titles_fixed: int

    @property
    def rows_after(self) -> int:
        return len(self.cleaned)


def _out_of_range(column: str, values: pd.Series) -> pd.Series:
    if column in COUNT_COLUMNS:
        return values < 0
    if column in RATIO_COLUMNS:
        return (values < 0) | (values > 1)
    if column in SCORE_COLUMNS:
        return (values < 0) | (values > MAX_SCORE)
    if column in ZERO_ONE_COLUMNS:
        return values.notna() & ~values.isin([0, 1])
    raise ValueError(f"No range rule for numeric column {column!r}. Add it to a column group in cleaning/values.py.")


def _title_placeholder(rows: pd.DataFrame) -> pd.Series:
    if "Title" not in rows.columns or "HasTitle" not in rows.columns:
        return pd.Series(False, index=rows.index)
    return rows["Title"].eq(NO_TITLE_PLACEHOLDER) & rows["HasTitle"].eq(0)


def _problem_masks(rows: pd.DataFrame) -> dict[str, dict[str, pd.Series]]:
    """For each column, a True/False mask per problem kind."""
    no_problem = pd.Series(False, index=rows.index)
    masks = {}
    for column in rows.columns:
        values = rows[column]
        is_text = not pd.api.types.is_numeric_dtype(values)
        empty = values.astype("string").str.strip().eq("").fillna(False) if is_text else no_problem
        if column == "Title":
            no_title = rows["HasTitle"].eq(0) if "HasTitle" in rows.columns else no_problem
            empty = (empty & ~no_title) | _title_placeholder(rows)
        masks[column] = {
            "missing": values.isna(),
            "empty": empty,
            "out_of_range": no_problem if is_text else _out_of_range(column, values),
        }
    return masks


def find_value_problems(rows: pd.DataFrame) -> pd.DataFrame:
    """Count missing, empty and out-of-range values per column. One row per column."""
    masks = _problem_masks(rows)
    counts = {column: {kind: int(mask.sum()) for kind, mask in kinds.items()} for column, kinds in masks.items()}
    return pd.DataFrame.from_dict(counts, orient="index", columns=list(PROBLEM_KINDS))


def clean_values(rows: pd.DataFrame) -> ValueResult:
    """Return a new frame with the title placeholder blanked and broken rows removed. The input is not changed."""
    problems = find_value_problems(rows)
    placeholder = _title_placeholder(rows)

    fixed = rows.copy()
    if placeholder.any():
        fixed.loc[placeholder, "Title"] = ""

    broken = pd.Series(False, index=fixed.index)
    for kinds in _problem_masks(fixed).values():
        for mask in kinds.values():
            broken |= mask
    cleaned = fixed.loc[~broken].copy()

    return ValueResult(
        cleaned=cleaned,
        problems=problems,
        rows_before=len(rows),
        rows_removed=int(broken.sum()),
        titles_fixed=int(placeholder.sum()),
    )

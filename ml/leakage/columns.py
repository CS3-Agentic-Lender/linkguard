"""Checks on two single columns the research flagged: FILENAME and URLSimilarityIndex."""

import re
from dataclasses import dataclass

import pandas as pd

from cleaning.labels import LABEL_COLUMN, LEGITIMATE, PHISHING
from leakage.classes import split_by_class

FILENAME_COLUMN = "FILENAME"
URL_SIMILARITY_COLUMN = "URLSimilarityIndex"
URL_SIMILARITY_MAX = 100

# A file name is an optional letter prefix, a run of digits, then an extension: "mw123456.txt".
FILENAME_PATTERN = re.compile(r"^([A-Za-z]*)(\d+)\.(\w+)$")


def filename_shape(name: str) -> str:
    """Describe a file name by its prefix, digit count and extension, for example "mw + 6 digits .txt"."""
    match = FILENAME_PATTERN.match(name)
    if match is None:
        return "other"
    prefix, digits, extension = match.groups()
    unit = "digit" if len(digits) == 1 else "digits"
    shape = f"{len(digits)} {unit} .{extension}"
    return f"{prefix} + {shape}" if prefix else shape


@dataclass(frozen=True)
class FilenameLeak:
    shapes: pd.DataFrame  # rows per shape, columns Legitimate and Phishing
    accuracy: float  # guessing each shape's most common label
    phishing_only_shapes: list[str]


def filename_leak(rows: pd.DataFrame) -> FilenameLeak:
    """Count FILENAME shapes per class and score how well the shape alone gives the label."""
    split_by_class(rows)
    shape = rows[FILENAME_COLUMN].map(filename_shape)
    counts = (
        pd.crosstab(shape, rows[LABEL_COLUMN])
        .reindex(columns=[LEGITIMATE, PHISHING], fill_value=0)
        .rename(columns={LEGITIMATE: "Legitimate", PHISHING: "Phishing"})
        .rename_axis(index="Shape", columns=None)
    )
    phishing_only = counts[(counts["Legitimate"] == 0) & (counts["Phishing"] > 0)]
    return FilenameLeak(
        shapes=counts,
        accuracy=float(counts.max(axis=1).sum() / len(rows)),
        phishing_only_shapes=sorted(phishing_only.index.tolist()),
    )


@dataclass(frozen=True)
class UrlSimilarityCheck:
    rows: int
    minimum: float
    maximum: float
    all_100: bool
    phishing_share_at_100: float


def url_similarity_for_legitimate(rows: pd.DataFrame) -> UrlSimilarityCheck:
    """Summarise URLSimilarityIndex on legitimate rows, to test the finding that every one is 100."""
    legitimate, phishing = split_by_class(rows)
    values = legitimate[URL_SIMILARITY_COLUMN]
    return UrlSimilarityCheck(
        rows=len(values),
        minimum=float(values.min()),
        maximum=float(values.max()),
        all_100=bool((values == URL_SIMILARITY_MAX).all()),
        phishing_share_at_100=float((phishing[URL_SIMILARITY_COLUMN] == URL_SIMILARITY_MAX).mean()),
    )

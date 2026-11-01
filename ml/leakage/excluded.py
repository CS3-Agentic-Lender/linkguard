"""Columns left out of the first model, each with a one-line reason.

This is the list the first model uses to choose its inputs: every numeric column
not named here (and not the label) is a candidate feature. Columns that only
look suspicious in the leakage check stay in until the template-bias decision
says otherwise; see ml/reports/leakage_report.md.
"""

from types import MappingProxyType

from cleaning.labels import LABEL_COLUMN

# Columns worked out from the fetched page. The first version only sees the URL text.
PAGE_CONTENT_COLUMNS = (
    "LineOfCode",
    "LargestLineLength",
    "HasTitle",
    "DomainTitleMatchScore",
    "URLTitleMatchScore",
    "HasFavicon",
    "Robots",
    "IsResponsive",
    "NoOfURLRedirect",
    "NoOfSelfRedirect",
    "HasDescription",
    "NoOfPopup",
    "NoOfiFrame",
    "HasExternalFormSubmit",
    "HasSocialNet",
    "HasSubmitButton",
    "HasHiddenFields",
    "HasPasswordField",
    "Bank",
    "Pay",
    "Crypto",
    "HasCopyrightInfo",
    "NoOfImage",
    "NoOfCSS",
    "NoOfJS",
    "NoOfSelfRef",
    "NoOfEmptyRef",
    "NoOfExternalRef",
)

PAGE_CONTENT_REASON = "Page content: needs the fetched page, which the first version cannot get."

EXCLUDED_FEATURES = MappingProxyType(
    {
        "URLSimilarityIndex": "Restates the label: it measures similarity to the legitimate URLs, so every legitimate row scores 100.",
        "TLDLegitimateProb": "Built from how often each TLD appears among legitimate URLs; its reference data is unpublished.",
        "URLCharProb": "Built from character frequencies of the legitimate class; its reference data is unpublished.",
        "FILENAME": "Identifier: the crawl file name, whose shape alone gives the label away.",
        "URL": "Identifier: raw text the URL feature extractor reads, never a feature itself.",
        "Domain": "Identifier: the domain text, which would let the model memorise sites instead of warning signs.",
        "TLD": "Identifier: the TLD text; its length is already a feature (TLDLength).",
        "Title": "Identifier and page content: the fetched page's title text.",
        **{column: PAGE_CONTENT_REASON for column in PAGE_CONTENT_COLUMNS},
    }
)


def model_feature_columns(columns: list[str]) -> list[str]:
    """The columns left for the first model, in the given order."""
    return [column for column in columns if column != LABEL_COLUMN and column not in EXCLUDED_FEATURES]

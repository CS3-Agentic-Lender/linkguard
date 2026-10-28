"""Find bare-homepage URLs and compare URL shapes between the two classes.

A bare homepage is https://www.<domain> with nothing after the domain except an
optional trailing slash. Our research expects almost every legitimate URL to have
that shape, which would let a model separate the classes by URL template alone.

URLs are only matched as text with regular expressions. None is opened or fetched.
"""

import re

import pandas as pd

from cleaning.labels import LABEL_COLUMN, LEGITIMATE
from leakage.classes import split_by_class

URL_COLUMN = "URL"

# The domain part may not hold a slash, query, fragment, port, user part or space.
BARE_HOMEPAGE = r"^https://www\.[^/?#:@\s]+/?$"

# Each shape is a pattern that str.contains() looks for, ignoring case.
URL_SHAPES = {
    "Bare homepage": BARE_HOMEPAGE,
    "Uses https": r"^https://",
    "Uses www.": r"^[a-z][a-z0-9+.-]*://www\.",
    "Has a path": r"^[a-z][a-z0-9+.-]*://[^/?#]*/[^?#]",  # something after the first slash
    "Has a query string": r"^[^#]*\?",
}


def is_bare_homepage(url: str) -> bool:
    """True if url is https://www.<domain>, optionally ending in one slash."""
    return re.match(BARE_HOMEPAGE, url, flags=re.IGNORECASE) is not None


def _has_shape(urls: pd.Series, pattern: str) -> pd.Series:
    return urls.str.contains(pattern, case=False, regex=True)


def url_shape_by_class(rows: pd.DataFrame) -> pd.DataFrame:
    """Percentage of each class's URLs that have each shape. One row per shape."""
    legitimate, phishing = split_by_class(rows)
    table = {
        shape: {
            "Legitimate (%)": _has_shape(legitimate[URL_COLUMN], pattern).mean() * 100,
            "Phishing (%)": _has_shape(phishing[URL_COLUMN], pattern).mean() * 100,
        }
        for shape, pattern in URL_SHAPES.items()
    }
    return pd.DataFrame.from_dict(table, orient="index")


def bare_homepage_rule_accuracy(rows: pd.DataFrame) -> float:
    """Accuracy of the rule "bare homepage means legitimate, anything else means phishing"."""
    split_by_class(rows)
    predicted_legitimate = _has_shape(rows[URL_COLUMN], BARE_HOMEPAGE)
    actually_legitimate = rows[LABEL_COLUMN] == LEGITIMATE
    return float((predicted_legitimate == actually_legitimate).mean())

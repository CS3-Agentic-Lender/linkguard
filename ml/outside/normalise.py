"""Write a link in one standard form, so two ways of writing the same link compare equal.

The outside test set is compared with PhiUSIIL, and with itself, after removing the scheme,
a leading www. and a trailing slash. Nothing else changes: the path and query stay as written.
"""

import re

_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
_LEADING_WWW = re.compile(r"^www\.", re.IGNORECASE)


def normalise(link: str) -> str:
    """The link without its scheme, a leading www. or a trailing slash."""
    text = _SCHEME.sub("", link.strip())
    text = _LEADING_WWW.sub("", text)
    return text.rstrip("/")

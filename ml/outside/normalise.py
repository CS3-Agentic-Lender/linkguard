"""Write a link in one standard form, so two ways of writing the same link compare equal.

The outside test set is compared with PhiUSIIL, and with itself, after removing the scheme,
a leading www. and a trailing slash. Host names are not case sensitive, so the host is
lowercased. Nothing else changes: the path and query stay as written, because they can be.
"""

import re

_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
_LEADING_WWW = re.compile(r"^www\.", re.IGNORECASE)
# The host runs up to the first /, ? or #.
_HOST = re.compile(r"^[^/?#]*")


def normalise(link: str) -> str:
    """The link without its scheme, a leading www. or a trailing slash, with the host in lowercase."""
    text = _SCHEME.sub("", link.strip())
    text = _HOST.sub(lambda host: host.group().lower(), text, count=1)
    text = _LEADING_WWW.sub("", text)
    return text.rstrip("/")

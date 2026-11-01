from dataclasses import dataclass
from ipaddress import ip_address
import re
from urllib.parse import urlsplit


EMPTY_LINK = "Paste a link first"
LONG_LINK = "That link is too long to check. Links over 2,000 characters can't be checked."
INVALID_LINK = "That doesn't look like a web address. It usually starts with www. or https://"


@dataclass(frozen=True)
class CleanedLink:
    url: str
    added_https: bool


def clean_link(text: str) -> CleanedLink:
    """Clean pasted text without opening the link or looking up its host."""
    cleaned = text.strip().replace("\r", "").replace("\n", "")
    wrappers = {"<": ">", '"': '"', "'": "'", "“": "”", "‘": "’"}
    while len(cleaned) > 1 and wrappers.get(cleaned[0]) == cleaned[-1]:
        cleaned = cleaned[1:-1]
    cleaned = cleaned.rstrip(".,;:!?\"'”’")
    if not cleaned:
        raise ValueError(EMPTY_LINK)

    added_https = not cleaned.lower().startswith(("http://", "https://"))
    other_scheme = added_https and (
        "://" in cleaned
        or (
            re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", cleaned)
            and not re.match(r"^[^:/?#]+:\d+(?:[/?#]|$)", cleaned)
        )
    )
    if added_https:
        cleaned = "https://" + cleaned

    if len(cleaned) > 2000:
        raise ValueError(LONG_LINK)

    try:
        # An explicit non-web scheme must not become part of a new host.
        if other_scheme:
            raise ValueError
        parsed = urlsplit(cleaned)
        host = parsed.hostname
        # Accessing port also rejects malformed or out-of-range port text.
        _ = parsed.port
        if parsed.scheme.lower() not in {"http", "https"} or not host:
            raise ValueError
        if any(character.isspace() for character in cleaned):
            raise ValueError
        try:
            ip_address(host)
        except ValueError:
            labels = host.encode("idna").decode("ascii").rstrip(".").split(".")
            if len(labels) < 2 or not all(
                re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
                for label in labels
            ):
                raise ValueError
    except (ValueError, UnicodeError):
        raise ValueError(INVALID_LINK) from None

    return CleanedLink(url=cleaned, added_https=added_https)

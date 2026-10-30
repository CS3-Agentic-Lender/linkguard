"""Ten hostname features for a pasted link, shared by training and live scans.

The features only read the text of the link. Nothing is opened, fetched, resolved
or looked up, so checking a link never contacts the site it points to.
"""

import ipaddress
import re
import string
from urllib.parse import urlsplit

FEATURE_NAMES: tuple[str, ...] = (
    "HostnameLength",
    "IsDomainIP",
    "TLDLength",
    "NoOfSubDomain",
    "NoOfLettersInHostname",
    "LetterRatioInHostname",
    "NoOfDigitsInHostname",
    "DigitRatioInHostname",
    "NoOfSpecialCharsInHostname",
    "SpecialCharRatioInHostname",
)

EMPTY_LINK_MESSAGE = "The link is empty. Paste a link to check."
UNREADABLE_LINK_MESSAGE = "The link could not be read as a web address."
NO_HOST_MESSAGE = "The link has no host name to check."
SPACE_IN_HOST_MESSAGE = "The host name contains a space."
BAD_HOST_MESSAGE = "The host name is not valid."

SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
WHITESPACE_PATTERN = re.compile(r"\s")
WWW_PREFIX = "www."
LETTERS = frozenset(string.ascii_lowercase)
DIGITS = frozenset(string.digits)


def _is_ip_address(host: str) -> bool:
    """True if host is an IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _normalized_host(link: str) -> tuple[str, bool]:
    """Return the host to measure and whether it is an IP address."""
    text = link.strip()
    if not text:
        raise ValueError(EMPTY_LINK_MESSAGE)
    # Without a scheme, urlsplit would read the whole link as a path. The // makes
    # the first part of the link the host.
    if not SCHEME_PATTERN.match(text):
        text = "//" + text
    try:
        host = urlsplit(text).hostname
    except ValueError as error:
        raise ValueError(UNREADABLE_LINK_MESSAGE) from error
    if not host:
        raise ValueError(NO_HOST_MESSAGE)
    if WHITESPACE_PATTERN.search(host):
        raise ValueError(SPACE_IN_HOST_MESSAGE)
    # A trailing dot is the DNS root, not part of the name, so it goes first.
    host = host.removesuffix(".").removeprefix(WWW_PREFIX)
    if not host:
        raise ValueError(NO_HOST_MESSAGE)
    if _is_ip_address(host):
        return host, True
    # The IDNA codec turns non-English names into ASCII (xn--...), so they are
    # measured the way DNS sees them.
    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise ValueError(BAD_HOST_MESSAGE) from error
    return ascii_host, False


def extract_features(link: str) -> dict[str, int | float]:
    """Return the ten hostname features of link, keyed by FEATURE_NAMES in order."""
    host, is_ip = _normalized_host(link)
    if is_ip:
        top_level_length = 0
        subdomains = 0
    else:
        labels = host.split(".")
        top_level_length = len(labels[-1])
        # The last two parts are the name and its ending; anything before them is a
        # subdomain. max() keeps a short name at 0 instead of going negative.
        subdomains = max(len(labels) - 2, 0)
    length = len(host)
    letters = sum(1 for character in host if character in LETTERS)
    digits = sum(1 for character in host if character in DIGITS)
    # Everything that is not a letter or digit: dots, hyphens and IPv6 colons.
    special = length - letters - digits
    return {
        "HostnameLength": length,
        "IsDomainIP": int(is_ip),
        "TLDLength": top_level_length,
        "NoOfSubDomain": subdomains,
        "NoOfLettersInHostname": letters,
        "LetterRatioInHostname": letters / length,
        "NoOfDigitsInHostname": digits,
        "DigitRatioInHostname": digits / length,
        "NoOfSpecialCharsInHostname": special,
        "SpecialCharRatioInHostname": special / length,
    }

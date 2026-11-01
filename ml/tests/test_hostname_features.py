import os
import re
import socket
from pathlib import Path

import pytest

from features.hostname import FEATURE_NAMES, extract_features
from leakage.excluded import EXCLUDED_FEATURES

# Made-up links, only ever handled as text.

CONTRACT_NAMES = (
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
RATIO_NAMES = ("LetterRatioInHostname", "DigitRatioInHostname", "SpecialCharRatioInHostname")
COUNT_NAMES = tuple(name for name in CONTRACT_NAMES if name not in RATIO_NAMES)

# Full-URL features the first model drops. The hostname features must not bring them back.
DROPPED_FULL_URL_NAMES = (
    "URLLength",
    "DomainLength",
    "NoOfLettersInURL",
    "LetterRatioInURL",
    "NoOfDegitsInURL",
    "DegitRatioInURL",
    "NoOfEqualsInURL",
    "NoOfQMarkInURL",
    "NoOfAmpersandInURL",
    "NoOfOtherSpecialCharsInURL",
    "SpacialCharRatioInURL",
    "IsHTTPS",
    "CharContinuationRate",
    "HasObfuscation",
    "NoOfObfuscatedChar",
    "ObfuscationRatio",
)

# The same link and values are checked in backend/tests/test_shared_features.py.
# Host is login.shop.example.co.uk: 5 + 4 + 7 + 2 + 2 = 20 letters, 4 dots, 24 characters.
# The port (8443) and the query (id=7) are not part of the host, so no digits count.
SHARED_LINK = "https://login.shop.example.co.uk:8443/verify?id=7"
SHARED_EXPECTED = {
    "HostnameLength": 24,
    "IsDomainIP": 0,
    "TLDLength": 2,
    "NoOfSubDomain": 3,
    "NoOfLettersInHostname": 20,
    "LetterRatioInHostname": 20 / 24,
    "NoOfDigitsInHostname": 0,
    "DigitRatioInHostname": 0.0,
    "NoOfSpecialCharsInHostname": 4,
    "SpecialCharRatioInHostname": 4 / 24,
}


def expected_features(length, is_ip, tld, sub, letters, digits, special):
    """Hand-counted values in, the ten-feature dict out. Ratios are count / length."""
    assert letters + digits + special == length
    return {
        "HostnameLength": length,
        "IsDomainIP": is_ip,
        "TLDLength": tld,
        "NoOfSubDomain": sub,
        "NoOfLettersInHostname": letters,
        "LetterRatioInHostname": letters / length,
        "NoOfDigitsInHostname": digits,
        "DigitRatioInHostname": digits / length,
        "NoOfSpecialCharsInHostname": special,
        "SpecialCharRatioInHostname": special / length,
    }


def assert_features(actual, expected):
    assert list(actual) == list(expected)
    for name, want in expected.items():
        if name in RATIO_NAMES:
            assert actual[name] == pytest.approx(want), name
        else:
            assert actual[name] == want, name


VALID_LINKS = [
    pytest.param("https://example.com", id="no-path"),
    pytest.param("https://example.com/a/b/c.html", id="path"),
    pytest.param("https://example.com/search?q=1&x=2", id="query-string"),
    pytest.param("https://example.com/page#section", id="fragment"),
    pytest.param("http://10.0.0.1/login", id="ipv4"),
    pytest.param("http://192.168.0.1:8080/", id="ipv4-with-port"),
    pytest.param("http://[::1]/", id="ipv6-loopback"),
    pytest.param("http://[fd00::1234]:8080/path", id="ipv6-with-port"),
    pytest.param("https://example.com:8443/", id="port"),
    pytest.param("example.com:8080", id="no-scheme-with-port"),
    pytest.param("example.com/path", id="no-scheme"),
    pytest.param("//example.com/path", id="protocol-relative"),
    pytest.param("//WWW.Example.com:8080/x", id="protocol-relative-noisy"),
    pytest.param("https://user:pw@example.com/", id="user-part"),
    pytest.param("https://example.com@login.test/", id="at-sign-before-real-host"),
    pytest.param("https://example.com/%41%2e%2e/", id="percent-escapes"),
    pytest.param("https://example.com/~user/", id="tilde"),
    pytest.param("https://bücher.de/", id="german-letters"),
    pytest.param("https://пример.test/", id="cyrillic"),
    pytest.param("https://例え.test/", id="japanese"),
    pytest.param("https://example.com/" + "a" * 1500, id="1500-character-path"),
    pytest.param("https://www.", id="www-dot-only"),
]


@pytest.mark.parametrize("link", VALID_LINKS)
def test_valid_links_return_all_ten_features(link):
    features = extract_features(link)

    assert tuple(features) == CONTRACT_NAMES
    assert all(isinstance(value, (int, float)) for value in features.values())


@pytest.mark.parametrize("link", VALID_LINKS)
def test_counts_add_up_and_ratios_are_count_over_length(link):
    features = extract_features(link)
    length = features["HostnameLength"]

    assert length > 0
    assert (
        features["NoOfLettersInHostname"]
        + features["NoOfDigitsInHostname"]
        + features["NoOfSpecialCharsInHostname"]
        == length
    )
    assert features["LetterRatioInHostname"] == pytest.approx(features["NoOfLettersInHostname"] / length)
    assert features["DigitRatioInHostname"] == pytest.approx(features["NoOfDigitsInHostname"] / length)
    assert features["SpecialCharRatioInHostname"] == pytest.approx(features["NoOfSpecialCharsInHostname"] / length)
    assert features["IsDomainIP"] in (0, 1)


@pytest.mark.parametrize(
    "link",
    [
        "https://example.com/a/b/c.html",
        "https://example.com/search?q=1&x=2",
        "https://example.com/page#section",
        "https://example.com:8443/",
        "https://example.com/%41%2e%2e/",
        "https://example.com/~user/",
        "https://example.com/café?q=ü",
        "https://example.com/" + "a" * 1500,
    ],
)
def test_nothing_after_the_host_changes_the_features(link):
    assert extract_features(link) == extract_features("https://example.com")


def test_the_host_is_the_part_after_the_at_sign():
    # login.test is 5 + 1 + 4 = 10 characters: 9 letters and one dot.
    features = extract_features("https://example.com@login.test/")

    assert_features(features, expected_features(10, 0, 4, 0, 9, 0, 1))


@pytest.mark.parametrize("link", ["http://10.0.0.1/login", "http://192.168.0.1:8080/", "http://[::1]/", "http://[fd00::1234]:8080/path"])
def test_ip_hosts_have_no_tld_and_no_subdomains(link):
    features = extract_features(link)

    assert features["IsDomainIP"] == 1
    assert features["TLDLength"] == 0
    assert features["NoOfSubDomain"] == 0


@pytest.mark.parametrize("link", ["https://bücher.de/", "https://пример.test/", "https://例え.test/"])
def test_non_english_hosts_are_counted_in_their_ascii_form(link):
    features = extract_features(link)

    # The ascii form starts xn--, so it has two hyphens and a dot at the least.
    assert features["IsDomainIP"] == 0
    assert features["NoOfSpecialCharsInHostname"] >= 3
    assert features["NoOfLettersInHostname"] > 0


@pytest.mark.parametrize(
    "link",
    [
        "",
        "   ",
        " \t\r\n ",
        "https://",
        "http:///path",
        "https://.",
        "https://..",
        "https://www..",
        "https://a..b.com",
        "https://example.com..",
        "example.com..",
        "http://1.2.3.4..",
        "http://[::1",
        "https://exa mple.com/",
        "https://" + "a" * 64 + ".com",
    ],
)
def test_broken_links_raise_value_error_with_a_message(link):
    with pytest.raises(ValueError) as error:
        extract_features(link)

    assert str(error.value).strip()


def test_output_keys_equal_the_feature_names_in_order():
    assert tuple(extract_features("https://example.com")) == FEATURE_NAMES
    assert tuple(extract_features("http://[::1]/")) == FEATURE_NAMES


def test_feature_names_are_the_ten_in_the_contract():
    assert FEATURE_NAMES == CONTRACT_NAMES


def test_counts_are_ints_and_ratios_are_floats():
    for link in ("https://example.com", "http://10.0.0.1/", "https://bücher.de/"):
        features = extract_features(link)

        for name in COUNT_NAMES:
            # type() rather than isinstance(): a bool would pass isinstance(..., int).
            assert type(features[name]) is int, (link, name)
        for name in RATIO_NAMES:
            assert type(features[name]) is float, (link, name)


def test_no_excluded_feature_is_in_the_output():
    output = set(extract_features("https://example.com"))

    assert output.isdisjoint(EXCLUDED_FEATURES)
    assert set(FEATURE_NAMES).isdisjoint(EXCLUDED_FEATURES)


def test_no_dropped_full_url_feature_is_in_the_output():
    output = set(extract_features("https://example.com/login?id=1"))

    assert output.isdisjoint(DROPPED_FULL_URL_NAMES)
    assert set(FEATURE_NAMES).isdisjoint(DROPPED_FULL_URL_NAMES)


@pytest.fixture
def no_network(monkeypatch):
    """Fail the test if anything tries to open a connection or look up a name."""
    attempts = []

    def blocked(name):
        def refuse(*args, **kwargs):
            attempts.append(name)
            raise AssertionError(f"a network call was attempted: {name}")

        return refuse

    monkeypatch.setattr(socket.socket, "connect", blocked("connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", blocked("connect_ex"))
    monkeypatch.setattr(socket, "getaddrinfo", blocked("getaddrinfo"))
    monkeypatch.setattr(socket, "create_connection", blocked("create_connection"))
    return attempts


def test_extractor_never_touches_the_network(no_network):
    links = ["https://example.com/login", "http://10.0.0.1/", "http://[::1]/", "https://bücher.de/", SHARED_LINK]

    for link in links:
        assert tuple(extract_features(link)) == FEATURE_NAMES
    with pytest.raises(ValueError):
        extract_features("https://a..b.com")

    assert no_network == []


def test_network_block_catches_a_connection(no_network):
    # Proves the fixture above really blocks, so the test before it would fail
    # if the extractor ever looked the host up.
    with pytest.raises(AssertionError, match="network call"):
        socket.create_connection(("example.com", 443))
    with pytest.raises(AssertionError, match="network call"):
        socket.getaddrinfo("example.com", 443)


def test_noisy_link_gives_the_same_features_as_the_plain_domain():
    noisy = "HTTP://User:pw@WWW.Example.COM.:8080/a/b?q=1#top"

    assert extract_features(noisy) == extract_features("example.com")


def test_only_one_leading_www_is_removed():
    # The host becomes www.example.com: 13 letters, 2 dots, 15 characters, 1 subdomain.
    features = extract_features("www.www.example.com")

    assert_features(features, expected_features(15, 0, 3, 1, 13, 0, 2))
    assert features != extract_features("example.com")


def test_one_leading_www_is_removed_with_or_without_a_scheme():
    plain = extract_features("example.com")

    assert extract_features("www.example.com") == plain
    assert extract_features("https://www.example.com") == plain
    assert extract_features("https://WWW.EXAMPLE.COM") == plain


def test_one_trailing_dot_is_removed():
    plain = extract_features("example.com")

    assert extract_features("https://example.com./") == extract_features("https://example.com/")
    # One dot is fine. Two are refused (see the broken links above), not read as one.
    assert extract_features("https://example.com.") == plain
    assert extract_features("example.com.") == plain


@pytest.mark.parametrize("link", ["//example.com/path", "//WWW.Example.com:8080/x", "//example.com"])
def test_protocol_relative_links_give_the_same_features_as_the_plain_domain(link):
    # A link that already starts with // must not get a second // put in front of it.
    assert extract_features(link) == extract_features("example.com")


@pytest.mark.parametrize("path", ["", "/", "/login", "/login?id=1", ":8080/login"])
def test_http_and_https_give_the_same_features(path):
    assert extract_features("http://shop.example.co.uk" + path) == extract_features("https://shop.example.co.uk" + path)


@pytest.mark.parametrize(
    ("link", "expected"),
    [
        # example.com: 10 letters and 1 dot.
        ("https://www.example.com", expected_features(11, 0, 3, 0, 10, 0, 1)),
        ("HTTP://User:pw@WWW.Example.COM.:8080/a/b?q=1#top", expected_features(11, 0, 3, 0, 10, 0, 1)),
        ("example.com", expected_features(11, 0, 3, 0, 10, 0, 1)),
        # 192.168.0.1: 3 + 3 + 1 + 1 = 8 digits and 3 dots.
        ("http://192.168.0.1/login", expected_features(11, 1, 0, 0, 0, 8, 3)),
        # ::1: one digit and two colons.
        ("http://[::1]:80/", expected_features(3, 1, 0, 0, 0, 1, 2)),
        # shop.example.co.uk: 4 + 7 + 2 + 2 = 15 letters and 3 dots.
        ("https://shop.example.co.uk", expected_features(18, 0, 2, 2, 15, 0, 3)),
        # xn--bcher-kva.de: 12 letters, a dot and three hyphens (xn, bcher and kva joined).
        ("https://bücher.de/", expected_features(16, 0, 2, 0, 12, 0, 4)),
    ],
)
def test_worked_examples(link, expected):
    assert_features(extract_features(link), expected)


def test_example_dot_com_ratios():
    features = extract_features("example.com")

    assert features["LetterRatioInHostname"] == pytest.approx(10 / 11)
    assert features["DigitRatioInHostname"] == 0.0
    assert features["SpecialCharRatioInHostname"] == pytest.approx(1 / 11)


def test_https_www_dot_is_valid_and_keeps_www():
    # The trailing dot goes first, leaving www, which has no www. in front to remove.
    assert_features(extract_features("https://www."), expected_features(3, 0, 3, 0, 3, 0, 0))


def test_shared_link_matches_the_hand_computed_features():
    assert extract_features(SHARED_LINK) == SHARED_EXPECTED


DEFINITION = re.compile(r"^[ \t]*def[ \t]+extract_features[ \t]*\(", re.MULTILINE)


def test_there_is_exactly_one_copy_of_the_extractor():
    root = Path(__file__).resolve().parents[2]
    skipped = {"node_modules", ".venv"}
    found = []

    for folder, subfolders, files in os.walk(root):
        subfolders[:] = [name for name in subfolders if name not in skipped and not name.startswith(".")]
        for file in files:
            if not file.endswith(".py"):
                continue
            path = Path(folder) / file
            text = path.read_text(encoding="utf-8", errors="replace")
            found.extend([path] * len(DEFINITION.findall(text)))

    assert found == [root / "ml" / "features" / "hostname.py"]

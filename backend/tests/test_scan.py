import re
import socket

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.links import EMPTY_LINK, INVALID_LINK, LONG_LINK, clean_link

client = TestClient(app)

# Made-up link on a reserved name. It is only ever handled as text.
LINK = "https://login.example/verify?account=1"


LOOPBACK = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture
def no_network(monkeypatch):
    """Fail the test if anything tries to open an outgoing connection.

    Loopback is still allowed: on Windows the event loop that runs the test
    client connects a socket to itself on 127.0.0.1 when it starts.
    """
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def check(host):
        if host not in LOOPBACK:
            raise AssertionError(f"a network connection was attempted to {host}")

    def connect(sock, address):
        check(address[0])
        return real_connect(sock, address)

    def connect_ex(sock, address):
        check(address[0])
        return real_connect_ex(sock, address)

    def getaddrinfo(host, *args, **kwargs):
        check(host)
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


def test_replies_with_the_placeholder_shape():
    response = client.post("/scan", json={"url": LINK})

    assert response.status_code == 200
    assert response.json() == {
        "url": LINK,
        "risk_level": None,
        "score": None,
        "reasons": [],
        "placeholder": True,
    }


def test_never_fetches_the_link(no_network):
    response = client.post("/scan", json={"url": LINK})

    assert response.status_code == 200


def test_network_block_catches_a_fetch(no_network):
    # Proves the fixture above really blocks connections, so the test
    # before it would fail if /scan ever fetched the link.
    with pytest.raises(AssertionError, match="network connection"):
        socket.create_connection(("login.example", 443))


def test_missing_url_gets_a_clear_422():
    response = client.post("/scan", json={})

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "url"]
    assert error["type"] == "missing"


@pytest.mark.parametrize("pasted_text", ["", "   ", " \t\r\n "])
def test_empty_input_gets_the_paste_link_error(pasted_text, no_network):
    response = client.post("/scan", json={"url": pasted_text})

    assert response.status_code == 400
    assert response.json() == {"error": "Paste a link first"}


@pytest.mark.parametrize(
    ("pasted", "expected", "added_https"),
    [
        (" example.com/page. \n", "https://example.com/page", True),
        ("<https://example.com/login>", "https://example.com/login", False),
        ('"https://example.com/login"', "https://example.com/login", False),
        ("https://exam\r\nple.com/path", "https://example.com/path", False),
        ("www.example.com/path", "https://www.example.com/path", True),
        ("http://example.com/path?q=1", "http://example.com/path?q=1", False),
        ("https://127.0.0.1/path", "https://127.0.0.1/path", False),
        ("https://[::1]/path", "https://[::1]/path", False),
        ("https://éxample.com/path", "https://éxample.com/path", False),
        ("example.com:8080/path", "https://example.com:8080/path", True),
    ],
)
def test_clean_link_examples(pasted, expected, added_https, no_network):
    cleaned = clean_link(pasted)

    assert cleaned.url == expected
    assert cleaned.added_https is added_https
    response = client.post("/scan", json={"url": pasted})
    assert response.status_code == 200
    assert response.json()["url"] == expected
    assert response.json()["placeholder"] is True


@pytest.mark.parametrize(
    ("pasted", "message"),
    [
        ('""', EMPTY_LINK),
        ("<>", EMPTY_LINK),
        ("hello there", INVALID_LINK),
        ("https://", INVALID_LINK),
        ("https://localhost/path", INVALID_LINK),
        ("ftp://example.com/file", INVALID_LINK),
        ("javascript:example.com", INVALID_LINK),
        ("custom:person@example.com", INVALID_LINK),
        ("mailto:person@example.com", INVALID_LINK),
        ("https://[broken", INVALID_LINK),
        ("https://example.com:wrong/path", INVALID_LINK),
        ("https://example.com:70000/path", INVALID_LINK),
        ("https://-bad.example/path", INVALID_LINK),
        ("https://example.com/" + "x" * 2000, LONG_LINK),
        ("ftp://example.com/" + "x" * 2000, LONG_LINK),
    ],
)
def test_invalid_links_return_only_the_agreed_error(pasted, message, no_network):
    with pytest.raises(ValueError, match=re.escape(message)):
        clean_link(pasted)

    response = client.post("/scan", json={"url": pasted})
    assert response.status_code == 400
    assert response.json() == {"error": message}


def test_length_limit_uses_the_cleaned_link(no_network):
    prefix = "https://example.com/"
    exactly_2000 = prefix + "x" * (2000 - len(prefix))

    assert client.post("/scan", json={"url": exactly_2000}).status_code == 200
    assert client.post("/scan", json={"url": " <" + exactly_2000 + "> \n"}).status_code == 200
    rejected = client.post("/scan", json={"url": exactly_2000 + "x"})
    assert rejected.status_code == 400
    assert rejected.json() == {"error": LONG_LINK}

    # The automatically added scheme counts toward the same final limit.
    assert client.post("/scan", json={"url": exactly_2000[8:]}).status_code == 200
    assert client.post("/scan", json={"url": exactly_2000[8:] + "x"}).json() == {"error": LONG_LINK}

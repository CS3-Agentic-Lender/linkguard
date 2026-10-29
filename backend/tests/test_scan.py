import socket

import pytest
from fastapi.testclient import TestClient

from app.main import app

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

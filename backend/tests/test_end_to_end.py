"""End-to-end tests: the real server, started on a free port, called over HTTP.

The other tests call the app in-process. These start uvicorn as the backend really runs,
with the fixture model, scaler and cut-offs, and send real HTTP requests to it, so the
whole path is covered: start-up, the cut-offs, the model, the reply and its JSON.

Each acceptance criterion of the risk-level story has a named test:
1. the reply holds a level, a score and placeholder false: the tests in this file
2. scores at and either side of each cut-off: tests/test_risk.py,
   test_scores_at_and_either_side_of_each_cutoff
3. the cut-offs come from the file: tests/test_risk.py,
   test_changing_the_file_changes_the_level_without_a_code_change
4. under 2 seconds on a laptop with the real model: scripts/timing_run.py (not in CI)
"""

import socket
import threading
import time

import httpx
import pytest
import uvicorn

from app.main import app

LEVELS = {"Safe", "Suspicious", "High risk"}

# Made-up links on reserved names and documentation addresses, only ever handled as text.
# With the fixture model and the agreed cut-offs, the first is Safe and the second High risk.
SAFE_LINK = "https://login.example/verify"
HIGH_RISK_LINK = "https://paypa1-support-2024.example/verify"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def server(fixture_model_dir):
    """The backend running for real on 127.0.0.1, as uvicorn starts it."""
    port = free_port()
    running = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=running.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    while not running.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError("The backend did not start.")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    running.should_exit = True
    thread.join(timeout=10)


def scan_over_http(server, link):
    return httpx.post(f"{server}/scan", json={"url": link}, timeout=10)


@pytest.mark.parametrize(("link", "level"), [(SAFE_LINK, "Safe"), (HIGH_RISK_LINK, "High risk")])
def test_a_valid_link_gets_a_level_a_score_and_no_placeholder(server, link, level):
    response = scan_over_http(server, link)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    reply = response.json()
    assert list(reply) == ["url", "risk_level", "score", "reasons", "placeholder"]
    assert reply["url"] == link
    assert reply["risk_level"] in LEVELS
    assert reply["risk_level"] == level
    assert isinstance(reply["score"], float)
    assert 0 <= reply["score"] <= 1
    assert reply["placeholder"] is False


def test_the_same_link_gets_the_same_answer_every_time(server):
    replies = [scan_over_http(server, HIGH_RISK_LINK).json() for _ in range(3)]

    assert replies[0] == replies[1] == replies[2]


def test_a_link_pasted_without_https_is_cleaned_then_scored(server):
    reply = scan_over_http(server, "  paypa1-support-2024.example/verify. ").json()

    assert reply["url"] == HIGH_RISK_LINK
    assert reply["risk_level"] in LEVELS


def test_text_that_is_not_a_link_gets_its_error_over_http(server):
    response = scan_over_http(server, "hello there")

    assert response.status_code == 400
    assert response.json() == {"error": "That doesn't look like a web address. It usually starts with www. or https://"}


def test_scoring_over_http_never_opens_the_link(server, no_network):
    # no_network only lets the test talk to its own server on 127.0.0.1.
    assert scan_over_http(server, HIGH_RISK_LINK).status_code == 200

"""Time 100 /scan calls over HTTP with the real model, on a team laptop. Not part of CI.

It starts the backend as it really runs (uvicorn on 127.0.0.1, loading ml/models/ or
LINKGUARD_MODEL_DIR), sends one warm-up scan that isn't counted, then sends the 20 sample
links below 5 times each: 100 scans. Each time is measured from sending the request to
having the whole reply. It prints a Markdown summary to paste into the sprint folder.

The run passes only when both hold: the p95 is under 2 seconds (the end-to-end tests
ticket) and every single scan is under 2 seconds (the risk-level story).

The links are only ever sent as text to the backend on 127.0.0.1: it never opens or
looks them up, and neither does this script.

Run from backend/:  uv run python -m scripts.timing_run
"""

import math
import platform
import statistics
import sys
import time
from collections import Counter

import httpx

from scripts.local_server import running_backend

LIMIT_SECONDS = 2.0
ROUNDS = 5
PERCENTILE = 0.95
REQUEST_TIMEOUT_SECONDS = 30

# A mix of plain homepages, longer links and made-up risky-looking ones, so all three
# levels come up. Some are real sites (bbc.co.uk, amazon.co.uk, google.com, mtu.ie) and
# one uses a .xyz ending anyone can register; the rest use reserved names (.example) and
# documentation addresses (192.0.2.x, 203.0.113.x, 2001:db8::) that no real site has.
# All of them are only ever sent as text to our own backend on 127.0.0.1, never opened.
SAMPLE_LINKS = [
    "https://www.bbc.co.uk",
    "https://www.amazon.co.uk",
    "https://google.com",
    "https://www.example.org/help",
    "https://example.com",
    "https://www.mtu.ie",
    "https://shop.example.net/basket/item?id=42&ref=mail",
    "https://login.shop.example.co.uk:8443/verify?id=7",
    "www.example.org/account/settings",
    "https://news.example.com/2026/11/13/story",
    "http://192.0.2.10/account/login",
    "https://[2001:db8::1]/pay",
    "https://paypa1-support-2024.example/verify",
    "https://secure-login-verify-account-update.example-bank.com.xyz",
    "https://a1b2c3d4e5.example",
    "https://login-verify-account.example.com.secure-check.example/pay",
    "https://my-bank.example.co.uk/login",
    "https://update-billing-info-now.example/confirm",
    "https://xn--exmple-cua.example/path",
    "https://203.0.113.45:8080/wp-login",
]


def p95(seconds):
    """The time 95 of the 100 scans beat: the 96th fastest of 100.

    For other counts, the fastest time that at least 95% of the scans are faster than.
    """
    ordered = sorted(seconds)
    return ordered[min(math.ceil(len(ordered) * PERCENTILE), len(ordered) - 1)]


def summarise(seconds, levels):
    """The figures for the record, from each scan's time in seconds and its risk level."""
    percentile_95 = p95(seconds)
    under_limit = sum(scan < LIMIT_SECONDS for scan in seconds)
    return {
        "scans": len(seconds),
        "median": statistics.median(seconds),
        "p95": percentile_95,
        "slowest": max(seconds),
        "under_limit": under_limit,
        "levels": dict(Counter(levels)),
        "p95_passes": percentile_95 < LIMIT_SECONDS,
        "every_scan_passes": under_limit == len(seconds),
        "passes": percentile_95 < LIMIT_SECONDS and under_limit == len(seconds),
    }


def markdown(summary):
    ms = lambda seconds: f"{seconds * 1000:.1f} ms"  # noqa: E731
    lines = [
        f"| Scans | Median | p95 | Slowest | Under {LIMIT_SECONDS:.0f} s |",
        "|---|---|---|---|---|",
        f"| {summary['scans']} | {ms(summary['median'])} | {ms(summary['p95'])} | {ms(summary['slowest'])} "
        f"| {summary['under_limit']} of {summary['scans']} |",
        "",
        "Levels: " + ", ".join(f"{level} {count}" for level, count in sorted(summary["levels"].items())),
        f"p95 {'under' if summary['p95_passes'] else 'NOT under'} {LIMIT_SECONDS:.0f} seconds; "
        f"every scan {'under' if summary['every_scan_passes'] else 'NOT under'} {LIMIT_SECONDS:.0f} seconds.",
        f"Result: {'PASS' if summary['passes'] else 'FAIL'}.",
    ]
    return "\n".join(lines)


def run():  # pragma: no cover - needs the real model files, so it isn't run in CI
    from app.main import app

    seconds, levels = [], []
    try:
        with running_backend(app) as base_url, httpx.Client(base_url=base_url, timeout=REQUEST_TIMEOUT_SECONDS) as client:
            client.post("/scan", json={"url": SAMPLE_LINKS[0]}).raise_for_status()  # warm-up, not counted
            for _ in range(ROUNDS):
                for link in SAMPLE_LINKS:
                    started = time.perf_counter()
                    response = client.post("/scan", json={"url": link})
                    response.raise_for_status()
                    seconds.append(time.perf_counter() - started)
                    levels.append(response.json()["risk_level"])
    except RuntimeError as error:
        sys.exit(str(error))

    print(f"Machine: {platform.platform()}, {platform.processor() or platform.machine()}, Python {platform.python_version()}")
    print(markdown(summarise(seconds, levels)))


if __name__ == "__main__":  # pragma: no cover
    run()

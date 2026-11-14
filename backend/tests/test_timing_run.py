import pytest

from scripts.timing_run import LIMIT_SECONDS, ROUNDS, SAMPLE_LINKS, markdown, p95, summarise


def test_the_run_is_100_scans_of_20_links():
    assert len(SAMPLE_LINKS) == 20
    assert len(set(SAMPLE_LINKS)) == 20
    assert len(SAMPLE_LINKS) * ROUNDS == 100


def test_p95_is_the_time_95_of_100_scans_beat():
    seconds = [n / 100 for n in range(1, 101)]  # 0.01 s up to 1.00 s

    assert p95(seconds) == 0.96
    assert sum(scan < p95(seconds) for scan in seconds) == 95


def test_p95_does_not_depend_on_the_order_the_scans_ran_in():
    seconds = [n / 100 for n in range(100, 0, -1)]

    assert p95(seconds) == 0.96


def test_the_run_passes_only_when_every_scan_and_the_p95_are_under_the_limit():
    fast = summarise([0.1] * 100, ["Safe"] * 100)
    one_slow_scan = summarise([0.1] * 99 + [5.0], ["Safe"] * 100)
    many_slow_scans = summarise([0.1] * 90 + [LIMIT_SECONDS] * 10, ["Safe"] * 100)

    assert fast["passes"] and fast["under_limit"] == 100
    # The risk-level story asks for every scan under 2 s, so one slow scan fails the run
    # even though its p95 is fine.
    assert one_slow_scan["p95_passes"]
    assert not one_slow_scan["every_scan_passes"]
    assert not one_slow_scan["passes"]
    assert not many_slow_scans["p95_passes"]
    assert not many_slow_scans["passes"]


def test_the_record_shows_every_figure():
    summary = summarise([0.02] * 60 + [0.05] * 40, ["Safe"] * 30 + ["Suspicious"] * 40 + ["High risk"] * 30)
    text = markdown(summary)

    assert "| 100 | 20.0 ms | 50.0 ms | 50.0 ms | 100 of 100 |" in text
    assert "High risk 30, Safe 30, Suspicious 40" in text
    assert "p95 under 2 seconds; every scan under 2 seconds." in text
    assert "Result: PASS." in text


def test_the_record_says_which_rule_failed():
    text = markdown(summarise([0.1] * 99 + [5.0], ["Safe"] * 100))

    assert "| 99 of 100 |" in text
    assert "p95 under 2 seconds; every scan NOT under 2 seconds." in text
    assert "Result: FAIL." in text


@pytest.mark.parametrize("link", SAMPLE_LINKS)
def test_every_sample_link_is_one_the_backend_accepts(client, link):
    assert client.post("/scan", json={"url": link}).status_code == 200

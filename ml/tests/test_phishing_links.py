"""Tests for collecting phishing links from the OpenPhish community feed.

No test touches the network. The feed is a made-up text answer, and urlopen is swapped for a
fake that records every address asked for. That record is how the tests show that only the
feed file is downloaded and no link in it is opened.
"""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from outside import phishing_links
from outside.normalise import normalise
from outside.phishing_links import (
    FEED_HOST,
    FEED_REPO_PATH,
    FEED_NAME,
    FEED_URL,
    MIN_LINKS,
    OUTPUT_PATH,
    CollectionError,
    check_enough,
    collect_phishing_links,
    download_feed,
    read_feed,
    site,
)

ML_DIR = Path(__file__).resolve().parent.parent
TODAY = date(2026, 11, 17)


class FakeResponse:
    def __init__(self, text: str):
        self.body = text.encode("utf-8")

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code: int):
    return phishing_links.urllib.error.HTTPError(FEED_URL, code, "error", {}, None)


@pytest.fixture
def no_waiting(monkeypatch):
    monkeypatch.setattr(phishing_links.time, "sleep", lambda seconds: None)


def feed(count: int) -> str:
    return "\n".join(f"http://login-{n}.example-bad.top/verify?id={n}" for n in range(count))


# Reading the feed


def test_read_feed_keeps_one_link_per_line():
    assert read_feed("http://a.top/x\nhttps://b.top/y\n") == ["http://a.top/x", "https://b.top/y"]


def test_read_feed_skips_blank_lines_and_trims_spaces():
    assert read_feed("\n  http://a.top/x  \n\n") == ["http://a.top/x"]


def test_read_feed_skips_a_broken_link_without_crashing():
    assert read_feed("http://[bad/x\nhttp://a.top/x") == ["http://a.top/x"]


def test_read_feed_skips_lines_that_are_not_web_links():
    assert read_feed("# comment\nftp://a.top/x\nnot a link\nhttp://b.top/y") == ["http://b.top/y"]


# Building the set (criteria 1 and 2)


def test_each_link_has_label_1_the_feed_name_and_the_date():
    links = collect_phishing_links(["http://a.top/x"], phiusiil_urls=[], collected_on=TODAY)
    assert list(links.columns) == ["url", "label", "source", "collected_on"]
    assert links.iloc[0].to_dict() == {
        "url": "http://a.top/x",
        "label": 1,
        "source": FEED_NAME,
        "collected_on": "2026-11-17",
    }


def test_links_already_in_phiusiil_are_removed_after_normalising():
    links = collect_phishing_links(
        ["http://www.old.top/login/", "http://new.top/login"],
        phiusiil_urls=["https://old.top/login"],
        collected_on=TODAY,
    )
    assert list(links["url"]) == ["http://new.top/login"]


def test_duplicates_are_removed_after_normalising():
    links = collect_phishing_links(
        ["http://a.top/x", "https://www.a.top/x/", "http://b.top/y"], phiusiil_urls=[], collected_on=TODAY
    )
    assert list(links["url"]) == ["http://a.top/x", "http://b.top/y"]
    assert links["url"].map(normalise).is_unique


def test_check_enough_stops_below_the_minimum():
    too_few = pd.DataFrame({"url": [f"http://x{n}.top/" for n in range(MIN_LINKS - 1)]})
    with pytest.raises(CollectionError, match=f"at least {MIN_LINKS}"):
        check_enough(too_few)


def test_check_enough_passes_at_the_minimum():
    check_enough(pd.DataFrame({"url": [f"http://x{n}.top/" for n in range(MIN_LINKS)]}))


# Downloading only the feed file (no link is opened)


def test_the_feed_is_the_only_address_ever_asked_for(monkeypatch):
    asked = []

    def fake_urlopen(request, timeout):
        asked.append(request.full_url)
        return FakeResponse(feed(3))

    monkeypatch.setattr(phishing_links, "urlopen", fake_urlopen)
    read_feed(download_feed())
    assert asked == [FEED_URL]


def test_every_download_goes_through_the_redirect_guard():
    assert phishing_links.urlopen == phishing_links._OPENER.open
    assert any(isinstance(handler, phishing_links._RefuseOtherHosts) for handler in phishing_links._OPENER.handlers)


def test_download_feed_refuses_any_other_address():
    with pytest.raises(CollectionError, match="Refusing"):
        download_feed("http://login-1.example-bad.top/verify")


def test_a_redirect_away_from_the_feed_host_is_refused():
    request = phishing_links.urllib.request.Request(FEED_URL)
    with pytest.raises(CollectionError, match="Refusing a redirect"):
        phishing_links._RefuseOtherHosts().redirect_request(request, None, 302, "Found", {}, "http://evil.top/")


def test_a_redirect_to_someone_elses_file_on_the_same_host_is_refused():
    request = phishing_links.urllib.request.Request(FEED_URL)
    with pytest.raises(CollectionError, match="Refusing a redirect"):
        phishing_links._RefuseOtherHosts().redirect_request(
            request, None, 302, "Found", {}, f"https://{FEED_HOST}/someone/else/main/page.html"
        )


def test_a_redirect_within_the_openphish_repository_is_followed():
    request = phishing_links.urllib.request.Request(FEED_URL)
    moved_to = f"https://{FEED_HOST}{FEED_REPO_PATH}main/feed.txt"
    moved = phishing_links._RefuseOtherHosts().redirect_request(request, None, 301, "Moved", {}, moved_to)
    assert moved.full_url == moved_to


def test_download_feed_tries_again_then_gives_up(monkeypatch, no_waiting):
    calls = []

    def busy(request, timeout):
        calls.append(1)
        raise http_error(503)

    monkeypatch.setattr(phishing_links, "urlopen", busy)
    with pytest.raises(CollectionError, match="did not answer"):
        download_feed()
    assert len(calls) == phishing_links.TRIES


def test_download_feed_does_not_wait_after_the_last_try(monkeypatch):
    waits = []
    monkeypatch.setattr(phishing_links.time, "sleep", waits.append)

    def dropped(request, timeout):
        raise ConnectionResetError("reset")

    monkeypatch.setattr(phishing_links, "urlopen", dropped)
    with pytest.raises(CollectionError):
        download_feed()
    assert len(waits) == phishing_links.TRIES - 1


def test_download_feed_succeeds_on_a_later_try(monkeypatch, no_waiting):
    answers = iter([TimeoutError("slow"), FakeResponse("http://a.top/x")])

    def flaky(request, timeout):
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(phishing_links, "urlopen", flaky)
    assert download_feed() == "http://a.top/x"


def test_a_client_error_is_not_tried_again(monkeypatch, no_waiting):
    calls = []

    def forbidden(request, timeout):
        calls.append(1)
        raise http_error(403)

    monkeypatch.setattr(phishing_links, "urlopen", forbidden)
    with pytest.raises(CollectionError, match="403"):
        download_feed()
    assert len(calls) == 1


# Saving (criterion 3: the CSV is never in the repo)


def test_the_output_is_inside_the_folder_git_ignores():
    assert OUTPUT_PATH.is_relative_to(ML_DIR / "data")


def write_phiusiil(folder: Path) -> Path:
    path = folder / "phiusiil.csv"
    pd.DataFrame({"URL": ["http://login-0.example-bad.top/verify?id=0"]}).to_csv(path, index=False)
    return path


def test_main_saves_the_csv_and_asks_only_for_the_feed(monkeypatch, tmp_path, capsys):
    asked = []

    def fake_urlopen(request, timeout):
        asked.append(request.full_url)
        return FakeResponse(feed(MIN_LINKS + 1))

    monkeypatch.setattr(phishing_links, "ML_DIR", tmp_path)
    monkeypatch.setattr(phishing_links, "PHIUSIIL_PATH", write_phiusiil(tmp_path))
    monkeypatch.setattr(phishing_links, "urlopen", fake_urlopen)
    out = tmp_path / "data" / "outside" / "phishing_links.csv"
    assert phishing_links.main(["--out", str(out)]) == 0
    assert asked == [FEED_URL]
    saved = pd.read_csv(out)
    assert len(saved) == MIN_LINKS
    assert set(saved["label"]) == {1}
    assert "Saved 200 phishing links" in capsys.readouterr().out


def test_main_stops_without_saving_when_too_few(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(phishing_links, "ML_DIR", tmp_path)
    monkeypatch.setattr(phishing_links, "PHIUSIIL_PATH", write_phiusiil(tmp_path))
    monkeypatch.setattr(phishing_links, "download_feed", lambda: feed(10))
    out = tmp_path / "data" / "outside" / "phishing_links.csv"
    assert phishing_links.main(["--out", str(out)]) == 1
    assert not out.exists()
    assert f"at least {MIN_LINKS}" in capsys.readouterr().err


def test_main_stops_when_the_dataset_is_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(phishing_links, "PHIUSIIL_PATH", tmp_path / "missing.csv")
    assert phishing_links.main([]) == 1
    assert "Get the dataset" in capsys.readouterr().err


def test_main_refuses_to_save_outside_the_ignored_data_folder(tmp_path, capsys):
    assert phishing_links.main(["--out", str(tmp_path / "phishing_links.csv")]) == 1
    assert "inside" in capsys.readouterr().err


# Keeping one site from filling the set


def test_site_is_the_last_two_parts_of_the_host():
    assert site("https://abc123.pages.dev/login") == "pages.dev"
    assert site("http://Login.Example.top/x") == "example.top"
    assert site("http://182.20.4.9/x") == "4.9"


def test_per_site_keeps_at_most_that_many_links_from_one_site():
    links = [f"https://x{n}.pages.dev/login" for n in range(5)] + ["http://a.top/x", "http://b.top/y"]
    kept = collect_phishing_links(links, phiusiil_urls=[], collected_on=TODAY, per_site=2)
    assert list(kept["url"]) == ["https://x0.pages.dev/login", "https://x1.pages.dev/login", "http://a.top/x", "http://b.top/y"]


def test_without_per_site_every_new_link_is_kept():
    links = [f"https://x{n}.pages.dev/login" for n in range(5)]
    assert len(collect_phishing_links(links, phiusiil_urls=[], collected_on=TODAY)) == 5


def test_a_repeat_does_not_use_up_a_sites_place():
    links = ["https://x0.pages.dev/a", "https://www.x0.pages.dev/a/", "https://x1.pages.dev/b"]
    kept = collect_phishing_links(links, phiusiil_urls=[], collected_on=TODAY, per_site=2)
    assert list(kept["url"]) == ["https://x0.pages.dev/a", "https://x1.pages.dev/b"]


def test_main_refuses_a_per_site_below_one(capsys):
    assert phishing_links.main(["--per-site", "0"]) == 1
    assert "--per-site" in capsys.readouterr().err

"""Tests for collecting legitimate links with paths from the Common Crawl URL index.

No test touches the network. The collector is given a fake fetch function that answers
from made-up index lines and records every address it is asked for. That record is how
the tests show that only the index is ever queried and no link in the set is opened.
"""

import json
from datetime import date
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd
import pytest

from outside import legit_links
from outside.legit_links import (
    ALLOWED_HOSTS,
    INDEX_HOST,
    MIN_LINKS,
    OUTPUT_PATH,
    CollectionError,
    check_enough,
    collect_legit_links,
    fetch,
    has_path,
    index_query_url,
    is_excluded,
    pick_links,
    read_tranco,
    urls_from_index,
)
from outside.normalise import normalise

ML_DIR = Path(__file__).resolve().parent.parent
INDEX_ID = "CC-MAIN-2026-44"
TRANCO_ID = "ABC12"
TODAY = date(2026, 11, 17)


def index_lines(*rows: tuple[str, str]) -> str:
    """Made-up Common Crawl index answer: one JSON object per line, as the real index sends."""
    return "\n".join(
        json.dumps({"url": url, "status": status, "mime": "text/html"}) for url, status in rows
    )


class FakeIndex:
    """Stands in for the network. Answers per domain and records every address asked for."""

    def __init__(self, answers: dict[str, str]):
        self.answers = answers
        self.asked: list[str] = []

    def __call__(self, address: str) -> str:
        self.asked.append(address)
        for domain, text in self.answers.items():
            if domain in address:
                return text
        return ""


# Tranco list


def test_read_tranco_returns_domains_in_rank_order():
    text = "1,google.com\n2,bbc.com\n3,rte.ie\n"
    assert read_tranco(text, top=2) == ["google.com", "bbc.com"]


def test_read_tranco_stops_on_a_page_that_is_not_the_list():
    with pytest.raises(CollectionError, match="Tranco"):
        read_tranco("<html>List not ready</html>", top=10)


def test_read_tranco_skips_blank_lines():
    assert read_tranco("1,google.com\n\n2,bbc.com\n", top=10) == ["google.com", "bbc.com"]


# Which links count


@pytest.mark.parametrize(
    ("link", "expected"),
    [
        ("https://bbc.com", False),
        ("https://bbc.com/", False),
        ("https://bbc.com/?page=2", False),
        ("https://bbc.com/news", True),
        ("https://bbc.com/news/world?page=2", True),
    ],
)
def test_has_path_needs_more_than_the_home_page(link, expected):
    assert has_path(link) is expected


@pytest.mark.parametrize(
    "domain",
    [
        "docs.google.com",
        "sites.google.com",
        "bit.ly",
        "tinyurl.com",
        "someone.github.io",
        "x.blogspot.com",
        "raw.githubusercontent.com",
        "t.me",
        "wa.me",
        "youtu.be",
    ],
)
def test_hosting_and_shortener_sites_are_excluded(domain):
    assert is_excluded(domain)


@pytest.mark.parametrize("domain", ["google.com", "bbc.com", "rte.ie", "github.com"])
def test_ordinary_sites_are_not_excluded(domain):
    assert not is_excluded(domain)


def test_every_excluded_site_has_a_reason():
    assert all(reason.strip() for reason in legit_links.EXCLUDED_DOMAINS.values())


# The index query


def test_index_query_goes_to_the_common_crawl_index_only():
    address = index_query_url(INDEX_ID, "bbc.com")
    assert urlsplit(address).hostname == INDEX_HOST == "index.commoncrawl.org"
    assert INDEX_ID in address
    assert "bbc.com" in address


def test_urls_from_index_keeps_only_pages_that_loaded():
    text = index_lines(("https://bbc.com/news", "200"), ("https://bbc.com/old", "404"))
    assert urls_from_index(text) == ["https://bbc.com/news"]


def test_urls_from_index_keeps_only_web_pages():
    text = "\n".join(
        json.dumps({"url": url, "status": "200", "mime": mime})
        for url, mime in [("https://bbc.com/news", "text/html"), ("https://bbc.com/robots.txt", "text/plain")]
    )
    assert urls_from_index(text) == ["https://bbc.com/news"]


def test_urls_from_index_ignores_blank_and_broken_lines():
    text = index_lines(("https://bbc.com/news", "200")) + "\n\nnot json\n"
    assert urls_from_index(text) == ["https://bbc.com/news"]


# Choosing links for one domain


def test_pick_links_prefers_links_with_a_query_string():
    candidates = [
        "https://bbc.com/news",
        "https://bbc.com/sport?team=cork",
        "https://bbc.com/weather",
        "https://bbc.com/search?q=rain",
    ]
    assert pick_links(candidates, per_domain=2) == [
        "https://bbc.com/sport?team=cork",
        "https://bbc.com/search?q=rain",
    ]


def test_pick_links_falls_back_to_paths_without_a_query():
    candidates = ["https://bbc.com/", "https://bbc.com/news", "https://bbc.com/sport?team=cork"]
    assert pick_links(candidates, per_domain=2) == ["https://bbc.com/sport?team=cork", "https://bbc.com/news"]


def test_pick_links_drops_two_ways_of_writing_one_link():
    candidates = ["https://www.bbc.com/news/", "http://bbc.com/news"]
    assert pick_links(candidates, per_domain=2) == ["https://www.bbc.com/news/"]


# The whole collection


def collect(fake: FakeIndex, domains: list[str], phiusiil: list[str] | None = None) -> pd.DataFrame:
    return collect_legit_links(
        domains,
        index_id=INDEX_ID,
        tranco_id=TRANCO_ID,
        fetch=fake,
        phiusiil_urls=phiusiil or [],
        collected_on=TODAY,
        per_domain=2,
        wait_seconds=0,
    )


def made_up_index() -> FakeIndex:
    return FakeIndex(
        {
            "bbc.com": index_lines(
                ("https://bbc.com/news?page=2", "200"),
                ("https://bbc.com/sport?team=cork", "200"),
                ("https://bbc.com/weather", "200"),
            ),
            "rte.ie": index_lines(("https://www.rte.ie/news/", "200"), ("https://rte.ie/player?id=9", "200")),
        }
    )


def test_collection_asks_only_the_index_and_never_opens_a_collected_link():
    fake = made_up_index()
    links = collect(fake, ["bbc.com", "rte.ie"])
    assert fake.asked, "the fake index was never asked anything"
    assert {urlsplit(address).hostname for address in fake.asked} == {INDEX_HOST}
    assert not set(links["url"]) & set(fake.asked)


def test_excluded_domains_are_never_queried():
    fake = made_up_index()
    collect(fake, ["bbc.com", "docs.google.com", "bit.ly"])
    assert not any("google" in address or "bit.ly" in address for address in fake.asked)


def test_collection_writes_label_0_with_source_and_date():
    links = collect(made_up_index(), ["bbc.com", "rte.ie"])
    assert list(links.columns) == ["url", "label", "source", "collected_on"]
    assert (links["label"] == 0).all()
    assert links["source"].str.contains(INDEX_ID).all()
    assert links["source"].str.contains(TRANCO_ID).all()
    assert (links["collected_on"] == "2026-11-17").all()


def test_collection_takes_at_most_two_links_per_domain():
    links = collect(made_up_index(), ["bbc.com", "rte.ie"])
    assert len(links) == 4
    assert links["url"].str.contains("bbc.com").sum() == 2


def test_links_already_in_phiusiil_are_removed_after_normalising():
    links = collect(made_up_index(), ["bbc.com", "rte.ie"], phiusiil=["http://bbc.com/sport?team=cork/"])
    assert normalise("https://bbc.com/sport?team=cork") not in set(links["url"].map(normalise))


def test_every_collected_link_has_a_path_and_no_duplicates():
    links = collect(made_up_index(), ["bbc.com", "rte.ie"])
    assert links["url"].map(has_path).all()
    assert links["url"].map(normalise).is_unique


# Safety and output


def test_check_enough_stops_below_the_minimum():
    assert MIN_LINKS == 200
    with pytest.raises(CollectionError, match="200"):
        check_enough(pd.DataFrame({"url": ["https://bbc.com/news"] * 199}))


def test_check_enough_passes_at_the_minimum():
    check_enough(pd.DataFrame({"url": [f"https://bbc.com/{n}" for n in range(200)]}))


def test_fetch_refuses_any_host_but_the_index_and_the_tranco_list():
    assert ALLOWED_HOSTS == {"index.commoncrawl.org", "tranco-list.eu"}
    with pytest.raises(CollectionError, match="bbc.com"):
        fetch("https://bbc.com/news")


def test_output_goes_into_the_ignored_data_folder():
    assert OUTPUT_PATH.is_relative_to(ML_DIR / "data")
    assert OUTPUT_PATH.suffix == ".csv"


# The network code, with urlopen replaced so nothing leaves the machine


class FakeResponse:
    def __init__(self, body: str):
        self.body = body.encode("utf-8")

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(address: str, code: int):
    return legit_links.urllib.error.HTTPError(address, code, "error", {}, None)


@pytest.fixture
def no_waiting(monkeypatch):
    monkeypatch.setattr(legit_links.time, "sleep", lambda seconds: None)


def test_fetch_returns_the_answer(monkeypatch):
    monkeypatch.setattr(legit_links, "urlopen", lambda request, timeout: FakeResponse("1,google.com"))
    assert fetch("https://tranco-list.eu/top-1m-id") == "1,google.com"


def test_fetch_treats_an_index_404_as_no_pages(monkeypatch):
    def not_found(request, timeout):
        raise http_error(request.full_url, 404)

    monkeypatch.setattr(legit_links, "urlopen", not_found)
    assert fetch(index_query_url(INDEX_ID, "bbc.com")) == ""


def test_fetch_tries_again_then_gives_up(monkeypatch, no_waiting):
    calls = []

    def busy(request, timeout):
        calls.append(request.full_url)
        if len(calls) % 2:
            raise http_error(request.full_url, 504)
        raise legit_links.urllib.error.URLError("timed out")

    monkeypatch.setattr(legit_links, "urlopen", busy)
    with pytest.raises(legit_links.FetchFailed, match="3 tries"):
        fetch(index_query_url(INDEX_ID, "bbc.com"))
    assert len(calls) == legit_links.TRIES


def test_fetch_succeeds_on_a_later_try(monkeypatch, no_waiting):
    answers = iter([http_error("x", 504), FakeResponse("ok")])

    def flaky(request, timeout):
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(legit_links, "urlopen", flaky)
    assert fetch(index_query_url(INDEX_ID, "bbc.com")) == "ok"


def test_a_domain_the_index_never_answers_is_skipped():
    def failing(address: str) -> str:
        if "rte.ie" in address:
            raise legit_links.FetchFailed("index.commoncrawl.org did not answer after 3 tries")
        return made_up_index()(address)

    links = collect_legit_links(
        ["rte.ie", "bbc.com"],
        index_id=INDEX_ID,
        tranco_id=TRANCO_ID,
        fetch=failing,
        phiusiil_urls=[],
        collected_on=TODAY,
        wait_seconds=0,
    )
    assert links["url"].str.contains("bbc.com").all()


def test_newest_index_skips_indexes_that_do_not_answer():
    collinfo = json.dumps([{"id": "CC-MAIN-2026-43"}, {"id": "CC-MAIN-2026-39"}, {"id": "CC-MAIN-2026-34"}])

    def answers(address: str) -> str:
        if address.endswith("collinfo.json"):
            return collinfo
        if "2026-34" in address:
            return ""
        raise legit_links.FetchFailed("busy")

    assert legit_links.newest_index(answers) == "CC-MAIN-2026-34"


def test_newest_index_stops_when_none_answer():
    def busy(address: str) -> str:
        if address.endswith("collinfo.json"):
            return json.dumps([{"id": "CC-MAIN-2026-43"}])
        raise legit_links.FetchFailed("busy")

    with pytest.raises(CollectionError, match="Try again later"):
        legit_links.newest_index(busy)


# The command


def fake_servers(domains: int) -> Callable:
    """Answers the Tranco and index addresses main() asks for, with two good links per domain."""

    def answer(address: str) -> str:
        if address.endswith("top-1m-id"):
            return TRANCO_ID + "\n"
        if "/download/" in address:
            return "\n".join(f"{rank},site{rank}.ie" for rank in range(1, domains + 1))
        domain = urlsplit(address).query.split("url=")[1].split("%2F")[0]
        return index_lines((f"https://{domain}/a?x=1", "200"), (f"https://{domain}/b?y=2", "200"))

    return answer


def test_main_saves_the_csv(monkeypatch, tmp_path, no_waiting):
    phiusiil = tmp_path / "phiusiil.csv"
    pd.DataFrame({"URL": ["https://www.site1.ie/a?x=1"]}).to_csv(phiusiil, index=False)
    monkeypatch.setattr(legit_links, "ML_DIR", tmp_path)
    monkeypatch.setattr(legit_links, "PHIUSIIL_PATH", phiusiil)
    monkeypatch.setattr(legit_links, "fetch", fake_servers(domains=101))
    out = tmp_path / "data" / "outside" / "legit_links.csv"

    assert legit_links.main(["--top", "101", "--index", INDEX_ID, "--out", str(out)]) == 0
    saved = pd.read_csv(out)
    assert len(saved) == 201
    assert "https://site1.ie/a?x=1" not in set(saved["url"])


def test_main_stops_without_saving_when_too_few(monkeypatch, tmp_path, no_waiting, capsys):
    phiusiil = tmp_path / "phiusiil.csv"
    pd.DataFrame({"URL": []}).to_csv(phiusiil, index=False)
    monkeypatch.setattr(legit_links, "ML_DIR", tmp_path)
    monkeypatch.setattr(legit_links, "PHIUSIIL_PATH", phiusiil)
    monkeypatch.setattr(legit_links, "fetch", fake_servers(domains=10))
    out = tmp_path / "data" / "legit_links.csv"

    assert legit_links.main(["--top", "10", "--index", INDEX_ID, "--out", str(out)]) == 1
    assert not out.exists()
    assert "at least 200" in capsys.readouterr().err


def test_main_stops_when_the_dataset_is_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(legit_links, "PHIUSIIL_PATH", tmp_path / "missing.csv")
    assert legit_links.main([]) == 1
    assert "Get the dataset" in capsys.readouterr().err


@pytest.mark.parametrize(
    "dropped",
    [ConnectionResetError("reset"), legit_links.http.client.RemoteDisconnected("closed"), TimeoutError("slow")],
)
def test_fetch_tries_again_after_a_dropped_connection(monkeypatch, no_waiting, dropped):
    answers = iter([dropped, FakeResponse("ok")])

    def flaky(request, timeout):
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(legit_links, "urlopen", flaky)
    assert fetch(index_query_url(INDEX_ID, "bbc.com")) == "ok"


def test_fetch_does_not_retry_an_answer_that_will_not_change(monkeypatch, no_waiting):
    calls = []

    def forbidden(request, timeout):
        calls.append(request.full_url)
        raise http_error(request.full_url, 403)

    monkeypatch.setattr(legit_links, "urlopen", forbidden)
    with pytest.raises(legit_links.FetchFailed, match="403"):
        fetch("https://tranco-list.eu/top-1m-id")
    assert len(calls) == 1


def test_fetch_does_not_wait_after_the_last_try(monkeypatch):
    waits = []
    monkeypatch.setattr(legit_links.time, "sleep", waits.append)

    def busy(request, timeout):
        raise http_error(request.full_url, 504)

    monkeypatch.setattr(legit_links, "urlopen", busy)
    with pytest.raises(legit_links.FetchFailed):
        fetch(index_query_url(INDEX_ID, "bbc.com"))
    assert len(waits) == legit_links.TRIES - 1


def redirect(to: str):
    request = legit_links.urllib.request.Request(index_query_url(INDEX_ID, "bbc.com"))
    return legit_links._RefuseOtherHosts().redirect_request(request, None, 302, "Found", {}, to)


def test_a_redirect_to_any_other_host_is_refused():
    with pytest.raises(CollectionError, match="bbc.com"):
        redirect("https://bbc.com/news")


def test_a_redirect_between_the_list_servers_is_followed():
    assert redirect("https://index.commoncrawl.org/CC-MAIN-2026-34-index").full_url.startswith("https://index.")


def test_main_refuses_to_save_outside_the_ignored_data_folder(tmp_path, capsys):
    assert legit_links.main(["--out", str(tmp_path / "legit_links.csv")]) == 1
    assert "inside" in capsys.readouterr().err

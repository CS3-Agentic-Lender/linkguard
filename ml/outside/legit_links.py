"""Collect legitimate links with paths for the outside test set, without opening any of them.

PhiUSIIL's legitimate links are all bare home pages, so the outside test needs ordinary links
with a path and, where possible, a query string. They come from two public lists:

- the Tranco list of the most visited domains (tranco-list.eu), downloaded as one file;
- the Common Crawl URL index (index.commoncrawl.org), which lists the pages a public web crawl
  saw on each domain.

The script asks the index which pages it has for each top domain. It never sends a request to
a domain or to any link it collects. fetch() refuses every host but those two list servers, and
a test checks that every address the collector asks for is on the index.

Hosting and shortener sites are skipped (EXCLUDED_DOMAINS). Anyone can put a page on them,
phishing included, so a link there is not safe to label legitimate.

Writes ml/data/outside/legit_links.csv with url, label (0 = legitimate), source and
collected_on. ml/data/ is ignored by git, so the file cannot be committed.

Run from ml/:  uv run python -m outside.legit_links
"""

import argparse
import http.client
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Sequence
from datetime import date
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import pandas as pd

from comparison.compare import RAW_CSV_NAME
from outside.normalise import normalise

ML_DIR = Path(__file__).resolve().parent.parent
PHIUSIIL_PATH = ML_DIR / "data" / RAW_CSV_NAME
OUTPUT_PATH = ML_DIR / "data" / "outside" / "legit_links.csv"

INDEX_HOST = "index.commoncrawl.org"
TRANCO_HOST = "tranco-list.eu"
ALLOWED_HOSTS = {INDEX_HOST, TRANCO_HOST}

LEGITIMATE = 0
MIN_LINKS = 200
TOP_DOMAINS = 300
PER_DOMAIN = 2
WAIT_SECONDS = 1.0
TRIES = 3
# How many index lines to read per domain. Robots files and redirects are dropped after.
INDEX_LIMIT = 200
TIMEOUT_SECONDS = 60

# Sites where anyone can host a page or a redirect. Each one has the reason it is left out.
EXCLUDED_DOMAINS = {
    "docs.google.com": "anyone can share a document or form",
    "drive.google.com": "anyone can share a file",
    "sites.google.com": "anyone can build a site",
    "forms.gle": "short links to anyone's Google form",
    "googleusercontent.com": "hosts files uploaded by users",
    "appspot.com": "anyone can host an app",
    "firebaseapp.com": "anyone can host an app",
    "web.app": "anyone can host an app",
    "amazonaws.com": "anyone can host files in a storage bucket",
    "cloudfront.net": "anyone can serve files through it",
    "azurewebsites.net": "anyone can host a site",
    "windows.net": "anyone can host files in Azure storage",
    "sharepoint.com": "anyone can share files",
    "dropbox.com": "anyone can share files",
    "github.io": "anyone can host a site",
    "gitlab.io": "anyone can host a site",
    "pages.dev": "anyone can host a site",
    "workers.dev": "anyone can host a script",
    "r2.dev": "anyone can host files",
    "netlify.app": "anyone can host a site",
    "vercel.app": "anyone can host a site",
    "herokuapp.com": "anyone can host an app",
    "blogspot.com": "anyone can start a blog",
    "wordpress.com": "anyone can start a blog",
    "wixsite.com": "anyone can build a site",
    "weebly.com": "anyone can build a site",
    "000webhostapp.com": "free hosting often used for phishing",
    "notion.site": "anyone can publish a page",
    "glitch.me": "anyone can host an app",
    "ipfs.io": "serves any file put on IPFS",
    "bit.ly": "link shortener, hides where the link goes",
    "tinyurl.com": "link shortener, hides where the link goes",
    "t.co": "link shortener, hides where the link goes",
    "goo.gl": "link shortener, hides where the link goes",
    "ow.ly": "link shortener, hides where the link goes",
    "is.gd": "link shortener, hides where the link goes",
    "cutt.ly": "link shortener, hides where the link goes",
    "rebrand.ly": "link shortener, hides where the link goes",
    "linktr.ee": "anyone can make a page of links",
    "githubusercontent.com": "serves any file uploaded to GitHub",
    "onedrive.live.com": "anyone can share files",
    "1drv.ms": "short links to anyone's OneDrive files",
    "mybluehost.me": "anyone can host a site",
    "youtu.be": "link shortener, hides where the link goes",
    "amzn.to": "link shortener, hides where the link goes",
    "lnkd.in": "link shortener, hides where the link goes",
    "t.me": "links to anyone's Telegram channel",
    "wa.me": "links to anyone's WhatsApp chat",
}

Fetch = Callable[[str], str]


class CollectionError(Exception):
    """The collection cannot go on, or would break a rule of the outside test set."""


class FetchFailed(CollectionError):
    """A list server did not answer after every try. The collector skips that domain."""


class _RefuseOtherHosts(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to one of the two list servers, so no other host gets a request."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).hostname not in ALLOWED_HOSTS:
            raise CollectionError(f"Refusing a redirect to {newurl}: only {sorted(ALLOWED_HOSTS)} may be contacted.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


urlopen = urllib.request.build_opener(_RefuseOtherHosts).open


def read_tranco(text: str, top: int) -> list[str]:
    """The first `top` domains of a Tranco list file ("rank,domain" per line), in rank order."""
    domains = []
    for line in text.splitlines():
        if not line.strip():
            continue
        rank, comma, domain = line.partition(",")
        if not comma or not rank.strip().isdigit() or not domain.strip():
            raise CollectionError(f"Unexpected line in the Tranco list: {line[:80]!r}")
        domains.append(domain.strip())
        if len(domains) == top:
            break
    return domains


def is_excluded(domain: str) -> bool:
    """True for a hosting or shortener site, or any subdomain of one."""
    domain = domain.lower()
    return any(domain == site or domain.endswith("." + site) for site in EXCLUDED_DOMAINS)


def has_path(link: str) -> bool:
    """True when the link goes further than the home page."""
    return urlsplit(link).path not in ("", "/")


def has_query(link: str) -> bool:
    return bool(urlsplit(link).query)


def index_query_url(index_id: str, domain: str) -> str:
    """The address that asks the Common Crawl index for pages it saw on one domain."""
    query = urlencode({"url": f"{domain}/*", "output": "json", "limit": INDEX_LIMIT})
    return f"https://{INDEX_HOST}/{index_id}-index?{query}"


def urls_from_index(text: str) -> list[str]:
    """The links in an index answer whose page loaded (status 200) as a web page."""
    urls = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("status") != "200":
            continue
        if row.get("mime", "text/html") != "text/html":
            continue
        urls.append(row["url"])
    return urls


def pick_links(candidates: Iterable[str], per_domain: int) -> list[str]:
    """Up to `per_domain` links with a path, links with a query string first."""
    seen = set()
    with_path = []
    for link in candidates:
        key = normalise(link)
        if key in seen or not has_path(link):
            continue
        seen.add(key)
        with_path.append(link)
    with_query = [link for link in with_path if has_query(link)]
    without_query = [link for link in with_path if not has_query(link)]
    return (with_query + without_query)[:per_domain]


def collect_legit_links(
    domains: Sequence[str],
    *,
    index_id: str,
    tranco_id: str,
    fetch: Fetch,
    phiusiil_urls: Iterable[str],
    collected_on: date,
    per_domain: int = PER_DOMAIN,
    wait_seconds: float = WAIT_SECONDS,
) -> pd.DataFrame:
    """Ask the index for each domain's pages and keep the new links that qualify.

    Only index addresses are passed to `fetch`. The collected links are never fetched.
    """
    known = {normalise(url) for url in phiusiil_urls}
    source = f"Common Crawl {index_id} index, Tranco list {tranco_id}"
    rows = []
    for domain in domains:
        if is_excluded(domain):
            continue
        try:
            answer = fetch(index_query_url(index_id, domain))
        except FetchFailed as problem:
            print(f"Skipped {domain}: {problem}", file=sys.stderr)
            continue
        candidates = [
            url
            for url in urls_from_index(answer)
            if normalise(url) not in known and not is_excluded(urlsplit(url).hostname or "")
        ]
        for link in pick_links(candidates, per_domain):
            known.add(normalise(link))
            rows.append({"url": link, "label": LEGITIMATE, "source": source, "collected_on": collected_on.isoformat()})
        if wait_seconds:
            time.sleep(wait_seconds)
    return pd.DataFrame(rows, columns=["url", "label", "source", "collected_on"])


def check_enough(links: pd.DataFrame) -> None:
    """Stop if fewer links are left than the outside test set needs."""
    if len(links) < MIN_LINKS:
        raise CollectionError(
            f"Only {len(links)} legitimate links were collected. The outside test set needs at least {MIN_LINKS}. "
            "Run again with more domains (--top)."
        )


def fetch(address: str) -> str:
    """Download one list file or index answer. Refuses any host but the two list servers.

    The index often answers 504 when busy, so a failed request is tried again. An answer of 4xx
    (other than 429, too many requests) will not change, so it is not tried again. An index
    answer of 404 means it saw no pages on that domain, which is an empty answer, not a failure.
    A redirect to any other host is refused too.
    """
    host = urlsplit(address).hostname
    if host not in ALLOWED_HOSTS:
        raise CollectionError(f"Refusing to fetch {address}: only {sorted(ALLOWED_HOSTS)} may be contacted.")
    request = urllib.request.Request(address, headers={"User-Agent": "LinkGuard outside test set collector"})
    problem = None
    for attempt in range(TRIES):
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            if error.code == 404 and host == INDEX_HOST:
                return ""
            if 400 <= error.code < 500 and error.code != 429:
                raise FetchFailed(f"{host} answered {error.code} ({error.reason})") from error
            problem = error
        except (OSError, http.client.HTTPException, UnicodeDecodeError) as error:
            # OSError covers URLError, timeouts and dropped connections.
            problem = error
        if attempt < TRIES - 1:
            time.sleep(5 * (attempt + 1))
    raise FetchFailed(f"{host} did not answer after {TRIES} tries ({problem})")


def newest_index(fetch: Fetch) -> str:
    """The newest Common Crawl index that answers. New indexes are often too busy at first."""
    indexes = json.loads(fetch(f"https://{INDEX_HOST}/collinfo.json"))
    for index in indexes[:4]:
        try:
            fetch(index_query_url(index["id"], "commoncrawl.org"))
        except FetchFailed:
            continue
        return index["id"]
    raise CollectionError("None of the four newest Common Crawl indexes answered. Try again later.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--top", type=int, default=TOP_DOMAINS, help="how many Tranco domains to ask about")
    parser.add_argument("--per-domain", type=int, default=PER_DOMAIN)
    parser.add_argument("--index", help="a Common Crawl index id, such as CC-MAIN-2026-34 (default: newest that answers)")
    parser.add_argument("--out", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args(argv)

    data_dir = ML_DIR / "data"
    if not args.out.resolve().is_relative_to(data_dir.resolve()):
        print(f"--out must be inside {data_dir}, which git ignores, so the CSV cannot be committed.", file=sys.stderr)
        return 1

    if not PHIUSIIL_PATH.exists():
        print(f"Missing {PHIUSIIL_PATH}. See 'Get the dataset' in ml/README.md.", file=sys.stderr)
        return 1
    try:
        tranco_id = fetch(f"https://{TRANCO_HOST}/top-1m-id").strip()
        domains = read_tranco(fetch(f"https://{TRANCO_HOST}/download/{tranco_id}/{args.top}"), top=args.top)
        index_id = args.index or newest_index(fetch)
        print(f"Tranco list {tranco_id}, top {len(domains)} domains. Common Crawl index {index_id}.")
        phiusiil_urls = pd.read_csv(PHIUSIIL_PATH, usecols=["URL"], encoding="utf-8-sig")["URL"]
        links = collect_legit_links(
            domains,
            index_id=index_id,
            tranco_id=tranco_id,
            fetch=fetch,
            phiusiil_urls=phiusiil_urls,
            collected_on=date.today(),
            per_domain=args.per_domain,
        )
        check_enough(links)
    except CollectionError as problem:
        print(problem, file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    links.to_csv(args.out, index=False)
    with_query = int(links["url"].map(has_query).sum())
    print(f"Saved {len(links)} legitimate links ({with_query} with a query string) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

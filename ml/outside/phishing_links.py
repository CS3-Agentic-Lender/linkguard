"""Collect recent phishing links for the outside test set, without opening any of them.

The links come from the OpenPhish community feed, a free text file with one recent phishing
link per line. openphish.com/feed.txt redirects to OpenPhish's own GitHub repository, so the
script asks that repository's file directly. The script downloads that one file and nothing else.
download_feed() refuses every other address, a redirect to another host is refused too, and no
link in the feed is ever requested.

Links already in PhiUSIIL and repeats are removed, compared after normalise() (no scheme,
leading www. or trailing slash, host in lowercase). The feed changes about every 12 hours.

One free hosting site can fill most of the feed. --per-site keeps at most that many links per
site (the last two parts of the host, such as pages.dev), so the set is less one-sided. It is
off by default, which is how the 17 Nov 2026 set was collected.

Writes ml/data/outside/phishing_links.csv with url, label (1 = phishing), source and
collected_on. ml/data/ is ignored by git, so the file cannot be committed.

Run from ml/:  uv run python -m outside.phishing_links
"""

import argparse
import http.client
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

from comparison.compare import RAW_CSV_NAME
from outside.legit_links import CollectionError
from outside.normalise import normalise

ML_DIR = Path(__file__).resolve().parent.parent
PHIUSIIL_PATH = ML_DIR / "data" / RAW_CSV_NAME
OUTPUT_PATH = ML_DIR / "data" / "outside" / "phishing_links.csv"

FEED_HOST = "raw.githubusercontent.com"
# Anyone can host a file on this host, so only OpenPhish's own repository is allowed.
FEED_REPO_PATH = "/openphish/public_feed/"
FEED_URL = f"https://{FEED_HOST}{FEED_REPO_PATH}refs/heads/main/feed.txt"
FEED_NAME = "OpenPhish community feed"

PHISHING = 1
MIN_LINKS = 200
TRIES = 3
TIMEOUT_SECONDS = 60


class _RefuseOtherHosts(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only within OpenPhish's repository, so no phishing site gets a request."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urlsplit(newurl)
        if parts.scheme != "https" or parts.hostname != FEED_HOST or not parts.path.startswith(FEED_REPO_PATH):
            raise CollectionError(f"Refusing a redirect to {newurl}: only the OpenPhish feed may be downloaded.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_RefuseOtherHosts)
urlopen = _OPENER.open


def read_feed(text: str) -> list[str]:
    """The web links in the feed file, one per line, in feed order."""
    links = []
    for line in text.splitlines():
        link = line.strip()
        try:
            parts = urlsplit(link)
            host = parts.hostname
        except ValueError:
            # A broken link, such as an unclosed [ in the host. The feed is written by attackers.
            continue
        if parts.scheme in ("http", "https") and host:
            links.append(link)
    return links


def site(link: str) -> str:
    """The last two parts of the link's host, such as pages.dev for abc.pages.dev."""
    host = (urlsplit(link).hostname or "").removesuffix(".")
    return ".".join(host.split(".")[-2:])


def collect_phishing_links(
    feed_links: Iterable[str], *, phiusiil_urls: Iterable[str], collected_on: date, per_site: int | None = None
) -> pd.DataFrame:
    """The feed links that are not in PhiUSIIL, each once, labelled phishing.

    With per_site, at most that many links are kept from any one site, in feed order.
    """
    known = {normalise(url) for url in phiusiil_urls}
    per_site_count: Counter[str] = Counter()
    rows = []
    for link in feed_links:
        key = normalise(link)
        if key in known:
            continue
        if per_site is not None and per_site_count[site(link)] >= per_site:
            continue
        known.add(key)
        per_site_count[site(link)] += 1
        rows.append({"url": link, "label": PHISHING, "source": FEED_NAME, "collected_on": collected_on.isoformat()})
    return pd.DataFrame(rows, columns=["url", "label", "source", "collected_on"])


def check_enough(links: pd.DataFrame) -> None:
    """Stop if fewer links are left than the outside test set needs."""
    if len(links) < MIN_LINKS:
        raise CollectionError(
            f"Only {len(links)} new phishing links were in the feed. The outside test set needs at least {MIN_LINKS}. "
            "The feed changes about every 12 hours, so try again later."
        )


def download_feed(address: str = FEED_URL) -> str:
    """Download the feed file. Refuses any other address, so no link in the feed is opened.

    A busy server or a dropped connection is tried again. A 4xx answer (other than 429, too many
    requests) will not change, so it is not.
    """
    if address != FEED_URL:
        raise CollectionError(f"Refusing to fetch {address}: only {FEED_URL} may be downloaded.")
    request = urllib.request.Request(address, headers={"User-Agent": "LinkGuard outside test set collector"})
    problem = None
    for attempt in range(TRIES):
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            if 400 <= error.code < 500 and error.code != 429:
                raise CollectionError(f"{FEED_HOST} answered {error.code} ({error.reason})") from error
            problem = error
        except (OSError, http.client.HTTPException, UnicodeDecodeError) as error:
            # OSError covers URLError, timeouts and dropped connections.
            problem = error
        if attempt < TRIES - 1:
            time.sleep(5 * (attempt + 1))
    raise CollectionError(f"{FEED_HOST} did not answer after {TRIES} tries ({problem})")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--per-site", type=int, default=None, help="keep at most this many links per site")
    args = parser.parse_args(argv)
    if args.per_site is not None and args.per_site < 1:
        print("--per-site must be 1 or more.", file=sys.stderr)
        return 1

    data_dir = ML_DIR / "data"
    if not args.out.resolve().is_relative_to(data_dir.resolve()):
        print(f"--out must be inside {data_dir}, which git ignores, so the CSV cannot be committed.", file=sys.stderr)
        return 1

    if not PHIUSIIL_PATH.exists():
        print(f"Missing {PHIUSIIL_PATH}. See 'Get the dataset' in ml/README.md.", file=sys.stderr)
        return 1
    try:
        feed_links = read_feed(download_feed())
        phiusiil_urls = pd.read_csv(PHIUSIIL_PATH, usecols=["URL"], encoding="utf-8-sig")["URL"]
        links = collect_phishing_links(
            feed_links, phiusiil_urls=phiusiil_urls, collected_on=date.today(), per_site=args.per_site
        )
        print(f"{FEED_NAME}: {len(feed_links)} links, {len(links)} new after removing PhiUSIIL links and repeats.")
        check_enough(links)
    except CollectionError as problem:
        print(problem, file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    links.to_csv(args.out, index=False)
    print(f"Saved {len(links)} phishing links to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

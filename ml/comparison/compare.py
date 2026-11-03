"""Compare our hostname features with the dataset's columns of the same meaning.

This is a bug check on the extractor, not an attempt to copy the dataset. Our
features are defined our own way, so some rows differ on purpose. Every
difference needs a reason, so each mismatch is sorted into a named pattern.

The leading www. is kept (strip_www=False) because the dataset's columns keep it.
URLs are only read as text. None is opened or fetched.

Run from ml/ with: uv run python -m comparison.compare
"""

import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

from features.hostname import extract_features

ML_DIR = Path(__file__).resolve().parents[1]
RAW_CSV = ML_DIR / "data" / "PhiUSIIL_Phishing_URL_Dataset.csv"
REPORT_PATH = ML_DIR / "reports" / "feature_comparison.md"
URL_COLUMN = "URL"

# Our feature -> the dataset column it is compared with.
COMPARED_COLUMNS = {
    "IsDomainIP": "IsDomainIP",
    "TLDLength": "TLDLength",
    "NoOfSubDomain": "NoOfSubDomain",
    "HostnameLength": "DomainLength",
}

DEFINITION_DIFFERENCE = "Definition difference"
SUSPECTED_BUG = "Suspected extractor bug"
DATASET_QUIRK = "Dataset quirk"
UNEXPLAINED = "Unexplained"

SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
PORT_PATTERN = re.compile(r":\d*$")
IPV4_START_PATTERN = re.compile(r"^\d{1,3}(\.\d{1,3}){3}\.")
TWO_PART_ENDING_PATTERN = re.compile(r"\.(co|com|org|net|ac|gov|edu)\.[a-z]{2}$")
# The scheme and the part up to the first /, ? or #. Every pattern is about this part.
URL_START_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*:)?(//)?[^/?#]*")
EXAMPLE_URL_LIMIT = 80


def _netloc(url: str) -> str:
    """The part between // and the first /, read the same way as the extractor reads it."""
    text = url.strip()
    if not SCHEME_PATTERN.match(text) and not text.startswith("//"):
        text = "//" + text
    return urlsplit(text).netloc


def _host_with_port(url: str) -> str:
    return _netloc(url).rpartition("@")[2]


def _host(url: str) -> str:
    return PORT_PATTERN.sub("", _host_with_port(url))


def _is_ip_host(url: str) -> bool:
    return extract_features(url, strip_www=False)["IsDomainIP"] == 1


def _starts_with_ipv4(url: str) -> bool:
    return IPV4_START_PATTERN.match(_host(url)) is not None


def _has_user_part(url: str) -> bool:
    return "@" in _netloc(url)


def _has_port(url: str) -> bool:
    return PORT_PATTERN.search(_host_with_port(url)) is not None


@dataclass(frozen=True)
class Pattern:
    name: str
    kind: str
    reason: str
    features: tuple[str, ...]  # the features this pattern can explain
    matches: Callable[[str], bool]


# Checked in this order. A mismatch goes to the first pattern that matches the URL
# and explains that feature.
PATTERNS: tuple[Pattern, ...] = (
    Pattern(
        "Host is an IP address",
        DEFINITION_DIFFERENCE,
        "The dataset reads an IP address like a name, so its last number is the TLD and the "
        "first two numbers count as subdomains. We give 0 for both.",
        ("TLDLength", "NoOfSubDomain"),
        _is_ip_host,
    ),
    Pattern(
        "Host starts with an IP address",
        DEFINITION_DIFFERENCE,
        "The dataset marks a name that starts with an IP address as an IP. We mark only a host "
        "that is an IP address.",
        ("IsDomainIP",),
        _starts_with_ipv4,
    ),
    Pattern(
        "User part in the link",
        DATASET_QUIRK,
        "The dataset's domain keeps the user:password@ part. We drop it and measure only the host.",
        ("HostnameLength", "NoOfSubDomain", "TLDLength"),
        _has_user_part,
    ),
    Pattern(
        "Port in the link",
        DATASET_QUIRK,
        "The dataset's domain keeps the port, so com:443 counts as the TLD. We drop the port.",
        ("HostnameLength", "TLDLength"),
        _has_port,
    ),
)

# Shapes we expected might cause mismatches. Each is counted to show whether it did.
SHAPES: dict[str, Callable[[str], bool]] = {
    "Leading www.": lambda url: _host(url).lower().startswith("www."),
    "Two-part ending such as .co.uk": lambda url: TWO_PART_ENDING_PATTERN.search(_host(url).lower()) is not None,
    "Non-English name (xn--)": lambda url: "xn--" in _host(url).lower() or not _host(url).isascii(),
    "Capital letters in the host": lambda url: _host(url) != _host(url).lower(),
    "Trailing dot after the host": lambda url: _host(url).endswith("."),
}


def recompute_features(urls: pd.Series) -> pd.DataFrame:
    """Our compared features for each URL, with www. kept. The index is kept."""
    rows = [extract_features(url, strip_www=False) for url in urls]
    return pd.DataFrame(rows, index=urls.index)[list(COMPARED_COLUMNS)]


def _differences(ours: pd.DataFrame, dataset: pd.DataFrame, feature: str) -> pd.Series:
    return (ours[feature] - dataset[COMPARED_COLUMNS[feature]]).abs()


def summary_table(ours: pd.DataFrame, dataset: pd.DataFrame) -> pd.DataFrame:
    """One row per compared feature: rows, exact match share and typical difference."""
    table = []
    for feature, column in COMPARED_COLUMNS.items():
        difference = _differences(ours, dataset, feature)
        different = difference[difference != 0]
        table.append(
            {
                "Our feature": feature,
                "Dataset column": column,
                "Rows compared": len(difference),
                "Exact match (%)": float((difference == 0).mean() * 100),
                "Mean absolute difference": float(difference.mean()),
                "Median absolute difference when different": float(different.median()) if len(different) else math.nan,
            }
        )
    return pd.DataFrame(table)


def find_mismatches(ours: pd.DataFrame, dataset: pd.DataFrame) -> pd.DataFrame:
    """One record per row and feature that differ, sorted by row."""
    records = [
        {"row": row, "feature": feature}
        for feature in COMPARED_COLUMNS
        for row in ours.index[_differences(ours, dataset, feature) != 0]
    ]
    return pd.DataFrame(records, columns=["row", "feature"]).sort_values(["row", "feature"], ignore_index=True)


def pattern_for(url: str, feature: str) -> str:
    """Name of the first pattern that explains this feature's mismatch, or UNEXPLAINED."""
    for pattern in PATTERNS:
        if feature in pattern.features and pattern.matches(url):
            return pattern.name
    return UNEXPLAINED


def patterns_table(mismatches: pd.DataFrame, urls: pd.Series) -> pd.DataFrame:
    """One row per pattern that has mismatches, plus the unexplained bucket, always."""
    named = mismatches.assign(
        pattern=[pattern_for(urls[row], feature) for row, feature in zip(mismatches["row"], mismatches["feature"])]
    )
    details = {pattern.name: pattern for pattern in PATTERNS}
    table = []
    for name in [*details, UNEXPLAINED]:
        found = named[named["pattern"] == name]
        if found.empty and name != UNEXPLAINED:
            continue
        example = int(found["row"].min()) if len(found) else None
        table.append(
            {
                "Pattern": name,
                "Kind": details[name].kind if name in details else "Not known",
                "Features": ", ".join(sorted(found["feature"].unique())),
                "Rows": found["row"].nunique(),
                "Reason": details[name].reason if name in details else "No pattern explains these rows yet.",
                "Example row": example,
                "Example URL": urls[example] if example is not None else "",
            }
        )
    # Int64 keeps the row ids whole numbers when the unexplained bucket has none.
    return pd.DataFrame(table).astype({"Example row": "Int64"})


def shapes_table(urls: pd.Series, mismatching_rows: set[int]) -> pd.DataFrame:
    """For each expected shape, how many rows have it and how many of those differ."""
    table = []
    for shape, matches in SHAPES.items():
        rows = {row for row, url in urls.items() if matches(url)}
        table.append(
            {"Shape": shape, "Rows with this shape": len(rows), "Rows with a mismatch": len(rows & mismatching_rows)}
        )
    return pd.DataFrame(table)


def _example_url(url: str) -> str:
    """The start of url, up to the host and port. The rest becomes ... ."""
    start = URL_START_PATTERN.match(url).group(0)
    if len(start) < len(url):
        start += "/..." if url[len(start)] == "/" else "..."
    return start


def _code(text: str) -> str:
    """Show text as inline code in a table cell, so a URL is never a clickable link."""
    if len(text) > EXAMPLE_URL_LIMIT:
        text = text[:EXAMPLE_URL_LIMIT] + "..."
    fence = "``" if "`" in text else "`"
    return f"{fence}{text.replace('|', chr(92) + '|')}{fence}"


def _number(value: float, places: int) -> str:
    return "-" if math.isnan(value) else f"{value:,.{places}f}"


def _markdown_table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def _bug_line(patterns: pd.DataFrame) -> str:
    unexplained = int(patterns.loc[patterns["Pattern"] == UNEXPLAINED, "Rows"].sum())
    suspected = patterns[(patterns["Kind"] == SUSPECTED_BUG) & (patterns["Rows"] > 0)]
    if unexplained == 0 and suspected.empty:
        return "**No suspected extractor bug was found.** Every mismatch has a named pattern."
    lines = []
    for name in suspected["Pattern"]:
        lines.append(f"**Suspected extractor bug: {name}.** Raise it as a Bug ticket.")
    if unexplained:
        verb = "row has" if unexplained == 1 else "rows have"
        lines.append(f"**{unexplained:,} mismatching {verb} no explanation.** Check them for an extractor bug.")
    return "\n\n".join(lines)


def render_report(summary: pd.DataFrame, patterns: pd.DataFrame, shapes: pd.DataFrame, rows: int) -> str:
    """The Markdown report. URLs appear only as inline code, never as links."""
    summary_rows = [
        [
            f"`{r['Our feature']}`",
            f"`{r['Dataset column']}`",
            f"{r['Rows compared']:,}",
            _number(r["Exact match (%)"], 2),
            _number(r["Mean absolute difference"], 4),
            _number(r["Median absolute difference when different"], 1),
        ]
        for r in summary.to_dict("records")
    ]
    pattern_rows = [
        [
            r["Pattern"],
            r["Kind"],
            r["Features"] or "-",
            f"{r['Rows']:,}",
            r["Reason"],
            "-" if r["Example row"] is None or pd.isna(r["Example row"]) else str(int(r["Example row"])),
            _code(_example_url(r["Example URL"])) if r["Example URL"] else "-",
        ]
        for r in patterns.to_dict("records")
    ]
    shape_rows = [
        [r["Shape"], f"{r['Rows with this shape']:,}", f"{r['Rows with a mismatch']:,}"]
        for r in shapes.to_dict("records")
    ]
    return "\n".join(
        [
            "# Recomputed features against the dataset's columns",
            "",
            "Generated by `uv run python -m comparison.compare` (run from `ml/`).",
            f"It reads the raw file `PhiUSIIL_Phishing_URL_Dataset.csv` ({rows:,} rows).",
            "URLs were only read as text. None was opened.",
            "",
            "This is a bug check on our extractor. It is not an attempt to copy the dataset.",
            "Most of our features have no dataset column. The four below do, but some are defined differently.",
            "A difference is fine as long as it has a reason. There is no fixed match line.",
            "The leading `www.` removal was switched off for this check, because the dataset's columns keep `www.`.",
            "",
            "## Summary",
            "",
            "The median difference only counts rows that differ.",
            "",
            _markdown_table(
                [
                    "Our feature",
                    "Dataset column",
                    "Rows compared",
                    "Exact match (%)",
                    "Mean absolute difference",
                    "Median absolute difference when different",
                ],
                summary_rows,
            ),
            "",
            "## Mismatch patterns",
            "",
            "**Draft reasons, to be confirmed by Nic.**",
            "",
            "Each mismatching row and feature goes to the first pattern that explains it.",
            "A row counts once per pattern. A row can fall under two patterns for different features.",
            "The example row is the 0-based data row in the raw file.",
            "Example URLs stop after the host, because a path or query can hold a victim's email address.",
            "",
            _markdown_table(["Pattern", "Kind", "Features", "Rows", "Reason", "Example row", "Example URL"], pattern_rows),
            "",
            "## Other shapes checked",
            "",
            "We expected these shapes might cause mismatches. The counts show whether they did.",
            "A row counted here as a mismatch is also in the patterns table above, which gives its reason.",
            "",
            _markdown_table(["Shape", "Rows with this shape", "Rows with a mismatch"], shape_rows),
            "",
            "## Extractor bugs",
            "",
            _bug_line(patterns),
            "",
        ]
    )


def main() -> None:
    raw = pd.read_csv(RAW_CSV, keep_default_na=False)
    urls = raw[URL_COLUMN]
    ours = recompute_features(urls)
    summary = summary_table(ours, raw)
    mismatches = find_mismatches(ours, raw)
    patterns = patterns_table(mismatches, urls)
    shapes = shapes_table(urls, set(mismatches["row"]))
    REPORT_PATH.write_text(render_report(summary, patterns, shapes, len(raw)), encoding="utf-8")
    print(summary.to_string(index=False))
    print()
    print(patterns[["Pattern", "Kind", "Features", "Rows", "Example row"]].to_string(index=False))
    print()
    print(shapes.to_string(index=False))
    print(f"\nWrote {REPORT_PATH.relative_to(ML_DIR)}")


if __name__ == "__main__":
    main()

"""Compare our hostname features with the dataset's columns of the same meaning.

This is a bug check on the extractor, not an attempt to copy the dataset. Our
features are defined our own way, so some rows differ on purpose. Every
difference needs a reason, so each mismatch is sorted into a named pattern. A
pattern explains a mismatch only if the row has its shape and the dataset's value
is the one the pattern predicts from the dataset's own definitions.

The leading www. is kept (strip_www=False) because the dataset's columns keep it.
The shape of each row is read from the dataset's own Domain column, the part between
// and the first / as the dataset's authors read it. Our own reading of a link comes
only from extract_features, so the URL parsing is never copied here.
URLs are only read as text. None is opened or fetched.

Run from ml/ with: uv run python -m comparison.compare
"""

import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from features.hostname import extract_features

ML_DIR = Path(__file__).resolve().parents[1]
RAW_CSV = ML_DIR / "data" / "PhiUSIIL_Phishing_URL_Dataset.csv"
REPORT_PATH = ML_DIR / "reports" / "feature_comparison.md"
URL_COLUMN = "URL"
DOMAIN_COLUMN = "Domain"

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

PORT_PATTERN = re.compile(r":\d+$")
IPV4_START_PATTERN = re.compile(r"^\d{1,3}(\.\d{1,3}){3}\.")
TWO_PART_ENDING_PATTERN = re.compile(r"\.(co|com|org|net|ac|gov|edu)\.[a-z]{2}$")
BACKTICKS_PATTERN = re.compile(r"`+")
EXAMPLE_URL_LIMIT = 80
# Shown in place of a user:password@ part, so no login-shaped text is ever written.
HIDDEN_USER_PART = "<user part hidden>@"


# Our features for one row, as extract_features returns them.
Ours = Mapping[str, int | float]


def _user_part(domain: str) -> str:
    """The user:password@ part of the dataset's domain, with its @, or "" if there is none."""
    user, at, _ = domain.rpartition("@")
    return user + at


def _port(domain: str) -> str:
    """The :port at the end of the dataset's domain, with its colon, or "" if there is none."""
    found = PORT_PATTERN.search(domain.removeprefix(_user_part(domain)))
    return found.group(0) if found else ""


def _host(domain: str) -> str:
    """The dataset's domain without its user part and port."""
    return domain.removeprefix(_user_part(domain)).removesuffix(_port(domain))


# The dataset's own definitions, worked out from its columns: DomainLength is the
# length of Domain, TLD is the text after the last dot of Domain, and NoOfSubDomain
# is the number of dots in Domain minus 1. So an IP address such as 192.0.2.10 gets
# 2 subdomains and the TLD 10, and a port stays on the end of the TLD.


def _last_number_length(domain: str) -> int:
    """Length of the text after the host's last dot: an IP address's last number."""
    return len(_host(domain).rpartition(".")[2])


def _kept_length(domain: str) -> int:
    """Length of the user part and port, which the dataset keeps and we drop."""
    return len(_user_part(domain)) + len(_port(domain))


def _tld_length_with_port(domain: str, ours: Ours) -> int:
    """The dataset's TLD length when the domain ends with a port: our TLD plus the port.

    For an IP host our TLD is 0, so the dataset's TLD is the last number plus the port.
    """
    tld = _last_number_length(domain) if ours["IsDomainIP"] == 1 else ours["TLDLength"]
    return tld + len(_port(domain))


@dataclass(frozen=True)
class Pattern:
    name: str
    kind: str
    reason: str
    matches: Callable[[str, Ours], bool]  # True if the row has this shape: (domain, our features)
    # Each feature this pattern can explain, with the dataset value it predicts for
    # that feature from (domain, our features).
    predicts: Mapping[str, Callable[[str, Ours], int]]


# Checked in this order. A mismatch goes to the first pattern that matches the row's
# shape and predicts the dataset's value for that feature.
PATTERNS: tuple[Pattern, ...] = (
    Pattern(
        "Host is an IP address",
        DEFINITION_DIFFERENCE,
        "The dataset reads an IP address like a name, so its last number is the TLD and the "
        "first two numbers count as subdomains. We give 0 for both.",
        lambda domain, ours: ours["IsDomainIP"] == 1,
        {
            "TLDLength": lambda domain, ours: _last_number_length(domain),
            "NoOfSubDomain": lambda domain, ours: 2,
        },
    ),
    Pattern(
        "Host starts with an IP address",
        DEFINITION_DIFFERENCE,
        "The dataset marks a name that starts with an IP address as an IP. We mark only a host "
        "that is an IP address.",
        lambda domain, ours: IPV4_START_PATTERN.match(_host(domain)) is not None,
        {"IsDomainIP": lambda domain, ours: 1},
    ),
    Pattern(
        "User part in the link",
        DATASET_QUIRK,
        "The dataset's domain keeps the user:password@ part. We drop it and measure only the host.",
        lambda domain, ours: _user_part(domain) != "",
        {
            "HostnameLength": lambda domain, ours: ours["HostnameLength"] + _kept_length(domain),
            # Every dot in the user part adds one to the dataset's count.
            "NoOfSubDomain": lambda domain, ours: ours["NoOfSubDomain"] + _user_part(domain).count("."),
        },
    ),
    Pattern(
        "Port in the link",
        DATASET_QUIRK,
        "The dataset's domain keeps the port, so com:443 counts as the TLD. We drop the port.",
        lambda domain, ours: _port(domain) != "",
        {
            "HostnameLength": lambda domain, ours: ours["HostnameLength"] + _kept_length(domain),
            "TLDLength": _tld_length_with_port,
        },
    ),
)

# Shapes we expected might cause mismatches. Each is counted to show whether it did.
# Each is read from the host in the dataset's domain.
SHAPES: dict[str, Callable[[str], bool]] = {
    "Leading www.": lambda host: host.lower().startswith("www."),
    "Two-part ending such as .co.uk": lambda host: TWO_PART_ENDING_PATTERN.search(host.lower()) is not None,
    "Non-English name (xn--)": lambda host: "xn--" in host.lower() or not host.isascii(),
    "Capital letters in the host": lambda host: host != host.lower(),
    "Trailing dot after the host": lambda host: host.endswith("."),
}


def recompute_features(urls: pd.Series) -> tuple[pd.DataFrame, dict[int, str]]:
    """Our compared features for each URL, with www. kept, and the URLs we could not read.

    The index is kept. A URL the extractor refuses is left out of the features and
    returned with its reason instead, so one bad row never stops the comparison.
    """
    rows: dict[int, dict] = {}
    refused: dict[int, str] = {}
    for row, url in urls.items():
        try:
            rows[row] = extract_features(url, strip_www=False)
        except ValueError as error:
            refused[row] = f"Our extractor refused the link: {error}"
    ours = pd.DataFrame(list(rows.values()), index=list(rows), columns=list(COMPARED_COLUMNS))
    return ours, refused


def _dataset_problems(raw: pd.DataFrame) -> dict[int, str]:
    """The reason for each row with a compared dataset value that is blank or not a number."""
    problems: dict[int, str] = {}
    for column in COMPARED_COLUMNS.values():
        values = raw[column]
        blank = values.isna() | (values.astype(str).str.strip() == "")
        not_number = pd.to_numeric(values, errors="coerce").isna() & ~blank
        for row in values.index[blank]:
            problems.setdefault(row, f"The dataset's {column} is blank.")
        for row in values.index[not_number]:
            problems.setdefault(row, f"The dataset's {column} is not a number.")
    return problems


@dataclass(frozen=True)
class Comparison:
    ours: pd.DataFrame  # our compared features, for the rows that can be compared
    dataset: pd.DataFrame  # URL, Domain and the compared columns as numbers, for the same rows
    skipped: pd.DataFrame  # row and reason, for each row that cannot be compared


def prepare(raw: pd.DataFrame) -> Comparison:
    """Split the raw rows into those that can be compared and those that cannot.

    A row cannot be compared if the extractor refuses its URL, or if one of the
    dataset's compared values is blank or not a number. Those rows are kept out of
    every count, and each is recorded with its raw row id and the reason.
    """
    ours, refused = recompute_features(raw[URL_COLUMN])
    # One reason per row. The extractor's reason comes first.
    reasons = {**_dataset_problems(raw), **refused}
    skipped = pd.DataFrame(sorted(reasons.items()), columns=["row", "reason"])
    kept = raw.index.difference(skipped["row"])
    columns = list(COMPARED_COLUMNS.values())
    dataset = raw.loc[kept, [URL_COLUMN, DOMAIN_COLUMN, *columns]]
    dataset = dataset.assign(**{column: pd.to_numeric(dataset[column]) for column in columns})
    return Comparison(ours.loc[kept], dataset, skipped)


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


def pattern_for(domain: str, ours: Ours, feature: str, dataset_value: int) -> str:
    """Name of the first pattern that explains this feature's mismatch, or UNEXPLAINED.

    domain is the dataset's Domain column for the row, ours is our features for it and
    dataset_value is the dataset's value for the feature. A pattern explains the
    mismatch only if the row has its shape and it predicts exactly dataset_value.
    """
    for pattern in PATTERNS:
        predict = pattern.predicts.get(feature)
        if predict and pattern.matches(domain, ours) and predict(domain, ours) == dataset_value:
            return pattern.name
    return UNEXPLAINED


def patterns_table(mismatches: pd.DataFrame, ours: pd.DataFrame, dataset: pd.DataFrame) -> pd.DataFrame:
    """One row per pattern that has mismatches, plus the unexplained bucket, always.

    dataset holds the URL, Domain and compared columns for the same rows as ours.
    """
    domains = dataset[DOMAIN_COLUMN]
    named = mismatches.assign(
        pattern=[
            pattern_for(domains[row], ours.loc[row], feature, dataset.loc[row, COMPARED_COLUMNS[feature]])
            for row, feature in zip(mismatches["row"], mismatches["feature"])
        ]
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
                "Example URL": (
                    _example_url(dataset[URL_COLUMN][example], dataset[DOMAIN_COLUMN][example])
                    if example is not None
                    else ""
                ),
            }
        )
    # Int64 keeps the row ids whole numbers when the unexplained bucket has none.
    return pd.DataFrame(table).astype({"Example row": "Int64"})


def skipped_table(skipped: pd.DataFrame) -> pd.DataFrame:
    """One row per reason a row could not be compared: how many rows and the first one."""
    rows = skipped.groupby("reason")["row"]
    return pd.DataFrame(
        {"Reason": rows.size().index, "Rows": rows.size().to_numpy(), "Example row": rows.min().to_numpy()}
    )


def shapes_table(domains: pd.Series, mismatching_rows: set[int]) -> pd.DataFrame:
    """For each expected shape, how many rows have it and how many of those differ."""
    hosts = domains.map(_host)
    table = []
    for shape, matches in SHAPES.items():
        rows = {row for row, host in hosts.items() if matches(host)}
        table.append(
            {"Shape": shape, "Rows with this shape": len(rows), "Rows with a mismatch": len(rows & mismatching_rows)}
        )
    return pd.DataFrame(table)


def _hide_user_part(domain: str) -> str:
    user = _user_part(domain)
    return HIDDEN_USER_PART + domain.removeprefix(user) if user else domain


def _example_url(url: str, domain: str) -> str:
    """The start of url, up to the end of the dataset's domain, with any user part hidden.

    The rest becomes ... . If the url does not hold the domain as written, only the
    domain is shown.
    """
    found = url.find(domain) if domain else -1
    if found < 0:
        return _hide_user_part(domain) + "..."
    end = found + len(domain)
    start = url[:found] + _hide_user_part(domain)
    if end < len(url):
        start += "/..." if url[end] == "/" else "..."
    return start


def _code(text: str) -> str:
    """Show text as inline code in a table cell, so a URL is never a clickable link."""
    if len(text) > EXAMPLE_URL_LIMIT:
        text = text[:EXAMPLE_URL_LIMIT] + "..."
    # The fence must be longer than any run of backticks inside the text, or that run
    # would close the code early. A space keeps a backtick at either end off the fence.
    fence = "`" * (max(map(len, BACKTICKS_PATTERN.findall(text)), default=0) + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text.replace('|', chr(92) + '|')}{pad}{fence}"


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


def _skipped_section(skipped: pd.DataFrame) -> list[str]:
    total = int(skipped["Rows"].sum())
    if total == 0:
        return ["Every row could be compared."]
    verb = "row could" if total == 1 else "rows could"
    return [
        f"**{total:,} {verb} not be compared.** They are left out of every count in this report.",
        "The example row is the 0-based data row in the raw file.",
        "",
        _markdown_table(
            ["Reason", "Rows", "Example row"],
            [[r["Reason"], f"{r['Rows']:,}", str(int(r["Example row"]))] for r in skipped.to_dict("records")],
        ),
    ]


def render_report(
    summary: pd.DataFrame, patterns: pd.DataFrame, shapes: pd.DataFrame, skipped: pd.DataFrame, rows: int
) -> str:
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
            _code(r["Example URL"]) if r["Example URL"] else "-",
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
            "Rows compared leaves out the rows that could not be compared (next section).",
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
            "## Rows that could not be compared",
            "",
            *_skipped_section(skipped),
            "",
            "## Mismatch patterns",
            "",
            "**Draft reasons, to be confirmed by Nic.**",
            "",
            "Each mismatching row and feature goes to the first pattern that explains it.",
            "A row counts once per pattern. A row can fall under two patterns for different features.",
            "The example row is the 0-based data row in the raw file.",
            "Example URLs stop after the host, because a path or query can hold a victim's email address.",
            f"A user part before the host is shown as `{HIDDEN_USER_PART}`, because it can look like a login.",
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
    comparison = prepare(raw)
    ours, dataset = comparison.ours, comparison.dataset
    summary = summary_table(ours, dataset)
    mismatches = find_mismatches(ours, dataset)
    patterns = patterns_table(mismatches, ours, dataset)
    shapes = shapes_table(dataset[DOMAIN_COLUMN], set(mismatches["row"]))
    skipped = skipped_table(comparison.skipped)
    REPORT_PATH.write_text(render_report(summary, patterns, shapes, skipped, len(raw)), encoding="utf-8")
    print(summary.to_string(index=False))
    print()
    print(f"Rows that could not be compared: {len(comparison.skipped):,}")
    if len(skipped):
        print(skipped.to_string(index=False))
    print()
    print(patterns[["Pattern", "Kind", "Features", "Rows", "Example row"]].to_string(index=False))
    print()
    print(shapes.to_string(index=False))
    print(f"\nWrote {REPORT_PATH.relative_to(ML_DIR)}")


if __name__ == "__main__":
    main()

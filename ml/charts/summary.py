"""Work out the chart numbers and takeaways from the cleaned data, and save them.

Run from ml/ with:

    uv run python -m charts.summary

It reads ml/data/phiusiil_cleaned.csv and writes ml/reports/chart_summary.json, a
small file of counts and percentages for the charts page. No link from the dataset
goes into the file. It stops without saving if the phishing and legitimate totals
differ from the ones in ml/reports/cleaning_report.md, since that would mean the
label is the wrong way round or the data has changed.

The first chart is the class balance: how many links are phishing and how many
are legitimate. Each other chart compares phishing with legitimate links on one
measure. Takeaways are worked out from the unrounded shares. Every
legitimate link in this dataset is a bare homepage on HTTPS, so the takeaways
point to warning signs and never say that HTTPS or a short link means safe.
"""

import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from cleaning.storage import CLEANED_CSV_NAME, load_cleaned

ML_DIR = Path(__file__).resolve().parents[1]
SUMMARY_FILE_NAME = "chart_summary.json"
CLEANING_REPORT_NAME = "cleaning_report.md"
PHISHING_LABEL = 1
LEGITIMATE_LABEL = 0
LONG_LINK_CHARACTERS = 50
DECIMALS = 1
# Share of the smaller class, in percent, at or above which the data counts as
# balanced, and below which it counts as heavily imbalanced.
BALANCED_MINORITY_SHARE = 45
HEAVY_IMBALANCE_MINORITY_SHARE = 20

SOURCE = (
    "Based on a modified version of the PhiUSIIL Phishing URL dataset (Prasad and Chandra, 2024, "
    "UCI, CC BY 4.0): duplicate links removed and the label recoded."
)
DATASET_NOTE = (
    "In this dataset every legitimate link is a website's homepage, such as https://www.example.com, "
    "with nothing after the name. Real links to safe sites are often longer, so these charts show "
    "warning signs, not proof that a link is safe."
)

SAFETY_SUBJECTS = ("https", "padlock", "short")
NEGATIONS = ("not", "never", "no")
SENTENCE_END = re.compile(r"[.!?](?:\s|$)")
CLAUSE_END = re.compile(r"[,;:](?:\s|$)")
WORD = re.compile(r"[a-z']+")
REPORT_COUNTS = re.compile(r"1 \(phishing\): ([\d,]+).*?0 \(legitimate\): ([\d,]+)")


@dataclass(frozen=True)
class ChartSpec:
    id: str
    title: str
    groups: Callable[[pd.DataFrame], list[dict]]
    takeaway: Callable[[float, float], str]


def _group(label: str, in_group: pd.Series) -> dict:
    count = int(in_group.sum())
    total = int(len(in_group))
    return {"label": label, "value": round(100 * count / total, DECIMALS), "count": count, "total": total}


def _class_balance(rows: pd.DataFrame) -> list[dict]:
    is_phishing = rows["label"] == PHISHING_LABEL
    return [_group("Phishing", is_phishing), _group("Legitimate", ~is_phishing)]


def _compare_sign(has_sign: Callable[[pd.DataFrame], pd.Series]) -> Callable[[pd.DataFrame], list[dict]]:
    """Groups for a chart showing the share of phishing and of legitimate links with a sign."""

    def groups(rows: pd.DataFrame) -> list[dict]:
        sign = has_sign(rows)
        return [
            _group("Phishing", sign[rows["label"] == PHISHING_LABEL]),
            _group("Legitimate", sign[rows["label"] == LEGITIMATE_LABEL]),
        ]

    return groups


def _balance_takeaway(phishing: float, legitimate: float) -> str:
    minority = min(phishing, legitimate)
    if minority >= BALANCED_MINORITY_SHARE:
        verdict = "balanced"
    elif minority >= HEAVY_IMBALANCE_MINORITY_SHARE:
        verdict = "mildly imbalanced"
    else:
        verdict = "heavily imbalanced"
    return f"About {phishing:.0f}% of links are phishing and {legitimate:.0f}% are legitimate, so the dataset is {verdict}."


CHART_SPECS = (
    ChartSpec(
        id="class_balance",
        title="How many links are phishing and how many are legitimate",
        groups=_class_balance,
        takeaway=_balance_takeaway,
    ),
    ChartSpec(
        id="https",
        title="Links that use HTTPS (the padlock)",
        groups=_compare_sign(lambda rows: rows["IsHTTPS"] == 1),
        takeaway=lambda phishing, legitimate: (
            f"About {phishing:.0f}% of phishing links use HTTPS too, so a padlock does not mean a link is safe."
        ),
    ),
    ChartSpec(
        id="long_links",
        title=f"Links longer than {LONG_LINK_CHARACTERS} characters",
        groups=_compare_sign(lambda rows: rows["URLLength"] > LONG_LINK_CHARACTERS),
        takeaway=lambda phishing, legitimate: (
            f"About {phishing:.0f}% of phishing links are longer than {LONG_LINK_CHARACTERS} characters. "
            "A long, messy link is a warning sign, but a short link is not proof that it is safe."
        ),
    ),
    ChartSpec(
        id="hyphens",
        title="Links that contain a hyphen (-)",
        groups=_compare_sign(lambda rows: rows["URL"].str.contains("-", regex=False)),
        takeaway=lambda phishing, legitimate: (
            f"About {phishing:.0f}% of phishing links contain a hyphen, against {legitimate:.0f}% of legitimate "
            "ones. Fake sites often join words with hyphens to look like a real company's name."
        ),
    ),
)
CHART_IDS = tuple(spec.id for spec in CHART_SPECS)
SPECS_BY_ID = {spec.id: spec for spec in CHART_SPECS}


def takeaway_for(chart_id: str, groups: list[dict]) -> str:
    """The takeaway for a chart, worked out from each group's unrounded share."""
    phishing, legitimate = (100 * group["count"] / group["total"] for group in groups)
    return SPECS_BY_ID[chart_id].takeaway(phishing, legitimate)


def _chart(spec: ChartSpec, rows: pd.DataFrame) -> dict:
    groups = spec.groups(rows)
    return {
        "id": spec.id,
        "title": spec.title,
        "takeaway": takeaway_for(spec.id, groups),
        "unit": "percent",
        "groups": groups,
    }


def build_summary(rows: pd.DataFrame) -> dict:
    """Return the totals, the dataset note and one comparison per chart."""
    unknown = set(rows["label"].unique()) - {PHISHING_LABEL, LEGITIMATE_LABEL}
    if unknown:
        raise ValueError(f"Unexpected label values {sorted(unknown)}: expected 1 = phishing and 0 = legitimate.")
    return {
        "source": SOURCE,
        "dataset_note": DATASET_NOTE,
        "totals": {
            "phishing": int((rows["label"] == PHISHING_LABEL).sum()),
            "legitimate": int((rows["label"] == LEGITIMATE_LABEL).sum()),
        },
        "charts": [_chart(spec, rows) for spec in CHART_SPECS],
    }


def _negated_before_safe(clause: str) -> bool:
    """True if a negation comes before the first "safe" in the clause."""
    words = WORD.findall(clause)
    before_safe = words[: words.index("safe")]
    return any(word in NEGATIONS or word.endswith("n't") for word in before_safe)


def _sentence_claims_safe(sentence: str) -> bool:
    if not any(subject in sentence for subject in SAFETY_SUBJECTS):
        return False
    clauses = [clause for clause in CLAUSE_END.split(sentence) if "safe" in WORD.findall(clause)]
    return any(not _negated_before_safe(clause) for clause in clauses)


def makes_safety_claim(text: str) -> bool:
    """True if a sentence names HTTPS, a padlock or a short link and calls something safe,
    unless that "safe" has a negation before it in its own clause.

    "A padlock does not mean a link is safe" passes. "A padlock means the site is safe,
    not a scam" is caught, because its "not" comes after "safe".
    """
    return any(_sentence_claims_safe(sentence) for sentence in SENTENCE_END.split(text.lower()))


def report_label_counts(report_text: str) -> dict[str, int]:
    """Read the phishing and legitimate totals from the cleaning report."""
    match = REPORT_COUNTS.search(report_text)
    if not match:
        raise ValueError("The cleaning report has no label counts after cleaning.")
    phishing, legitimate = (int(value.replace(",", "")) for value in match.groups())
    return {"phishing": phishing, "legitimate": legitimate}


def save_summary(summary: dict, path: Path) -> Path:
    """Write the summary as indented JSON, creating its folder if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2) + "\n")
    return path


def main(ml_dir: Path = ML_DIR) -> int:
    """Build, check and save the summary. Returns 0 on success, 1 if a check fails."""
    cleaned_path = ml_dir / "data" / CLEANED_CSV_NAME
    if not cleaned_path.exists():
        print(f"Cleaned data not found at {cleaned_path}. Run 03_clean_dataset.ipynb first.")
        return 1
    summary = build_summary(load_cleaned(cleaned_path))
    expected = report_label_counts((ml_dir / "reports" / CLEANING_REPORT_NAME).read_text())
    if summary["totals"] != expected:
        print(f"Summary not saved: totals {summary['totals']} do not match the cleaning report's {expected}.")
        return 1
    path = save_summary(summary, ml_dir / "reports" / SUMMARY_FILE_NAME)
    print(f"Totals {summary['totals']} match the cleaning report.")
    for chart in summary["charts"]:
        phishing, legitimate = chart["groups"]
        print(f"- {chart['title']}: phishing {phishing['value']}%, legitimate {legitimate['value']}%")
    print(f"Saved {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

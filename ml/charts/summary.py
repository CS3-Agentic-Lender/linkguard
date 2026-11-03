"""Work out the chart numbers and takeaways from the cleaned data, and save them.

Run from ml/ with:

    uv run python -m charts.summary

It reads ml/data/phiusiil_cleaned.csv and writes ml/reports/chart_summary.json, a
small file of counts and percentages for the charts page. No link from the dataset
goes into the file. It stops without saving if the phishing and legitimate totals
differ from the ones in ml/reports/cleaning_report.md, since that would mean the
label is the wrong way round or the data has changed.

Each chart compares phishing with legitimate links on one measure. Every
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
NEGATIONS = ("not", "n't", "never", "no ")
REPORT_COUNTS = re.compile(r"1 \(phishing\): ([\d,]+).*?0 \(legitimate\): ([\d,]+)")


@dataclass(frozen=True)
class ChartSpec:
    id: str
    title: str
    has_sign: Callable[[pd.DataFrame], pd.Series]
    takeaway: Callable[[float, float], str]


CHART_SPECS = (
    ChartSpec(
        id="https",
        title="Links that use HTTPS (the padlock)",
        has_sign=lambda rows: rows["IsHTTPS"] == 1,
        takeaway=lambda phishing, legitimate: (
            f"About {phishing:.0f}% of phishing links use HTTPS too, so a padlock does not mean a link is safe."
        ),
    ),
    ChartSpec(
        id="long_links",
        title=f"Links longer than {LONG_LINK_CHARACTERS} characters",
        has_sign=lambda rows: rows["URLLength"] > LONG_LINK_CHARACTERS,
        takeaway=lambda phishing, legitimate: (
            f"About {phishing:.0f}% of phishing links are longer than {LONG_LINK_CHARACTERS} characters. "
            "A long, messy link is a warning sign, but a short link is not proof that it is safe."
        ),
    ),
    ChartSpec(
        id="hyphens",
        title="Links that contain a hyphen (-)",
        has_sign=lambda rows: rows["URL"].str.contains("-", regex=False),
        takeaway=lambda phishing, legitimate: (
            f"About {phishing:.0f}% of phishing links contain a hyphen, against {legitimate:.0f}% of legitimate "
            "ones. Fake sites often join words with hyphens to look like a real company's name."
        ),
    ),
)
CHART_IDS = tuple(spec.id for spec in CHART_SPECS)


def _group(label: str, has_sign: pd.Series) -> dict:
    count = int(has_sign.sum())
    total = int(len(has_sign))
    return {"label": label, "value": round(100 * count / total, DECIMALS), "count": count, "total": total}


def _chart(spec: ChartSpec, rows: pd.DataFrame) -> dict:
    has_sign = spec.has_sign(rows)
    phishing = _group("Phishing", has_sign[rows["label"] == PHISHING_LABEL])
    legitimate = _group("Legitimate", has_sign[rows["label"] == LEGITIMATE_LABEL])
    return {
        "id": spec.id,
        "title": spec.title,
        "takeaway": spec.takeaway(phishing["value"], legitimate["value"]),
        "unit": "percent",
        "groups": [phishing, legitimate],
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


def makes_safety_claim(text: str) -> bool:
    """True if text links HTTPS, a padlock or a short link with being safe, without a negation."""
    lowered = text.lower()
    if "safe" not in lowered or not any(subject in lowered for subject in SAFETY_SUBJECTS):
        return False
    return not any(negation in lowered for negation in NEGATIONS)


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

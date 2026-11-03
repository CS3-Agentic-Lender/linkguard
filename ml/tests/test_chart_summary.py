import json
from pathlib import Path

import pandas as pd
import pytest

from charts.summary import (
    CHART_IDS,
    DATASET_NOTE,
    build_summary,
    main,
    makes_safety_claim,
    report_label_counts,
    save_summary,
)
from cleaning.storage import CLEANED_CSV_NAME, save_cleaned

ML_DIR = Path(__file__).resolve().parents[1]

# Made-up cleaned rows with 1 = phishing. Phishing: 1 of 2 on HTTPS, 1 of 2 longer than
# 50 characters, 2 of 2 with a hyphen. Legitimate: 3 of 3 on HTTPS, none long, 1 of 3
# with a hyphen. URLs are fake.
LONG = "http://pay-account.example/" + "x" * 40
ROWS = pd.DataFrame(
    {
        "URL": [LONG, "https://log-in.example", "https://www.a.example", "https://www.b-c.example", "https://www.d.example"],
        "URLLength": [len(LONG), 22, 21, 23, 21],
        "IsHTTPS": [0, 1, 1, 1, 1],
        "label": [1, 1, 0, 0, 0],
    }
)


def chart(summary: dict, chart_id: str) -> dict:
    return next(item for item in summary["charts"] if item["id"] == chart_id)


def group(item: dict, label: str) -> dict:
    return next(entry for entry in item["groups"] if entry["label"] == label)


def test_has_at_least_three_charts_each_comparing_phishing_with_legitimate():
    summary = build_summary(ROWS)

    assert len(summary["charts"]) >= 3
    assert [item["id"] for item in summary["charts"]] == list(CHART_IDS)
    for item in summary["charts"]:
        assert [entry["label"] for entry in item["groups"]] == ["Phishing", "Legitimate"]
        assert item["title"] and item["unit"] == "percent"


def test_figures_follow_the_label_direction_one_is_phishing():
    summary = build_summary(ROWS)

    https = chart(summary, "https")
    assert group(https, "Phishing") == {"label": "Phishing", "value": 50.0, "count": 1, "total": 2}
    assert group(https, "Legitimate") == {"label": "Legitimate", "value": 100.0, "count": 3, "total": 3}


def test_long_link_and_hyphen_figures():
    summary = build_summary(ROWS)

    assert group(chart(summary, "long_links"), "Phishing")["count"] == 1
    assert group(chart(summary, "long_links"), "Legitimate")["count"] == 0
    assert group(chart(summary, "hyphens"), "Phishing")["count"] == 2
    assert group(chart(summary, "hyphens"), "Legitimate")["count"] == 1
    assert group(chart(summary, "hyphens"), "Legitimate")["value"] == pytest.approx(33.3)


def test_totals_are_the_label_counts():
    summary = build_summary(ROWS)

    assert summary["totals"] == {"phishing": 2, "legitimate": 3}


def test_rejects_a_label_other_than_zero_or_one():
    rows = ROWS.assign(label=[1, 1, 0, 0, 2])

    with pytest.raises(ValueError, match="label"):
        build_summary(rows)


def test_every_chart_has_a_one_line_takeaway():
    summary = build_summary(ROWS)

    for item in summary["charts"]:
        assert item["takeaway"].strip()
        assert "\n" not in item["takeaway"]


def test_no_takeaway_or_note_says_https_or_a_short_link_means_safe():
    summary = build_summary(build_rows_like_the_real_data())

    for text in [item["takeaway"] for item in summary["charts"]] + [summary["dataset_note"]]:
        assert not makes_safety_claim(text), text


def test_the_dataset_note_says_legitimate_links_are_all_homepages():
    summary = build_summary(ROWS)

    assert summary["dataset_note"] == DATASET_NOTE
    assert "homepage" in DATASET_NOTE


@pytest.mark.parametrize(
    "text",
    [
        "A padlock means the site is safe.",
        "Links with HTTPS are safe.",
        "A short link is safe to open.",
    ],
)
def test_safety_claim_check_catches_a_bad_takeaway(text):
    assert makes_safety_claim(text)


@pytest.mark.parametrize(
    "text",
    [
        "Half of phishing links use HTTPS too, so a padlock does not mean a link is safe.",
        "A short link is not proof that it is safe.",
        "Phishing links are more likely to contain a hyphen.",
    ],
)
def test_safety_claim_check_allows_a_warning(text):
    assert not makes_safety_claim(text)


def test_reads_the_label_counts_from_the_cleaning_report():
    text = "- Label counts after cleaning: **1 (phishing): 100,520**, **0 (legitimate): 134,850**."

    assert report_label_counts(text) == {"phishing": 100520, "legitimate": 134850}


def test_the_real_cleaning_report_has_label_counts():
    text = (ML_DIR / "reports" / "cleaning_report.md").read_text()

    assert report_label_counts(text) == {"phishing": 100520, "legitimate": 134850}


def test_report_without_label_counts_is_rejected():
    with pytest.raises(ValueError, match="label counts"):
        report_label_counts("no counts here")


def test_saved_summary_reads_back_unchanged(tmp_path):
    summary = build_summary(ROWS)

    path = save_summary(summary, tmp_path / "reports" / "chart_summary.json")

    assert json.loads(path.read_text()) == summary


def test_main_writes_the_summary_when_totals_match_the_report(tmp_path, capsys):
    save_cleaned(ROWS, tmp_path / "data" / CLEANED_CSV_NAME)
    write_report(tmp_path, phishing=2, legitimate=3)

    assert main(tmp_path) == 0

    assert (tmp_path / "reports" / "chart_summary.json").exists()
    assert "match the cleaning report" in capsys.readouterr().out


def test_main_saves_nothing_when_totals_differ_from_the_report(tmp_path, capsys):
    save_cleaned(ROWS, tmp_path / "data" / CLEANED_CSV_NAME)
    write_report(tmp_path, phishing=3, legitimate=2)

    assert main(tmp_path) == 1

    assert "do not match" in capsys.readouterr().out
    assert not (tmp_path / "reports" / "chart_summary.json").exists()


def test_main_stops_without_the_cleaned_file(tmp_path, capsys):
    assert main(tmp_path) == 1

    assert "03_clean_dataset" in capsys.readouterr().out


def write_report(ml_dir: Path, phishing: int, legitimate: int) -> None:
    report = ml_dir / "reports" / "cleaning_report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(f"- Label counts after cleaning: **1 (phishing): {phishing:,}**, **0 (legitimate): {legitimate:,}**.\n")


def build_rows_like_the_real_data() -> pd.DataFrame:
    """Shares close to the real data, so the takeaways are worded as they will be."""
    phishing = pd.DataFrame(
        {
            "URL": ["http://a-b.example/" + "x" * 40] * 22 + ["https://c.example"] * 49 + ["http://d.example"] * 29,
            "URLLength": [59] * 22 + [17] * 49 + [16] * 29,
            "IsHTTPS": [0] * 22 + [1] * 49 + [0] * 29,
            "label": [1] * 100,
        }
    )
    legitimate = pd.DataFrame(
        {
            "URL": ["https://www.e-f.example"] * 8 + ["https://www.g.example"] * 92,
            "URLLength": [23] * 8 + [21] * 92,
            "IsHTTPS": [1] * 100,
            "label": [0] * 100,
        }
    )
    return pd.concat([phishing, legitimate], ignore_index=True)

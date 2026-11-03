import re
from pathlib import Path

import numpy as np
import pandas as pd

import cleaning.storage
import featureset.build
import features.hostname
import leakage.single_feature
from cleaning.storage import CLEANED_CSV_NAME, save_cleaned
from features.hostname import FEATURE_NAMES
from leakage import recheck
from leakage.recheck import REPORT_NAME, main, recheck_table, render_report, report_path

ROWS = 40
rng = np.random.default_rng(0)
label = np.tile([0, 1], ROWS // 2)

# Made-up feature rows: IsDomainIP equals the label, so it gives the answer away.
# Every other feature is noise.
FEATURES = pd.DataFrame(
    {name: rng.random(ROWS) for name in FEATURE_NAMES} | {"IsDomainIP": label, "label": label}
)

# Made-up cleaned rows, only ever handled as text. Every phishing link is an IP
# address and every legitimate one is a name, so IsDomainIP gives the label away.
# Other features may give it away too, so main is checked against recheck_table.
CLEANED = pd.DataFrame(
    {
        "URL": [
            f"http://10.0.0.{i}/login" if is_phishing else f"https://www.site{i}.example.com"
            for i, is_phishing in enumerate(label)
        ],
        "label": label,
    }
)

TABLE_ROW = re.compile(r"^\| `(\w+)` \| (\d+\.\d{2}) \| (YES)? \|$")


def _table_rows(markdown: str) -> list[tuple[str, str, str]]:
    return [match.groups(default="") for line in markdown.splitlines() if (match := TABLE_ROW.match(line))]


def test_table_has_exactly_the_ten_features():
    table = recheck_table(FEATURES)

    assert sorted(table["Column"]) == sorted(FEATURE_NAMES)
    assert len(table) == len(FEATURE_NAMES)


def test_table_is_sorted_high_to_low():
    table = recheck_table(FEATURES)

    assert table["Accuracy (%)"].is_monotonic_decreasing


def test_flags_exactly_the_feature_that_equals_the_label():
    table = recheck_table(FEATURES)

    assert table.loc[table["Over 95%"], "Column"].tolist() == ["IsDomainIP"]
    assert table.iloc[0]["Column"] == "IsDomainIP"


def test_markdown_has_the_header_row_then_one_row_per_feature_with_yes_marks():
    table = recheck_table(FEATURES)

    markdown = render_report(table, ROWS)

    lines = markdown.splitlines()
    header = lines.index("| Column | Accuracy (%) | Over 95% |")
    assert lines[header + 1] == "|---|---|---|"
    rows = _table_rows(markdown)
    assert [column for column, _, _ in rows] == table["Column"].tolist()
    assert [column for column, _, mark in rows if mark == "YES"] == ["IsDomainIP"]
    assert rows[0][1] == f"{table.iloc[0]['Accuracy (%)']:.2f}"


def test_markdown_says_how_many_are_over_95_and_compares_with_the_original_top_score():
    markdown = render_report(recheck_table(FEATURES), ROWS)

    assert "**1 of 10** features score over 95%: `IsDomainIP`." in markdown
    assert "`URLSimilarityIndex` at 99.67%" in markdown
    assert f"({ROWS:,} rows)" in markdown


def test_markdown_says_so_when_no_feature_is_over_95():
    noise_only = FEATURES.assign(IsDomainIP=rng.random(ROWS))

    markdown = render_report(recheck_table(noise_only), ROWS)

    assert "**0 of 10** features score over 95%. None of them predicts the label on its own." in markdown
    assert [mark for _, _, mark in _table_rows(markdown)] == [""] * len(FEATURE_NAMES)

def test_recheck_uses_the_shared_check_and_feature_set_code_not_a_copy():
    assert recheck.single_feature_accuracy is leakage.single_feature.single_feature_accuracy
    assert recheck.build_feature_set is featureset.build.build_feature_set
    assert recheck.load_cleaned is cleaning.storage.load_cleaned
    assert recheck.FEATURE_NAMES is features.hostname.FEATURE_NAMES


def test_main_writes_the_report_and_returns_0(tmp_path, capsys):
    save_cleaned(CLEANED, tmp_path / "data" / CLEANED_CSV_NAME)

    code = main(tmp_path)

    assert code == 0
    markdown = report_path(tmp_path).read_text()
    expected = recheck_table(featureset.build.build_feature_set(CLEANED).features)
    rows = _table_rows(markdown)
    assert [column for column, _, _ in rows] == expected["Column"].tolist()
    flagged = [column for column, _, mark in rows if mark == "YES"]
    assert flagged == expected.loc[expected["Over 95%"], "Column"].tolist()
    assert "IsDomainIP" in flagged
    out = capsys.readouterr().out
    assert f"{len(flagged)} over 95%" in out
    assert str(report_path(tmp_path)) in out


def test_main_explains_a_missing_cleaned_file_writes_no_report_and_returns_1(tmp_path, capsys):
    code = main(tmp_path)

    assert code == 1
    assert not report_path(tmp_path).exists()
    out = capsys.readouterr().out
    assert "The cleaned file was not found" in out
    assert featureset.build.MISSING_CLEANED_HINT in out


def test_main_reports_links_that_fail_writes_no_report_and_returns_1(tmp_path, capsys):
    broken = CLEANED.copy()
    broken.loc[3, "URL"] = "https://a..b.com"
    save_cleaned(broken, tmp_path / "data" / CLEANED_CSV_NAME)

    code = main(tmp_path)

    assert code == 1
    assert not report_path(tmp_path).exists()
    assert "1 rows failed" in capsys.readouterr().out


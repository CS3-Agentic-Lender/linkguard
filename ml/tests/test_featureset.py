import subprocess
from pathlib import Path

import pandas as pd

import features.hostname
from cleaning.storage import CLEANED_CSV_NAME, save_cleaned
from featureset import build
from featureset.build import OUTPUT_COLUMNS, OUTPUT_CSV_NAME, build_feature_set, main, output_path
from features.hostname import FEATURE_NAMES, cleaned_host, extract_features

# Made-up cleaned rows, only ever handled as text. The index is not 0, 1, 2 on
# purpose, so the test can tell the kept row index from a new count.
CLEANED = pd.DataFrame(
    {
        "URL": ["https://www.example.com/login", "http://10.0.0.1/", "shop.example.co.uk"],
        "TLD": ["com", "", "uk"],
        "label": [1, 0, 1],
    },
    index=[4, 9, 17],
)
BROKEN = pd.DataFrame(
    {
        "URL": ["https://example.com", "https://a..b.com", "", "https://c..d.com"],
        "label": [0, 1, 1, 0],
    },
    index=[0, 1, 2, 3],
)
# A cell that was never text: a blank cell read by pandas is NaN, and a bad
# load could give None. The valid row comes last, so the build must carry on.
NOT_TEXT = pd.DataFrame(
    {
        "URL": [None, float("nan"), "https://a..b.com", "https://example.com"],
        "label": [1, 0, 1, 0],
    },
    index=[0, 1, 2, 3],
)


def test_columns_are_row_then_the_ten_features_then_label_and_hostname():
    result = build_feature_set(CLEANED)

    assert OUTPUT_COLUMNS == ("row", *FEATURE_NAMES, "label", "hostname")
    assert tuple(result.features.columns) == OUTPUT_COLUMNS


def test_one_output_row_per_input_row_with_the_row_index_kept():
    result = build_feature_set(CLEANED)

    assert result.failures == ()
    assert len(result.features) == len(CLEANED)
    assert result.features["row"].tolist() == [4, 9, 17]


def test_features_are_the_shared_extractor_values():
    result = build_feature_set(CLEANED)

    for position, link in enumerate(CLEANED["URL"]):
        row = result.features.iloc[position]
        assert {name: row[name] for name in FEATURE_NAMES} == extract_features(link)


def test_label_is_passed_through_unchanged():
    result = build_feature_set(CLEANED)

    assert result.features["label"].tolist() == CLEANED["label"].tolist()


def test_hostname_column_is_the_cleaned_host():
    result = build_feature_set(CLEANED)

    assert result.features["hostname"].tolist() == [cleaned_host(link) for link in CLEANED["URL"]]
    assert result.features["hostname"].tolist() == ["example.com", "10.0.0.1", "shop.example.co.uk"]


def test_every_failing_row_is_counted_with_its_reason():
    result = build_feature_set(BROKEN)

    assert [failure.row for failure in result.failures] == [1, 2, 3]
    reasons = {failure.row: failure.reason for failure in result.failures}
    assert reasons[1] == reasons[3] == features.hostname.BAD_HOST_MESSAGE
    assert reasons[2] == features.hostname.EMPTY_LINK_MESSAGE


def test_main_writes_the_file_and_returns_0(tmp_path, capsys):
    save_cleaned(CLEANED, tmp_path / "data" / CLEANED_CSV_NAME)

    code = main(tmp_path)

    assert code == 0
    written = pd.read_csv(output_path(tmp_path), keep_default_na=False)
    assert tuple(written.columns) == OUTPUT_COLUMNS
    # save_cleaned drops the index, so the file's rows are numbered from 0.
    assert written["row"].tolist() == [0, 1, 2]
    assert str(len(CLEANED)) in capsys.readouterr().out


def test_main_reports_failures_writes_no_file_and_returns_1(tmp_path, capsys):
    save_cleaned(BROKEN, tmp_path / "data" / CLEANED_CSV_NAME)

    code = main(tmp_path)

    assert code == 1
    assert not output_path(tmp_path).exists()
    out = capsys.readouterr().out
    assert "3 rows failed" in out
    assert f"2 rows: {features.hostname.BAD_HOST_MESSAGE} (for example row 1)" in out
    assert f"1 row: {features.hostname.EMPTY_LINK_MESSAGE} (for example row 2)" in out


def test_a_link_that_is_not_text_is_a_failed_row_and_the_build_carries_on():
    result = build_feature_set(NOT_TEXT)

    assert [failure.row for failure in result.failures] == [0, 1, 2]
    reasons = {failure.row: failure.reason for failure in result.failures}
    assert reasons[0] == reasons[1] == build.NOT_TEXT_MESSAGE
    assert reasons[2] == features.hostname.BAD_HOST_MESSAGE
    assert result.features["row"].tolist() == [3]


def test_main_reports_links_that_are_not_text_writes_no_file_and_returns_1(tmp_path, capsys, monkeypatch):
    # load_cleaned reads blanks as "", so the loader is swapped to hand over None and NaN.
    monkeypatch.setattr(build, "load_cleaned", lambda _path: NOT_TEXT)

    code = main(tmp_path)

    assert code == 1
    assert not output_path(tmp_path).exists()
    out = capsys.readouterr().out
    assert "3 rows failed" in out
    assert f"2 rows: {build.NOT_TEXT_MESSAGE} (for example row 0)" in out
    assert f"1 row: {features.hostname.BAD_HOST_MESSAGE} (for example row 2)" in out


def test_build_uses_the_shared_extractor_not_a_copy():
    assert build.extract_features is features.hostname.extract_features
    assert build.cleaned_host is features.hostname.cleaned_host


def test_output_file_is_gitignored():
    ml_dir = Path(__file__).resolve().parents[1]
    path = output_path(ml_dir)

    assert path.name == OUTPUT_CSV_NAME
    assert path.parent == ml_dir / "data"
    ignored = subprocess.run(["git", "check-ignore", "-q", str(path)], cwd=ml_dir, check=False)
    assert ignored.returncode == 0

import pandas as pd
import pytest

from cleaning.values import clean_values, find_value_problems

# Made-up sample: one clean row, then one problem per row. URLs are fake and only handled as text.
CLEAN_ROW = {
    "URL": "https://ok.example",
    "TLD": "example",
    "Title": "Welcome",
    "HasTitle": 1,
    "URLLength": 18,
    "ObfuscationRatio": 0.0,
    "URLSimilarityIndex": 100.0,
    "label": 1,
}


def make_rows(*changes: dict) -> pd.DataFrame:
    return pd.DataFrame([{**CLEAN_ROW, **change} for change in [{}, *changes]])


def problem_count(problems: pd.DataFrame, column: str, kind: str) -> int:
    return int(problems.loc[column, kind])


def test_catches_a_negative_count():
    problems = find_value_problems(make_rows({"URLLength": -1}))

    assert problem_count(problems, "URLLength", "out_of_range") == 1


def test_catches_a_ratio_outside_0_to_1():
    problems = find_value_problems(make_rows({"ObfuscationRatio": 1.5}))

    assert problem_count(problems, "ObfuscationRatio", "out_of_range") == 1


def test_catches_a_score_above_100():
    problems = find_value_problems(make_rows({"URLSimilarityIndex": 100.5}))

    assert problem_count(problems, "URLSimilarityIndex", "out_of_range") == 1


def test_catches_a_0_1_column_holding_anything_else():
    problems = find_value_problems(make_rows({"HasTitle": 2}))

    assert problem_count(problems, "HasTitle", "out_of_range") == 1


def test_catches_a_label_other_than_0_or_1():
    problems = find_value_problems(make_rows({"label": 3}))

    assert problem_count(problems, "label", "out_of_range") == 1


def test_counts_missing_and_empty_values():
    problems = find_value_problems(make_rows({"URLLength": None}, {"TLD": "  "}))

    assert problem_count(problems, "URLLength", "missing") == 1
    assert problem_count(problems, "TLD", "empty") == 1


def test_counts_the_no_title_placeholder_as_empty():
    problems = find_value_problems(make_rows({"Title": "0", "HasTitle": 0}))

    assert problem_count(problems, "Title", "empty") == 1


def test_a_real_title_of_0_is_not_a_placeholder():
    problems = find_value_problems(make_rows({"Title": "0", "HasTitle": 1}))

    assert problem_count(problems, "Title", "empty") == 0


def test_namibias_na_domain_is_not_missing():
    problems = find_value_problems(make_rows({"TLD": "na"}))

    assert problems.loc["TLD"].sum() == 0


def test_clean_data_has_no_problems():
    problems = find_value_problems(make_rows())

    assert problems.to_numpy().sum() == 0


def test_removes_rows_with_missing_or_out_of_range_values():
    rows = make_rows({"URLLength": -1}, {"label": 3}, {"URLLength": None}, {"TLD": ""})

    result = clean_values(rows)

    assert result.rows_before == 5
    assert result.rows_removed == 4
    assert result.rows_after == 1
    assert result.cleaned["URL"].tolist() == ["https://ok.example"]


def test_works_on_data_without_title_columns():
    rows = make_rows({"URLLength": -1}).drop(columns=["Title", "HasTitle"])

    result = clean_values(rows)

    assert result.rows_after == 1
    assert result.titles_fixed == 0


def test_replaces_the_no_title_placeholder_with_an_empty_title_and_keeps_the_row():
    rows = make_rows({"Title": "0", "HasTitle": 0})

    result = clean_values(rows)

    assert result.rows_removed == 0
    assert result.titles_fixed == 1
    assert result.cleaned["Title"].tolist() == ["Welcome", ""]


def test_cleaned_data_has_no_problems_left_and_cleaning_twice_changes_nothing():
    rows = make_rows({"URLLength": -1}, {"Title": "0", "HasTitle": 0})
    once = clean_values(rows)

    twice = clean_values(once.cleaned)

    assert find_value_problems(once.cleaned).to_numpy().sum() == 0
    pd.testing.assert_frame_equal(twice.cleaned, once.cleaned)
    assert twice.rows_removed == 0
    assert twice.titles_fixed == 0


def test_does_not_change_the_input():
    rows = make_rows({"URLLength": -1}, {"Title": "0", "HasTitle": 0})
    original = rows.copy()

    clean_values(rows)

    pd.testing.assert_frame_equal(rows, original)


def test_raises_a_clear_error_for_a_numeric_column_with_no_rule():
    with pytest.raises(ValueError, match="NewColumn"):
        find_value_problems(make_rows().assign(NewColumn=1))

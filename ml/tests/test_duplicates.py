import pandas as pd
import pytest

from cleaning.duplicates import remove_duplicate_urls

# Made-up sample. The URLs are fake and only ever handled as text.
SAMPLE = pd.DataFrame(
    {
        "URL": [
            "https://a.example",
            "https://a.example",  # same URL, same label: extra copy
            "https://b.example",
            "https://c.example",
            "https://c.example",  # same URL, different label: conflict
        ],
        "URLLength": [17, 17, 17, 17, 17],
        "label": [0, 0, 1, 1, 0],
    }
)


def test_removes_extra_copy_and_keeps_the_first():
    result = remove_duplicate_urls(SAMPLE)

    assert result.cleaned["URL"].tolist() == ["https://a.example", "https://b.example"]
    assert result.duplicate_rows_removed == 1


def test_counts_and_removes_every_copy_of_a_conflicting_url():
    result = remove_duplicate_urls(SAMPLE)

    assert result.conflicting_urls == 1
    assert result.conflicting_rows_removed == 2
    assert "https://c.example" not in result.cleaned["URL"].tolist()


def test_reports_row_counts_before_and_after():
    result = remove_duplicate_urls(SAMPLE)

    assert result.rows_before == 5
    assert result.rows_after == 2


def test_leaves_data_without_duplicates_unchanged():
    unique = SAMPLE.drop_duplicates("URL", keep=False)

    result = remove_duplicate_urls(unique)

    pd.testing.assert_frame_equal(result.cleaned, unique)
    assert result.duplicate_rows_removed == 0
    assert result.conflicting_urls == 0


def test_does_not_change_the_input():
    original = SAMPLE.copy()

    remove_duplicate_urls(SAMPLE)

    pd.testing.assert_frame_equal(SAMPLE, original)


def test_running_twice_gives_the_same_result():
    once = remove_duplicate_urls(SAMPLE).cleaned

    twice = remove_duplicate_urls(once)

    pd.testing.assert_frame_equal(twice.cleaned, once)
    assert twice.duplicate_rows_removed == 0


def test_rows_with_a_missing_url_are_not_treated_as_duplicates():
    missing = pd.DataFrame({"URL": [None, None], "label": [0, 0]})

    result = remove_duplicate_urls(missing)

    assert result.rows_after == 2
    assert result.duplicate_rows_removed == 0


def test_raises_a_clear_error_when_a_column_is_missing():
    with pytest.raises(ValueError, match="label"):
        remove_duplicate_urls(SAMPLE.drop(columns="label"))

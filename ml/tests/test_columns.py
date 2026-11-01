import pandas as pd
import pytest

from leakage.columns import filename_leak, filename_shape, url_similarity_for_legitimate

# Made-up sample in the cleaned coding: 1 = phishing, 0 = legitimate.
SAMPLE = pd.DataFrame(
    {
        "FILENAME": ["123456.txt", "654321.txt", "mw123456.txt", "1234567.txt", "12345.txt"],
        "URLSimilarityIndex": [100.0, 100.0, 42.5, 100.0, 61.0],
        "label": [0, 0, 1, 1, 1],
    }
)


@pytest.mark.parametrize(
    ("name", "shape"),
    [
        ("123456.txt", "6 digits .txt"),
        ("mw123456.txt", "mw + 6 digits .txt"),
        ("oph04268.txt", "oph + 5 digits .txt"),
        ("8044250.txt", "7 digits .txt"),
        ("op4.txt", "op + 1 digit .txt"),
        ("readme", "other"),
    ],
)
def test_filename_shape_keeps_the_prefix_digit_count_and_extension(name, shape):
    assert filename_shape(name) == shape


def test_filename_leak_counts_each_shape_per_class():
    result = filename_leak(SAMPLE)

    assert result.shapes.loc["6 digits .txt"].tolist() == [2, 0]
    assert result.shapes.loc["mw + 6 digits .txt"].tolist() == [0, 1]
    assert result.shapes.columns.tolist() == ["Legitimate", "Phishing"]


def test_filename_leak_scores_guessing_the_label_from_the_shape_alone():
    result = filename_leak(SAMPLE)

    # Each shape is guessed as its most common label: every row is right.
    assert result.accuracy == pytest.approx(1.0)
    assert result.phishing_only_shapes == ["5 digits .txt", "7 digits .txt", "mw + 6 digits .txt"]


def test_url_similarity_reports_the_legitimate_values():
    result = url_similarity_for_legitimate(SAMPLE)

    assert result.rows == 2
    assert result.minimum == 100
    assert result.maximum == 100
    assert result.all_100
    assert result.phishing_share_at_100 == pytest.approx(1 / 3)


def test_url_similarity_rejects_the_finding_when_a_legitimate_row_is_not_100():
    rows = SAMPLE.assign(URLSimilarityIndex=[100.0, 99.0, 42.5, 100.0, 61.0])

    assert not url_similarity_for_legitimate(rows).all_100

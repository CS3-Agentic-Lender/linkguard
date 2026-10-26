import pandas as pd
import pytest

from cleaning.labels import PHISHING, LEGITIMATE, recode_label

# Made-up sample in the raw file's coding: 1 = legitimate, 0 = phishing. URLs are fake.
RAW = pd.DataFrame(
    {
        "URL": ["https://safe.example", "https://bad.example", "https://bad2.example"],
        "label": [1, 0, 0],
    },
    index=[10, 20, 30],
)


def test_flips_the_label_so_1_means_phishing():
    result = recode_label(RAW)

    assert result.recoded["label"].tolist() == [0, 1, 1]
    assert PHISHING == 1
    assert LEGITIMATE == 0


def test_every_raw_0_becomes_1_and_every_raw_1_becomes_0():
    result = recode_label(RAW)

    raw_label = RAW["label"]
    new_label = result.recoded["label"]
    assert (new_label[raw_label == 0] == 1).all()
    assert (new_label[raw_label == 1] == 0).all()


def test_reports_the_counts_after_the_flip():
    result = recode_label(RAW)

    assert result.phishing == 2
    assert result.legitimate == 1


def test_keeps_every_other_column_and_the_row_index():
    result = recode_label(RAW)

    assert result.recoded.columns.tolist() == RAW.columns.tolist()
    assert result.recoded["URL"].tolist() == RAW["URL"].tolist()
    assert result.recoded.index.tolist() == [10, 20, 30]


def test_does_not_change_the_input():
    original = RAW.copy()

    recode_label(RAW)

    pd.testing.assert_frame_equal(RAW, original)


def test_refuses_a_label_other_than_0_or_1():
    with pytest.raises(ValueError, match="0 or 1"):
        recode_label(RAW.assign(label=[1, 0, 2]))


def test_raises_a_clear_error_when_the_label_column_is_missing():
    with pytest.raises(ValueError, match="label"):
        recode_label(RAW.drop(columns="label"))

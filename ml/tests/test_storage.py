import pandas as pd

from cleaning.storage import CLEANED_CSV_NAME, load_cleaned, save_cleaned

# Made-up cleaned sample. It includes the two values a CSV round-trip can break:
# a blanked title ("") and Namibia's real domain ("na"). URLs are fake.
CLEANED = pd.DataFrame(
    {
        "URL": ["https://a.example", "https://b.example.na", "https://c.example"],
        "TLD": ["example", "na", "example"],
        "Title": ["A page", "", "NULL"],
        "HasTitle": [1, 0, 1],
        "ObfuscationRatio": [0.0, 0.125, 0.348],
        "label": [0, 1, 1],
    },
    index=[3, 8, 42],
)


def test_saves_and_reads_back_the_same_rows_and_columns(tmp_path):
    path = save_cleaned(CLEANED, tmp_path / CLEANED_CSV_NAME)

    loaded = load_cleaned(path)

    assert loaded.shape == CLEANED.shape
    assert loaded.columns.tolist() == CLEANED.columns.tolist()
    pd.testing.assert_frame_equal(loaded, CLEANED.reset_index(drop=True))


def test_reading_back_adds_no_missing_values(tmp_path):
    path = save_cleaned(CLEANED, tmp_path / CLEANED_CSV_NAME)

    loaded = load_cleaned(path)

    assert int(loaded.isna().sum().sum()) == 0
    assert loaded["Title"].tolist() == ["A page", "", "NULL"]
    assert loaded["TLD"].tolist() == ["example", "na", "example"]


def test_creates_the_folder_if_needed(tmp_path):
    path = save_cleaned(CLEANED, tmp_path / "data" / CLEANED_CSV_NAME)

    assert path.exists()


def test_saving_does_not_change_the_data(tmp_path):
    original = CLEANED.copy()

    save_cleaned(CLEANED, tmp_path / CLEANED_CSV_NAME)

    pd.testing.assert_frame_equal(CLEANED, original)

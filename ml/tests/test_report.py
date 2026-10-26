import pandas as pd
import pytest

from cleaning.report import CleaningStep, run_cleaning, steps_table

# Made-up raw sample in the raw file's coding (1 = legitimate, 0 = phishing). URLs are fake.
RAW = pd.DataFrame(
    {
        "URL": [
            "https://a.example",
            "https://a.example",  # duplicate URL
            "https://b.example",
            "https://c.example",  # negative count, removed by the value checks
            "https://d.example",
        ],
        "Title": ["A", "A", "0", "C", "D"],
        "HasTitle": [1, 1, 0, 1, 1],
        "URLLength": [17, 17, 17, -1, 17],
        "label": [1, 1, 0, 1, 0],
    }
)


def test_runs_every_step_in_order_from_the_raw_data():
    run = run_cleaning(RAW)

    assert [step.name for step in run.steps] == [
        "1. Duplicate URLs",
        "2. Missing, empty and out-of-range values",
        "3. Recode the label",
    ]
    assert [(step.rows_before, step.rows_after) for step in run.steps] == [(5, 4), (4, 3), (3, 3)]


def test_the_cleaned_data_is_deduplicated_fixed_and_recoded():
    run = run_cleaning(RAW)

    assert run.cleaned["URL"].tolist() == ["https://a.example", "https://b.example", "https://d.example"]
    assert run.cleaned["Title"].tolist() == ["A", "", "D"]
    assert run.cleaned["label"].tolist() == [0, 1, 1]


def test_running_again_from_the_raw_data_gives_the_same_numbers():
    first = run_cleaning(RAW)

    second = run_cleaning(RAW)

    assert first.steps == second.steps
    pd.testing.assert_frame_equal(first.cleaned, second.cleaned)


def test_does_not_change_the_raw_data():
    original = RAW.copy()

    run_cleaning(RAW)

    pd.testing.assert_frame_equal(RAW, original)


def test_steps_table_shows_rows_before_after_and_removed():
    steps = (CleaningStep("first", 10, 7), CleaningStep("second", 7, 7))

    table = steps_table(steps)

    assert table.columns.tolist() == ["Step", "Rows before", "Rows after", "Rows removed"]
    assert table["Rows removed"].tolist()[:-1] == [3, 0]
    assert table.iloc[-1]["Step"] == "Total"
    assert table.iloc[-1][["Rows before", "Rows after", "Rows removed"]].tolist() == [10, 7, 3]


def test_steps_table_refuses_steps_that_do_not_chain():
    steps = (CleaningStep("first", 10, 7), CleaningStep("second", 8, 8))

    with pytest.raises(ValueError, match="second"):
        steps_table(steps)


def test_steps_table_needs_at_least_one_step():
    with pytest.raises(ValueError, match="at least one"):
        steps_table(())

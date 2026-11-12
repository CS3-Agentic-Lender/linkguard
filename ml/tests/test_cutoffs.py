"""Checks on ml/models/cutoffs.json, the risk-level cut-offs the backend reads.

The backend turns a phishing score into Safe, Suspicious or High risk with these two values, so
the file must keep exactly this shape.
"""

import json

from training.pipeline import ML_DIR

CUTOFFS_PATH = ML_DIR / "models" / "cutoffs.json"


def test_the_file_has_exactly_a_lower_and_an_upper_cutoff():
    cutoffs = json.loads(CUTOFFS_PATH.read_text())

    assert set(cutoffs) == {"lower", "upper"}
    assert all(isinstance(value, float) for value in cutoffs.values())


def test_the_lower_cutoff_is_below_the_upper_one_and_both_are_scores():
    cutoffs = json.loads(CUTOFFS_PATH.read_text())

    assert 0 < cutoffs["lower"] < cutoffs["upper"] < 1


def test_the_agreed_values_are_saved():
    assert json.loads(CUTOFFS_PATH.read_text()) == {"lower": 0.20, "upper": 0.60}

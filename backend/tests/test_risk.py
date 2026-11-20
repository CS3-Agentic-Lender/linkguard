import json
import math

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.model import ModelFileMissing, ModelFileWrong, phishing_score
from app.risk import CUTOFFS_FILE, Cutoffs, load_cutoffs, risk_level
from conftest import CUTOFFS

AGREED = Cutoffs(**CUTOFFS)
LOWER, UPPER = AGREED.lower, AGREED.upper

# Made-up link on a reserved name, only ever handled as text.
LINK = "https://paypa1-support-2024.example/verify"


def just_below(value):
    return math.nextafter(value, -math.inf)


def just_above(value):
    return math.nextafter(value, math.inf)


@pytest.mark.parametrize(
    ("score", "level"),
    [
        (0.0, "Safe"),
        (just_below(LOWER), "Safe"),
        (LOWER, "Suspicious"),
        (just_above(LOWER), "Suspicious"),
        (just_below(UPPER), "Suspicious"),
        (UPPER, "High risk"),
        (just_above(UPPER), "High risk"),
        (1.0, "High risk"),
    ],
)
def test_scores_at_and_either_side_of_each_cutoff(score, level):
    assert risk_level(score, AGREED) == level


def test_scan_reply_holds_the_level_and_the_score(client):
    reply = client.post("/scan", json={"url": LINK}).json()

    score = phishing_score(client.app.state.model, LINK)
    assert reply["score"] == pytest.approx(score)
    assert 0 <= reply["score"] <= 1
    assert reply["risk_level"] == risk_level(score, AGREED)
    assert reply["placeholder"] is False


def test_the_cutoffs_are_read_from_the_file(client):
    assert client.app.state.cutoffs == AGREED


def write_cutoffs(folder, lower, upper):
    (folder / CUTOFFS_FILE).write_text(json.dumps({"lower": lower, "upper": upper}), encoding="utf-8")


def test_changing_the_file_changes_the_level_without_a_code_change(fixture_model_dir):
    levels = []
    # The same link, scored by the same model: only the cut-offs file changes.
    for lower, upper in [(0.0001, 0.0002), (0.9998, 0.9999)]:
        write_cutoffs(fixture_model_dir, lower, upper)
        with TestClient(app) as client:
            levels.append(client.post("/scan", json={"url": LINK}).json()["risk_level"])

    assert levels == ["High risk", "Safe"]


def test_startup_stops_and_names_a_missing_cutoffs_file(fixture_model_dir):
    (fixture_model_dir / CUTOFFS_FILE).unlink()

    with pytest.raises(ModelFileMissing, match=CUTOFFS_FILE) as stopped:
        with TestClient(app):
            pass

    assert str(fixture_model_dir / CUTOFFS_FILE) in str(stopped.value)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("not json", "not valid JSON"),
        ("[0.2, 0.6]", 'exactly "lower" and "upper"'),
        ('{"lower": 0.2}', 'exactly "lower" and "upper"'),
        ('{"lower": 0.2, "upper": 0.6, "middle": 0.4}', 'exactly "lower" and "upper"'),
        ('{"lower": "0.2", "upper": 0.6}', "must be numbers"),
        ('{"lower": true, "upper": 0.6}', "must be numbers"),
        ('{"lower": 0.6, "upper": 0.2}', "lower below upper"),
        ('{"lower": 0.4, "upper": 0.4}', "lower below upper"),
        ('{"lower": -0.1, "upper": 0.6}', "between 0 and 1"),
        ('{"lower": 0.2, "upper": 1.5}', "between 0 and 1"),
    ],
)
def test_startup_stops_on_a_wrong_cutoffs_file(fixture_model_dir, text, message):
    (fixture_model_dir / CUTOFFS_FILE).write_text(text, encoding="utf-8")

    with pytest.raises(ModelFileWrong, match=message):
        load_cutoffs(fixture_model_dir)


def test_whole_numbers_are_allowed_as_cutoffs(fixture_model_dir):
    write_cutoffs(fixture_model_dir, 0, 1)

    assert load_cutoffs(fixture_model_dir) == Cutoffs(lower=0.0, upper=1.0)

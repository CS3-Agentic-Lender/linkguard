"""The /scan reply refuses combinations the result card can't show.

The result card shows its "couldn't check" message for a reply that contradicts
itself, so the backend stops such a reply being built at all.
"""

import pytest
from pydantic import ValidationError

from app.main import ScanResponse

# Made-up link on a reserved name. It is only ever handled as text.
LINK = "https://login.example/verify"


def reply(**fields):
    return ScanResponse(**{"url": LINK, **fields})


# Criterion 1: a placeholder reply carries no result


@pytest.mark.parametrize(
    "result",
    [
        {"risk_level": "High risk", "score": None, "reasons": []},
        {"risk_level": None, "score": 0.9, "reasons": []},
        {"risk_level": None, "score": None, "reasons": ["The website name contains a lot of numbers."]},
    ],
)
def test_a_placeholder_reply_with_a_result_is_refused(result):
    with pytest.raises(ValidationError, match="placeholder reply"):
        reply(placeholder=True, **result)


# Criterion 2: a real reply has a risk level and a score


@pytest.mark.parametrize(
    "result",
    [
        {"risk_level": None, "score": 0.9},
        {"risk_level": "High risk", "score": None},
        {"risk_level": None, "score": None},
    ],
)
def test_a_real_reply_without_a_level_and_score_is_refused(result):
    with pytest.raises(ValidationError, match="real reply"):
        reply(placeholder=False, reasons=[], **result)


@pytest.mark.parametrize("score", [-0.1, 1.1])
def test_a_score_outside_0_to_1_is_refused(score):
    with pytest.raises(ValidationError):
        reply(placeholder=False, risk_level="Suspicious", score=score, reasons=[])


def test_an_unknown_risk_level_is_refused():
    with pytest.raises(ValidationError):
        reply(placeholder=False, risk_level="Dangerous", score=0.9, reasons=[])


# Criterion 3: a Safe reply carries no reasons


def test_a_safe_reply_with_reasons_is_refused():
    with pytest.raises(ValidationError, match="Safe reply"):
        reply(placeholder=False, risk_level="Safe", score=0.1, reasons=["The website name is very long."])


# Criterion 4: the replies the page expects still build


def test_the_placeholder_reply_still_builds():
    built = reply(placeholder=True, risk_level=None, score=None, reasons=[])
    assert built.placeholder is True


@pytest.mark.parametrize(
    ("level", "score", "reasons"),
    [
        ("Safe", 0.1, []),
        ("Suspicious", 0.4, ["The website name is very long."]),
        ("High risk", 0.95, ["The website name contains a lot of numbers."]),
        ("Suspicious", 0.4, []),
    ],
)
def test_real_replies_still_build(level, score, reasons):
    built = reply(placeholder=False, risk_level=level, score=score, reasons=reasons)
    assert (built.risk_level, built.score, built.reasons) == (level, score, reasons)

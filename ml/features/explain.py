"""Pick up to three reasons for a link from how much each feature pushed its score.

The rules are in docs/adr/0004-explanation-method.md, "Picking the reasons". This module
only picks. Working out the contributions depends on the final model and lives elsewhere.

- contributions: how much each feature moved this link's phishing log-odds away from an
  average training link's. Above zero means it pushed the score towards phishing.
- scaled: the link's feature values after the saved scaler. The scaler is fitted on the
  training rows, so 0 is an average training link.
"""

import math
from types import MappingProxyType
from typing import Mapping

from features.hostname import FEATURE_NAMES

MAX_REASONS = 3

# The side of the average each sentence describes: 1 above it, -1 below it. A feature is
# only a reason when the link is on that side, so its sentence is true for the link.
# Only features with a sentence are here, so never-shown features can never be picked.
# A test checks these are exactly the features in features.reasons.REASON_SENTENCES.
RAISING_SIDE: Mapping[str, int] = MappingProxyType(
    {
        "HostnameLength": 1,  # longer name
        "IsDomainIP": 1,  # uses an IP address
        "LetterRatioInHostname": -1,  # smaller share of letters
        "NoOfDigitsInHostname": 1,  # more digits
        "DigitRatioInHostname": 1,  # larger share of digits
        "NoOfSpecialCharsInHostname": 1,  # more dots or hyphens
    }
)

# Their sentences say nearly the same thing, so at most one of them is shown.
# On a tie the first (the count) is kept.
DIGIT_PAIR = ("NoOfDigitsInHostname", "DigitRatioInHostname")


def pick_reasons(contributions: Mapping[str, float], scaled: Mapping[str, float]) -> tuple[str, ...]:
    """Up to MAX_REASONS feature names that raised this link's score, largest first.

    Never returns a feature that lowered the score, one that is never shown, or one whose
    sentence is untrue for the link. Can return an empty tuple. Equal pushes keep the
    extractor's feature order, so the same link always gets the same reasons.

    Raises ValueError for an unknown feature name, a contribution with no scaled value,
    or a value that is not a finite number.
    """
    _check(contributions, scaled)
    raised = [name for name in FEATURE_NAMES if name in contributions and _is_reason(name, contributions, scaled)]
    raised = _drop_smaller_digit_reason(raised, contributions)
    largest_first = sorted(raised, key=lambda name: -contributions[name])
    return tuple(largest_first[:MAX_REASONS])


def _is_reason(name: str, contributions: Mapping[str, float], scaled: Mapping[str, float]) -> bool:
    side = RAISING_SIDE.get(name)
    return side is not None and contributions[name] > 0 and side * scaled[name] > 0


def _drop_smaller_digit_reason(raised: list[str], contributions: Mapping[str, float]) -> list[str]:
    count, share = DIGIT_PAIR
    if count not in raised or share not in raised:
        return raised
    smaller = share if contributions[count] >= contributions[share] else count
    return [name for name in raised if name != smaller]


def _check(contributions: Mapping[str, float], scaled: Mapping[str, float]) -> None:
    for name, value in contributions.items():
        if name not in FEATURE_NAMES:
            raise ValueError(f"{name} is not one of the hostname features.")
        if name not in scaled:
            raise ValueError(f"{name} has a contribution but no scaled value.")
        if not math.isfinite(value):
            raise ValueError(f"The contribution for {name} is not a finite number: {value}.")
        if not math.isfinite(scaled[name]):
            raise ValueError(f"The scaled value for {name} is not a finite number: {scaled[name]}.")

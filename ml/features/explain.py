"""Pick up to three reasons for a link from how much each feature pushed its score.

The method is in docs/adr/0004-explanation-method.md: "The measure" and "Picking the reasons".

- contributions: how much each feature moved this link's phishing log-odds away from an
  average training link's. Above zero means it pushed the score towards phishing.
- scaled: the link's feature values after the saved scaler. The scaler is fitted on the
  training rows, so 0 is an average training link.

For the saved logistic regression model, a feature's contribution is its coefficient times
its scaled value. This module reads the model's fitted attributes and never imports
scikit-learn, so the shared package keeps no dependencies.
"""

import math
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

from features.hostname import FEATURE_NAMES

MAX_REASONS = 3

# The saved model's shape (ml/training/final_model.py): a step that keeps the final features
# out of the ten scaled ones, by position in FEATURE_NAMES, then logistic regression.
KEEP_STEP = "keep_final_features"
KEPT_COLUMNS = "final"
MODEL_STEP = "model"
PHISHING_LABEL = 1  # the cleaned dataset's label for phishing

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

# Their sentences all say the website name is mostly numbers, so at most one of them is
# shown: the one that pushed most. On a tie the first in this order is kept.
NUMBER_GROUP = ("NoOfDigitsInHostname", "DigitRatioInHostname", "LetterRatioInHostname")


def reasons_for_link(model: Any, scaled: Mapping[str, float]) -> tuple[str, ...]:
    """Up to MAX_REASONS feature names that raised this link's score, largest first.

    model is the saved model. scaled holds the link's ten scaled feature values by name.
    Can return an empty tuple.
    """
    return pick_reasons(linear_contributions(model_coefficients(model), scaled), scaled)


def model_coefficients(model: Any) -> dict[str, float]:
    """The saved model's coefficient for each feature it keeps, by name, in the model's order.

    Raises ValueError when the model is not the saved shape, or its second class (the one
    its coefficients point towards) is not phishing.
    """
    try:
        kept = {name: columns for name, _, columns in model.named_steps[KEEP_STEP].transformers_}[KEPT_COLUMNS]
        estimator = model.named_steps[MODEL_STEP]
        weights = [float(weight) for weight in estimator.coef_[0]]
        classes = list(estimator.classes_)
    except (AttributeError, KeyError, TypeError, IndexError) as error:
        raise ValueError(
            f"The model is not the saved model's shape ({KEEP_STEP}, then {MODEL_STEP}): {error!r}"
        ) from error
    if len(classes) != 2 or classes[1] != PHISHING_LABEL:
        raise ValueError(f"The model's second class must be phishing ({PHISHING_LABEL}), not {classes}.")
    if len(kept) != len(weights):
        raise ValueError(f"The model keeps {len(kept)} features but has {len(weights)} coefficients.")
    return {FEATURE_NAMES[position]: weight for position, weight in zip(kept, weights)}


def linear_contributions(coefficients: Mapping[str, float], scaled: Mapping[str, float]) -> dict[str, float]:
    """Each model feature's push on the log-odds: its coefficient times its scaled value.

    Features the model does not use get no entry. Raises ValueError when a model feature
    has no scaled value.
    """
    missing = [name for name in coefficients if name not in scaled]
    if missing:
        raise ValueError(f"No scaled value for {', '.join(missing)}.")
    return {name: weight * scaled[name] for name, weight in coefficients.items()}


def pick_reasons(contributions: Mapping[str, float], scaled: Mapping[str, float]) -> tuple[str, ...]:
    """Up to MAX_REASONS feature names that raised this link's score, largest first.

    Never returns a feature that lowered the score, one that is never shown, or one whose
    sentence is untrue for the link. Can return an empty tuple. Equal pushes keep the
    extractor's feature order, so the same link always gets the same reasons.

    Raises ValueError for an unknown feature name, a contribution with no scaled value,
    or a value that is not a finite number.
    """
    _check(contributions, scaled)
    raised = [name for name in FEATURE_NAMES if name in contributions and can_be_reason(name, contributions, scaled)]
    kept = kept_number_reason(raised, contributions)
    raised = [name for name in raised if name not in NUMBER_GROUP or name == kept]
    largest_first = sorted(raised, key=lambda name: -contributions[name])
    return tuple(largest_first[:MAX_REASONS])


def can_be_reason(name: str, contributions: Mapping[str, float], scaled: Mapping[str, float]) -> bool:
    """True when the feature has a sentence, raised the score, and its sentence is true for the link."""
    side = RAISING_SIDE.get(name)
    return side is not None and contributions[name] > 0 and side * scaled[name] > 0


def kept_number_reason(candidates: Sequence[str], contributions: Mapping[str, float]) -> str | None:
    """The one number feature among candidates that may be shown, or None if there is none.

    It is the one that pushed most. On a tie the first in NUMBER_GROUP is kept.
    """
    numbers = [name for name in NUMBER_GROUP if name in candidates]
    return max(numbers, key=lambda name: contributions[name], default=None)


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

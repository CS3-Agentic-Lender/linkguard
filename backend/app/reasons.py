import logging

from features.explain import reasons_for_link
from features.hostname import FEATURE_NAMES
from features.reasons import reason_for

from app.model import LoadedModel
from app.risk import RiskLevel

logger = logging.getLogger(__name__)


def reasons_for_scan(loaded: LoadedModel, scaled: list[float], level: RiskLevel) -> list[str]:
    """Up to three plain sentences on why a Suspicious or High risk link looks risky.

    They come from the features that pushed this link's score up most, largest first,
    picked by the shared reasons code in ml/features (docs/adr/0004). A Safe link gets
    none, and a risky link can get none too, when no single feature stood out.

    If the reasons can't be worked out, the link still gets its level and score, with no
    reasons, and the problem is logged. The shared code raises ValueError for a value
    that isn't a finite number or an explainer that gives the wrong number of pushes.
    """
    if level == "Safe":
        return []
    try:
        names = reasons_for_link(loaded.model, loaded.explainer, dict(zip(FEATURE_NAMES, scaled)))
    except ValueError as error:
        logger.warning("Couldn't work out the reasons for a %s link, so it gets none: %s", level, error)
        return []
    # The picking code only returns features that have a sentence, so none is None.
    return [reason_for(name) for name in names]

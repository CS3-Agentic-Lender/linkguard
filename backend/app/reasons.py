from features.explain import reasons_for_link
from features.hostname import FEATURE_NAMES
from features.reasons import reason_for

from app.model import LoadedModel
from app.risk import RiskLevel


def reasons_for_scan(loaded: LoadedModel, scaled: list[float], level: RiskLevel) -> list[str]:
    """Up to three plain sentences on why a Suspicious or High risk link looks risky.

    They come from the features that pushed this link's score up most, largest first,
    picked by the shared reasons code in ml/features (docs/adr/0004). A Safe link gets
    none, and a risky link can get none too, when no single feature stood out.
    """
    if level == "Safe":
        return []
    names = reasons_for_link(loaded.model, loaded.explainer, dict(zip(FEATURE_NAMES, scaled)))
    # The picking code only returns features that have a sentence, so none is None.
    return [reason_for(name) for name in names]

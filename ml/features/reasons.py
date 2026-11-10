"""The plain sentence a user sees for each feature that raised a link's score.

The result page and the /scan reply read their reasons from here, so the wording
is kept in one place. The same sentences are listed in docs/reason-sentences.md,
and a test checks the two match word for word.

A feature is never shown when its strength may come from how the dataset was
built rather than from phishing, or when the model does not use it.
"""

from types import MappingProxyType
from typing import Mapping

FINAL_LIST = "ml/reports/final_feature_list.md"

REASON_SENTENCES: Mapping[str, str] = MappingProxyType(
    {
        "HostnameLength": "The website name in this link is unusually long.",
        "IsDomainIP": "This link uses a string of numbers instead of a website name.",
        "LetterRatioInHostname": "Much of the website name is numbers or symbols, not letters.",
        "NoOfDigitsInHostname": "The website name contains a lot of numbers.",
        "DigitRatioInHostname": "Numbers make up a large part of the website name.",
        "NoOfSpecialCharsInHostname": "The website name has a lot of dots or hyphens.",
    }
)

NOT_SHOWN: Mapping[str, str] = MappingProxyType(
    {
        "TLDLength": (
            "Marked to watch: common endings like .com are typical of the big sites' front pages that make up "
            f"the dataset's legitimate links, so it may not be a real warning sign (see {FINAL_LIST})."
        ),
        "NoOfSubDomain": (
            "Marked to watch: few subdomains is typical of the big sites' front pages that make up "
            f"the dataset's legitimate links, so it may not be a real warning sign (see {FINAL_LIST})."
        ),
        "NoOfLettersInHostname": f"The model does not use it, because it copies other features (see {FINAL_LIST}).",
        "SpecialCharRatioInHostname": (
            f"The model does not use it, because it copies other features (see {FINAL_LIST})."
        ),
    }
)


def reason_for(name: str) -> str | None:
    """The sentence for one feature, or None if that feature is never shown.

    Raises KeyError naming the feature if it is not one of the extractor's features.
    """
    if name in REASON_SENTENCES:
        return REASON_SENTENCES[name]
    if name in NOT_SHOWN:
        return None
    raise KeyError(f"No reason entry for {name}.")

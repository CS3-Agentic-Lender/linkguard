"""Picking up to three reasons for a link from how much each feature pushed its score.

The rules come from docs/adr/0004-explanation-method.md, "Picking the reasons".
Contributions are in log-odds: above zero pushed the score towards phishing.
Scaled values are the saved scaler's output: 0 is an average training link.
"""

import math

import pytest

from features.explain import (
    MAX_REASONS,
    NUMBER_GROUP,
    RAISING_SIDE,
    kept_number_reason,
    pick_reasons,
)
from features.reasons import NOT_SHOWN, REASON_SENTENCES

# A link on the phishing side of every shown feature: long name, an IP address,
# few letters, many digits and many dots or hyphens.
PHISHING_SIDE = {
    "HostnameLength": 2.0,
    "IsDomainIP": 3.0,
    "TLDLength": 1.0,
    "NoOfSubDomain": 1.0,
    "LetterRatioInHostname": -2.0,
    "NoOfDigitsInHostname": 2.0,
    "DigitRatioInHostname": 2.0,
    "NoOfSpecialCharsInHostname": 2.0,
}


def _contributions(**raised: float) -> dict[str, float]:
    """Every model feature at 0, apart from the ones given."""
    return {name: raised.get(name, 0.0) for name in PHISHING_SIDE}


# The two links ALG-104 asks for


def test_link_with_several_raising_features_gets_the_three_largest_largest_first():
    contributions = _contributions(
        HostnameLength=0.4, IsDomainIP=1.2, NoOfDigitsInHostname=0.9, NoOfSpecialCharsInHostname=0.2
    )

    reasons = pick_reasons(contributions, PHISHING_SIDE)

    assert reasons == ("IsDomainIP", "NoOfDigitsInHostname", "HostnameLength")


def test_link_with_no_raising_features_gets_no_reasons():
    contributions = _contributions(HostnameLength=-0.5, IsDomainIP=-0.1, LetterRatioInHostname=-0.3)

    assert pick_reasons(contributions, PHISHING_SIDE) == ()


# Only features that raised the score


def test_a_feature_that_lowered_the_score_is_never_picked():
    contributions = _contributions(HostnameLength=-3.0, NoOfSpecialCharsInHostname=0.1)

    assert pick_reasons(contributions, PHISHING_SIDE) == ("NoOfSpecialCharsInHostname",)


def test_a_feature_that_did_not_move_the_score_is_not_picked():
    assert pick_reasons(_contributions(), PHISHING_SIDE) == ()


def test_never_more_than_three_reasons():
    contributions = _contributions(
        HostnameLength=0.5,
        IsDomainIP=0.4,
        LetterRatioInHostname=0.3,
        NoOfDigitsInHostname=0.2,
        NoOfSpecialCharsInHostname=0.1,
    )

    reasons = pick_reasons(contributions, PHISHING_SIDE)

    assert len(reasons) == MAX_REASONS == 3


# Never-shown features


@pytest.mark.parametrize("hidden", ["TLDLength", "NoOfSubDomain"])
def test_a_never_shown_feature_is_skipped_even_when_it_raised_the_score_most(hidden):
    contributions = _contributions(HostnameLength=0.3, **{hidden: 5.0})

    assert pick_reasons(contributions, PHISHING_SIDE) == ("HostnameLength",)


def test_a_link_raised_only_by_never_shown_features_gets_no_reasons():
    contributions = _contributions(TLDLength=1.0, NoOfSubDomain=2.0)

    assert pick_reasons(contributions, PHISHING_SIDE) == ()


# The link must be on the side its sentence describes


def test_a_short_name_is_not_called_unusually_long_even_if_its_push_was_up():
    scaled = {**PHISHING_SIDE, "HostnameLength": -1.0}

    assert pick_reasons(_contributions(HostnameLength=0.6), scaled) == ()


def test_a_name_with_more_letters_than_average_is_not_called_numbers_or_symbols():
    scaled = {**PHISHING_SIDE, "LetterRatioInHostname": 1.0}

    assert pick_reasons(_contributions(LetterRatioInHostname=0.6), scaled) == ()


def test_a_name_with_fewer_letters_than_average_can_be_a_reason():
    assert pick_reasons(_contributions(LetterRatioInHostname=0.6), PHISHING_SIDE) == ("LetterRatioInHostname",)


def test_an_ip_address_reason_needs_the_link_to_use_an_ip_address():
    not_an_ip = {**PHISHING_SIDE, "IsDomainIP": -0.1}

    assert pick_reasons(_contributions(IsDomainIP=0.6), not_an_ip) == ()


def test_a_value_exactly_at_the_average_is_not_on_either_side():
    at_average = {**PHISHING_SIDE, "HostnameLength": 0.0}

    assert pick_reasons(_contributions(HostnameLength=0.6), at_average) == ()


# The three number sentences say nearly the same thing: digit count, digit share and letter share


def test_the_number_group_is_the_digit_count_digit_share_and_letter_share():
    assert NUMBER_GROUP == ("NoOfDigitsInHostname", "DigitRatioInHostname", "LetterRatioInHostname")


@pytest.mark.parametrize(
    ("count", "share", "letters", "kept"),
    [
        (0.9, 0.4, 0.2, "NoOfDigitsInHostname"),
        (0.4, 0.9, 0.2, "DigitRatioInHostname"),
        (0.4, 0.2, 0.9, "LetterRatioInHostname"),
    ],
)
def test_only_the_largest_number_reason_is_kept(count, share, letters, kept):
    contributions = _contributions(
        NoOfDigitsInHostname=count, DigitRatioInHostname=share, LetterRatioInHostname=letters
    )

    assert pick_reasons(contributions, PHISHING_SIDE) == (kept,)


def test_an_ip_address_link_gets_one_number_reason_not_two():
    # The hand check's IP link: letter share and digit count both raised the score.
    contributions = _contributions(
        LetterRatioInHostname=3.9, NoOfDigitsInHostname=3.5, NoOfSpecialCharsInHostname=0.9, IsDomainIP=0.2
    )

    reasons = pick_reasons(contributions, PHISHING_SIDE)

    assert reasons == ("LetterRatioInHostname", "NoOfSpecialCharsInHostname", "IsDomainIP")


def test_dropping_a_number_reason_lets_the_next_feature_in():
    contributions = _contributions(
        NoOfDigitsInHostname=0.9,
        DigitRatioInHostname=0.8,
        LetterRatioInHostname=0.7,
        HostnameLength=0.5,
        NoOfSpecialCharsInHostname=0.3,
    )

    reasons = pick_reasons(contributions, PHISHING_SIDE)

    assert reasons == ("NoOfDigitsInHostname", "HostnameLength", "NoOfSpecialCharsInHostname")


@pytest.mark.parametrize(
    ("tied", "kept"),
    [
        ({"NoOfDigitsInHostname": 0.5, "DigitRatioInHostname": 0.5}, "NoOfDigitsInHostname"),
        ({"DigitRatioInHostname": 0.5, "LetterRatioInHostname": 0.5}, "DigitRatioInHostname"),
        ({"NoOfDigitsInHostname": 0.5, "LetterRatioInHostname": 0.5}, "NoOfDigitsInHostname"),
    ],
)
def test_equal_number_reasons_keep_the_first_in_the_group(tied, kept):
    assert pick_reasons(_contributions(**tied), PHISHING_SIDE) == (kept,)


def test_a_number_reason_that_fails_its_side_does_not_knock_out_the_others():
    scaled = {**PHISHING_SIDE, "NoOfDigitsInHostname": -1.0}
    contributions = _contributions(NoOfDigitsInHostname=0.9, DigitRatioInHostname=0.4, LetterRatioInHostname=0.3)

    assert pick_reasons(contributions, scaled) == ("DigitRatioInHostname",)


def test_kept_number_reason_names_none_when_no_number_feature_qualifies():
    assert kept_number_reason(("HostnameLength",), _contributions(HostnameLength=0.5)) is None


# Same answer every time


def test_equal_pushes_keep_the_extractor_order():
    contributions = _contributions(NoOfSpecialCharsInHostname=0.5, HostnameLength=0.5)

    assert pick_reasons(contributions, PHISHING_SIDE) == ("HostnameLength", "NoOfSpecialCharsInHostname")


def test_inputs_are_not_changed():
    contributions = _contributions(HostnameLength=0.5)
    before = (dict(contributions), dict(PHISHING_SIDE))

    pick_reasons(contributions, PHISHING_SIDE)

    assert (contributions, PHISHING_SIDE) == before


# Bad input fails loudly


def test_an_unknown_feature_name_is_rejected():
    with pytest.raises(ValueError, match="NotAFeature"):
        pick_reasons({"NotAFeature": 1.0}, {"NotAFeature": 1.0})


def test_a_contribution_with_no_scaled_value_is_rejected():
    scaled = {name: value for name, value in PHISHING_SIDE.items() if name != "HostnameLength"}

    with pytest.raises(ValueError, match="HostnameLength"):
        pick_reasons(_contributions(HostnameLength=0.5), scaled)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_a_contribution_that_is_not_a_real_number_is_rejected(bad):
    with pytest.raises(ValueError, match="HostnameLength"):
        pick_reasons(_contributions(HostnameLength=bad), PHISHING_SIDE)


def test_a_scaled_value_that_is_not_a_real_number_is_rejected():
    scaled = {**PHISHING_SIDE, "IsDomainIP": math.nan}

    with pytest.raises(ValueError, match="IsDomainIP"):
        pick_reasons(_contributions(IsDomainIP=0.5), scaled)


# The side table matches the sentences


def test_every_shown_feature_has_a_side_and_no_hidden_one_does():
    assert set(RAISING_SIDE) == set(REASON_SENTENCES)
    assert not set(RAISING_SIDE) & set(NOT_SHOWN)


def test_sides_are_up_or_down():
    assert set(RAISING_SIDE.values()) <= {1, -1}


def test_the_side_table_cannot_be_changed():
    with pytest.raises(TypeError):
        RAISING_SIDE["HostnameLength"] = -1  # type: ignore[index]


def test_every_picked_reason_has_a_sentence():
    reasons = pick_reasons(
        _contributions(**{name: 1.0 for name in PHISHING_SIDE}),
        PHISHING_SIDE,
    )

    assert reasons
    assert all(name in REASON_SENTENCES for name in reasons)

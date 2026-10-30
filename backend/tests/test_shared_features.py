from features.hostname import FEATURE_NAMES, extract_features

# Made-up link, only ever handled as text.
# The ml suite (ml/tests/test_hostname_features.py) checks this same link against the same values,
# so the backend and the model training are shown to get identical features from one function.
# Host is login.shop.example.co.uk: 5 + 4 + 7 + 2 + 2 = 20 letters, 4 dots, 24 characters.
# The port (8443) and the query (id=7) are not part of the host, so no digits count.
SHARED_LINK = "https://login.shop.example.co.uk:8443/verify?id=7"
SHARED_EXPECTED = {
    "HostnameLength": 24,
    "IsDomainIP": 0,
    "TLDLength": 2,
    "NoOfSubDomain": 3,
    "NoOfLettersInHostname": 20,
    "LetterRatioInHostname": 20 / 24,
    "NoOfDigitsInHostname": 0,
    "DigitRatioInHostname": 0.0,
    "NoOfSpecialCharsInHostname": 4,
    "SpecialCharRatioInHostname": 4 / 24,
}


def test_backend_gets_the_same_features_as_the_ml_suite_for_the_same_link():
    assert extract_features(SHARED_LINK) == SHARED_EXPECTED


def test_backend_output_keys_are_the_feature_names_in_order():
    assert tuple(extract_features(SHARED_LINK)) == FEATURE_NAMES
    assert tuple(SHARED_EXPECTED) == FEATURE_NAMES

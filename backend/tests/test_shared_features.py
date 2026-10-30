import json
import os
import subprocess
import sys
from pathlib import Path

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


def test_backend_runtime_imports_the_extractor_outside_pytest():
    """pytest's pythonpath setting changes only the test process, so this checks that the
    backend's own environment can import the shared package, as the running app would."""
    backend_folder = Path(__file__).resolve().parents[1]
    env = {name: value for name, value in os.environ.items() if name != "PYTHONPATH"}
    code = (
        "import json\n"
        "from features.hostname import extract_features\n"
        f"print(json.dumps(extract_features({SHARED_LINK!r})))\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=backend_folder,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == SHARED_EXPECTED

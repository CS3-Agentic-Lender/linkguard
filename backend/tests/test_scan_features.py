from concurrent.futures import ThreadPoolExecutor
import warnings

from fastapi.testclient import TestClient
import pytest
from features.hostname import FEATURE_NAMES, extract_features

from app.main import app
from app.model import COLUMN_NAME_WARNING, PHISHING, phishing_score, silence_column_name_warning

# Scans sent side by side, as FastAPI's thread pool runs them.
SCANS_AT_ONCE = 20

# Made-up links on reserved names and documentation addresses, only ever handled
# as text. Each pair is the text a person pastes, then the link as the dataset
# holds it, which is what the training code passes to the extractor.
LINKS = [
    ("https://shop.example.net/basket/item?id=42&ref=mail", "https://shop.example.net/basket/item?id=42&ref=mail"),
    ("https://login.shop.example.co.uk:8443/verify?id=7", "https://login.shop.example.co.uk:8443/verify?id=7"),
    ("http://192.0.2.10/account/login", "http://192.0.2.10/account/login"),
    ("https://[2001:db8::1]/pay", "https://[2001:db8::1]/pay"),
    ("www.example.org/help", "https://www.example.org/help"),
    ("<https://paypa1-support-2024.example/verify>", "https://paypa1-support-2024.example/verify"),
    ("https://éxample.com/path", "https://éxample.com/path"),
]


@pytest.fixture
def scaled_rows(client, monkeypatch):
    """Records every row /scan hands to the scaler, while still scaling it."""
    rows = []
    scaler = client.app.state.model.scaler
    real_transform = scaler.transform

    def recording_transform(row, *args, **kwargs):
        rows.append(row)
        return real_transform(row, *args, **kwargs)

    monkeypatch.setattr(scaler, "transform", recording_transform)
    return rows


@pytest.mark.parametrize(("pasted", "training_link"), LINKS)
def test_scan_uses_the_training_features_in_the_same_order(client, scaled_rows, pasted, training_link):
    # The training code builds its feature set with this same extract_features
    # (ml/featureset/build.py), so these are the values the model was trained on.
    training_features = extract_features(training_link)

    response = client.post("/scan", json={"url": pasted})

    assert response.status_code == 200
    assert scaled_rows == [[[training_features[name] for name in FEATURE_NAMES]]]
    # The scaler was fitted on the features in this order, and start-up checks it.
    assert tuple(client.app.state.model.scaler.feature_names_in_) == FEATURE_NAMES


def test_an_ip_link_is_measured_as_an_ip_address(client, scaled_rows):
    client.post("/scan", json={"url": "http://192.0.2.10/account/login"})

    features = dict(zip(FEATURE_NAMES, scaled_rows[0][0]))
    assert features["IsDomainIP"] == 1
    assert features["TLDLength"] == 0
    assert features["NoOfSubDomain"] == 0


@pytest.mark.parametrize(("pasted", "training_link"), LINKS)
def test_scoring_a_link_never_opens_it(client, no_network, pasted, training_link):
    # no_network fails the test on any outgoing connection or name lookup.
    assert client.post("/scan", json={"url": pasted}).status_code == 200
    assert 0 <= phishing_score(client.app.state.model, training_link) <= 1


def test_score_is_the_models_phishing_probability(client):
    loaded = client.app.state.model
    link = "https://paypa1-support-2024.example/verify"
    row = [[extract_features(link)[name] for name in FEATURE_NAMES]]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        expected = loaded.model.predict_proba(loaded.scaler.transform(row))[0]

    phishing = list(loaded.model.classes_).index(PHISHING)
    assert phishing_score(loaded, link) == pytest.approx(expected[phishing])


def test_scoring_does_not_warn_about_feature_names(fixture_model_dir):
    # The app starts inside the recording block, as the running backend does: the
    # warning is silenced once at start-up, not around each scan.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with TestClient(app) as client:
            client.post("/scan", json={"url": "https://shop.example.net/basket"})

    assert [str(warning.message) for warning in caught if "feature names" in str(warning.message)] == []


def test_only_the_column_name_warning_is_silenced():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        silence_column_name_warning()
        warnings.warn(f"{COLUMN_NAME_WARNING}, but StandardScaler was fitted with feature names", UserWarning)
        warnings.warn("Some other warning", UserWarning)

    assert [str(warning.message) for warning in caught] == ["Some other warning"]


def test_scans_at_the_same_time_give_no_warning_and_the_same_scores(fixture_model_dir):
    links = [link for _, link in LINKS] * 3
    links = links[:SCANS_AT_ONCE]

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with TestClient(app) as client:

            def score(link):
                return client.post("/scan", json={"url": link}).json()["score"]

            alone = {link: score(link) for link in set(links)}
            with ThreadPoolExecutor(max_workers=SCANS_AT_ONCE) as pool:
                together = list(pool.map(score, links))

    assert len(together) == SCANS_AT_ONCE
    assert together == [alone[link] for link in links]
    assert [str(warning.message) for warning in caught if "feature names" in str(warning.message)] == []

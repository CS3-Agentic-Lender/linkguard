import pandas as pd
import pytest

from leakage.homepage import bare_homepage_rule_accuracy, is_bare_homepage, url_shape_by_class

# Made-up URLs, only ever handled as text.


@pytest.mark.parametrize(
    "url",
    [
        "https://www.example.com",
        "https://www.example.com/",
        "https://www.shop.example.co.uk",
        "HTTPS://WWW.Example.com",
    ],
)
def test_bare_homepage_matches_https_www_domain_with_optional_slash(url):
    assert is_bare_homepage(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.example.com/login",  # has a path
        "https://www.example.com/?id=1",  # has a query string
        "https://www.example.com?id=1",  # query string with no slash
        "https://www.example.com/#top",  # has a fragment
        "http://www.example.com",  # not https
        "https://example.com",  # no www.
        "https://login.example.com",  # other subdomain
        "https://www.example.com:8443",  # has a port
        "https://user@www.example.com",  # has a user part
        "https://www.",  # no domain
        "https://www.example.com//",  # more than one slash
        "",
    ],
)
def test_bare_homepage_rejects_anything_after_the_domain_or_another_shape(url):
    assert not is_bare_homepage(url)


SAMPLE = pd.DataFrame(
    {
        "URL": [
            "https://www.a.example",  # legitimate, bare homepage
            "https://www.b.example/",  # legitimate, bare homepage
            "https://www.c.example/about",  # legitimate, has a path
            "http://d.example/login.php?u=1",  # phishing, http, path and query
            "https://e.example/",  # phishing, https without www.
        ],
        "label": [0, 0, 0, 1, 1],
    }
)


def test_reports_each_url_shape_share_for_legitimate_and_phishing_separately():
    table = url_shape_by_class(SAMPLE)

    assert table.columns.tolist() == ["Legitimate (%)", "Phishing (%)"]
    assert table.index.tolist() == ["Bare homepage", "Uses https", "Uses www.", "Has a path", "Has a query string"]
    assert table.loc["Bare homepage"].tolist() == pytest.approx([200 / 3, 0])
    assert table.loc["Uses https"].tolist() == pytest.approx([100, 50])
    assert table.loc["Uses www."].tolist() == pytest.approx([100, 0])
    assert table.loc["Has a path"].tolist() == pytest.approx([100 / 3, 50])
    assert table.loc["Has a query string"].tolist() == pytest.approx([0, 50])


def test_rule_bare_homepage_means_legitimate_scores_its_accuracy():
    # Right on both bare homepages and both phishing rows, wrong on the legitimate page with a path.
    assert bare_homepage_rule_accuracy(SAMPLE) == pytest.approx(4 / 5)


def test_does_not_change_the_input():
    original = SAMPLE.copy()

    url_shape_by_class(SAMPLE)
    bare_homepage_rule_accuracy(SAMPLE)

    pd.testing.assert_frame_equal(SAMPLE, original)


def test_needs_both_classes():
    with pytest.raises(ValueError, match="both"):
        url_shape_by_class(SAMPLE[SAMPLE["label"] == 0])


def test_needs_a_label_column():
    with pytest.raises(ValueError, match="label"):
        url_shape_by_class(SAMPLE.drop(columns="label"))

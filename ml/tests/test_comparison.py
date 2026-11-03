import math

import pandas as pd
import pytest

from comparison.compare import (
    COMPARED_COLUMNS,
    UNEXPLAINED,
    find_mismatches,
    pattern_for,
    patterns_table,
    recompute_features,
    render_report,
    shapes_table,
    summary_table,
)

# Made-up links, only ever handled as text. 192.0.2.x is a range kept for examples.


def test_compares_four_features_with_the_dataset_columns():
    assert COMPARED_COLUMNS == {
        "IsDomainIP": "IsDomainIP",
        "TLDLength": "TLDLength",
        "NoOfSubDomain": "NoOfSubDomain",
        "HostnameLength": "DomainLength",
    }


def test_recompute_keeps_the_www_label():
    ours = recompute_features(pd.Series(["https://www.example.com/login"], index=[7]))

    assert ours.index.tolist() == [7]
    assert ours.columns.tolist() == list(COMPARED_COLUMNS)
    # www.example.com, not example.com: 15 characters and 1 subdomain.
    assert ours.loc[7, "HostnameLength"] == 15
    assert ours.loc[7, "NoOfSubDomain"] == 1


OURS = pd.DataFrame(
    {
        "IsDomainIP": [0, 0, 0, 0],
        "TLDLength": [3, 3, 3, 3],
        "NoOfSubDomain": [1, 1, 1, 1],
        "HostnameLength": [10, 10, 10, 10],
    }
)
DATASET = pd.DataFrame(
    {
        "IsDomainIP": [0, 0, 0, 0],
        "TLDLength": [3, 3, 3, 3],
        "NoOfSubDomain": [1, 1, 1, 1],
        # Differences of 0, 0, 2 and 6.
        "DomainLength": [10, 10, 12, 16],
    }
)


def test_summary_gives_rows_exact_share_and_typical_difference():
    table = summary_table(OURS, DATASET).set_index("Our feature")

    length = table.loc["HostnameLength"]
    assert length["Dataset column"] == "DomainLength"
    assert length["Rows compared"] == 4
    assert length["Exact match (%)"] == pytest.approx(50.0)
    assert length["Mean absolute difference"] == pytest.approx(2.0)
    assert length["Median absolute difference when different"] == pytest.approx(4.0)


def test_summary_median_is_missing_when_every_row_matches():
    table = summary_table(OURS, DATASET).set_index("Our feature")

    assert table.loc["TLDLength", "Exact match (%)"] == pytest.approx(100.0)
    assert math.isnan(table.loc["TLDLength", "Median absolute difference when different"])


def test_mismatches_list_each_differing_row_and_feature():
    found = find_mismatches(OURS, DATASET)

    assert found.to_dict("records") == [
        {"row": 2, "feature": "HostnameLength"},
        {"row": 3, "feature": "HostnameLength"},
    ]


@pytest.mark.parametrize(
    ("url", "feature", "pattern"),
    [
        ("http://192.0.2.10/login", "TLDLength", "Host is an IP address"),
        ("http://192.0.2.10/login", "NoOfSubDomain", "Host is an IP address"),
        ("http://192.0.2.10.host.example.net/", "IsDomainIP", "Host starts with an IP address"),
        ("https://shop.example.com:8443/a", "HostnameLength", "Port in the link"),
        ("https://shop.example.com:8443/a", "TLDLength", "Port in the link"),
        ("http://192.0.2.10:8080/", "HostnameLength", "Port in the link"),
        ("http://bank.example.com@example.net/", "HostnameLength", "User part in the link"),
        ("http://bank.example.com:pw@example.net/", "NoOfSubDomain", "User part in the link"),
    ],
)
def test_each_mismatch_gets_the_pattern_that_explains_it(url, feature, pattern):
    assert pattern_for(url, feature) == pattern


@pytest.mark.parametrize(
    ("url", "feature"),
    [
        ("https://shop.example.com/a", "HostnameLength"),  # no pattern fits this row
        ("http://192.0.2.10/login", "HostnameLength"),  # an IP host does not explain a length gap
        ("https://example.com/a@b:99", "HostnameLength"),  # @ and :99 sit in the path, not the host
    ],
)
def test_a_mismatch_no_pattern_explains_is_unexplained(url, feature):
    assert pattern_for(url, feature) == UNEXPLAINED


URLS = pd.Series(
    [
        "https://example.com",
        "http://192.0.2.10/",
        "http://192.0.2.20/x",
        "https://shop.example.com:8443/",
        "https://odd.example.com/",
    ]
)
MISMATCHES = pd.DataFrame(
    {
        "row": [1, 1, 2, 3, 3, 4],
        "feature": ["TLDLength", "NoOfSubDomain", "TLDLength", "HostnameLength", "TLDLength", "HostnameLength"],
    }
)


def test_patterns_table_counts_rows_and_gives_the_first_example():
    table = patterns_table(MISMATCHES, URLS).set_index("Pattern")

    ip = table.loc["Host is an IP address"]
    assert ip["Rows"] == 2
    assert ip["Features"] == "NoOfSubDomain, TLDLength"
    assert ip["Example row"] == 1
    assert ip["Example URL"] == "http://192.0.2.10/"
    assert ip["Kind"] == "Definition difference"
    assert ip["Reason"]
    assert table.loc["Port in the link", "Rows"] == 1


def test_patterns_table_always_reports_the_unexplained_bucket():
    table = patterns_table(MISMATCHES, URLS).set_index("Pattern")

    assert table.loc[UNEXPLAINED, "Rows"] == 1
    assert table.loc[UNEXPLAINED, "Example row"] == 4

    explained = patterns_table(MISMATCHES[MISMATCHES["row"] != 4], URLS).set_index("Pattern")
    assert explained.loc[UNEXPLAINED, "Rows"] == 0
    assert explained.loc[UNEXPLAINED, "Example URL"] == ""


def test_patterns_table_leaves_out_patterns_with_no_rows():
    table = patterns_table(MISMATCHES, URLS)

    assert "User part in the link" not in table["Pattern"].tolist()


def test_shapes_table_counts_rows_with_each_shape_and_how_many_differ():
    urls = pd.Series(["https://shop.example.co.uk", "https://example.co.uk:8443", "https://xn--bcher-kva.example"])
    table = shapes_table(urls, mismatching_rows={1}).set_index("Shape")

    assert table.loc["Two-part ending such as .co.uk", "Rows with this shape"] == 2
    assert table.loc["Two-part ending such as .co.uk", "Rows with a mismatch"] == 1
    assert table.loc["Non-English name (xn--)", "Rows with this shape"] == 1
    assert table.loc["Non-English name (xn--)", "Rows with a mismatch"] == 0


def test_report_shows_urls_as_code_never_as_links():
    urls = pd.Series(["https://example.com"])
    patterns = pd.DataFrame(
        [
            {"Pattern": UNEXPLAINED, "Kind": "Not known", "Features": "TLDLength", "Rows": 1,
             "Reason": "None.", "Example row": 0, "Example URL": "http://a|b.example"},
        ]
    )
    text = render_report(summary_table(OURS, DATASET), patterns, shapes_table(urls, {0}), rows=1)

    # A | inside a table cell is escaped so it does not split the cell.
    assert "`http://a\\|b.example`" in text
    assert "](http" not in text
    assert "<http" not in text


def test_report_marks_the_reasons_as_a_draft_and_says_www_removal_is_off():
    urls = pd.Series(["https://example.com"])
    no_mismatches = pd.DataFrame({"row": [], "feature": []})
    text = render_report(summary_table(OURS, DATASET), patterns_table(no_mismatches, urls), shapes_table(urls, set()), rows=1)

    assert "Draft reasons, to be confirmed by Nic" in text
    assert "www." in text
    assert "No suspected extractor bug" in text


def test_report_flags_unexplained_rows_as_a_possible_bug():
    urls = pd.Series(["https://odd.example.com/"])
    mismatches = pd.DataFrame({"row": [0], "feature": ["HostnameLength"]})
    text = render_report(summary_table(OURS, DATASET), patterns_table(mismatches, urls), shapes_table(urls, {0}), rows=1)

    assert "No suspected extractor bug" not in text
    assert "1 mismatching row has no explanation" in text


def test_report_names_a_pattern_marked_as_a_suspected_bug():
    urls = pd.Series(["https://example.com"])
    patterns = pd.DataFrame(
        [
            {"Pattern": "Made-up fault", "Kind": "Suspected extractor bug", "Features": "TLDLength", "Rows": 3,
             "Reason": "Made up for the test.", "Example row": 0, "Example URL": "https://example.com"},
            {"Pattern": UNEXPLAINED, "Kind": "Not known", "Features": "", "Rows": 0,
             "Reason": "None.", "Example row": None, "Example URL": ""},
        ]
    )
    text = render_report(summary_table(OURS, DATASET), patterns, shapes_table(urls, set()), rows=1)

    assert "Suspected extractor bug: Made-up fault." in text
    assert "No suspected extractor bug" not in text


def test_report_shows_only_the_example_host_and_hides_the_rest():
    # The path and query of a phishing link can hold a victim's email address.
    url = "http://192.0.2.10/login?user=someone@example.com"
    mismatches = pd.DataFrame({"row": [0], "feature": ["TLDLength"]})
    text = render_report(
        summary_table(OURS, DATASET), patterns_table(mismatches, pd.Series([url])), shapes_table(pd.Series([url]), {0}), rows=1
    )

    assert "`http://192.0.2.10/...`" in text
    assert "someone" not in text


def test_report_shortens_a_very_long_example_host():
    url = "http://" + "a" * 200 + ".example"
    mismatches = pd.DataFrame({"row": [0], "feature": ["HostnameLength"]})
    text = render_report(
        summary_table(OURS, DATASET), patterns_table(mismatches, pd.Series([url])), shapes_table(pd.Series([url]), {0}), rows=1
    )

    assert url not in text
    assert "`" + url[:80] + "...`" in text


def test_links_without_a_scheme_are_read_like_the_extractor_reads_them():
    assert pattern_for("shop.example.com:8443/a", "HostnameLength") == "Port in the link"

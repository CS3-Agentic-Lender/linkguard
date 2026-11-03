import math

import pandas as pd
import pytest

from features.hostname import extract_features
from comparison.compare import (
    COMPARED_COLUMNS,
    UNEXPLAINED,
    find_mismatches,
    pattern_for,
    patterns_table,
    prepare,
    recompute_features,
    render_report,
    shapes_table,
    skipped_table,
    summary_table,
)
from features.hostname import EMPTY_LINK_MESSAGE, NO_HOST_MESSAGE

# Made-up links, only ever handled as text. 192.0.2.x is a range kept for examples.


def test_compares_four_features_with_the_dataset_columns():
    assert COMPARED_COLUMNS == {
        "IsDomainIP": "IsDomainIP",
        "TLDLength": "TLDLength",
        "NoOfSubDomain": "NoOfSubDomain",
        "HostnameLength": "DomainLength",
    }


def test_recompute_keeps_the_www_label():
    ours, refused = recompute_features(pd.Series(["https://www.example.com/login"], index=[7]))

    assert ours.index.tolist() == [7]
    assert ours.columns.tolist() == list(COMPARED_COLUMNS)
    # www.example.com, not example.com: 15 characters and 1 subdomain.
    assert ours.loc[7, "HostnameLength"] == 15
    assert ours.loc[7, "NoOfSubDomain"] == 1
    assert refused == {}


def test_recompute_skips_a_link_the_extractor_refuses_and_gives_the_reason():
    ours, refused = recompute_features(pd.Series(["https://example.com", "http://", " "], index=[3, 4, 5]))

    assert ours.index.tolist() == [3]
    assert refused == {
        4: f"Our extractor refused the link: {NO_HOST_MESSAGE}",
        5: f"Our extractor refused the link: {EMPTY_LINK_MESSAGE}",
    }


RAW = pd.DataFrame(
    {
        "URL": ["https://example.com", "http://", "https://example.org", "https://example.net"],
        "Domain": ["example.com", "", "example.org", "example.net"],
        "IsDomainIP": ["0", "0", "0", "0"],
        "TLDLength": ["3", "0", "3", "three"],
        "NoOfSubDomain": ["0", "0", "0", "0"],
        "DomainLength": ["11", "0", " ", "11"],
    }
)


def test_prepare_leaves_out_rows_that_cannot_be_compared_and_says_why():
    comparison = prepare(RAW)

    assert comparison.skipped.to_dict("records") == [
        {"row": 1, "reason": f"Our extractor refused the link: {NO_HOST_MESSAGE}"},
        {"row": 2, "reason": "The dataset's DomainLength is blank."},
        {"row": 3, "reason": "The dataset's TLDLength is not a number."},
    ]
    assert comparison.ours.index.tolist() == [0]
    assert comparison.dataset.index.tolist() == [0]
    # The dataset's values are numbers again, so they can be subtracted.
    assert comparison.dataset.loc[0, "DomainLength"] == 11


def test_rows_that_cannot_be_compared_are_left_out_of_the_match_rate():
    comparison = prepare(RAW)
    table = summary_table(comparison.ours, comparison.dataset).set_index("Our feature")

    assert table.loc["HostnameLength", "Rows compared"] == 1
    assert table.loc["HostnameLength", "Exact match (%)"] == pytest.approx(100.0)


def test_skipped_table_counts_each_reason_with_an_example_row():
    table = skipped_table(prepare(RAW).skipped)

    assert table.to_dict("records") == [
        {"Reason": f"Our extractor refused the link: {NO_HOST_MESSAGE}", "Rows": 1, "Example row": 1},
        {"Reason": "The dataset's DomainLength is blank.", "Rows": 1, "Example row": 2},
        {"Reason": "The dataset's TLDLength is not a number.", "Rows": 1, "Example row": 3},
    ]


def test_report_gives_the_count_and_an_example_of_rows_that_cannot_be_compared():
    comparison = prepare(RAW)
    mismatches = find_mismatches(comparison.ours, comparison.dataset)
    text = render_report(
        summary_table(comparison.ours, comparison.dataset),
        patterns_table(mismatches, comparison.ours, comparison.dataset),
        shapes_table(comparison.dataset["Domain"], set()),
        skipped_table(comparison.skipped),
        rows=len(RAW),
    )

    assert "3 rows could not be compared" in text
    assert "| The dataset's TLDLength is not a number. | 1 | 3 |" in text


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


def _ours(domain):
    """Our features for a link with this domain, read by the extractor."""
    return extract_features("http://" + domain + "/", strip_www=False)


# Each case gives the dataset's value, worked out from the dataset's own definitions:
# DomainLength is the length of the whole domain, TLDLength the length of the text
# after its last dot, and NoOfSubDomain its number of dots minus 1.
@pytest.mark.parametrize(
    ("domain", "feature", "dataset_value", "pattern"),
    [
        ("192.0.2.10", "TLDLength", 2, "Host is an IP address"),
        ("192.0.2.10", "NoOfSubDomain", 2, "Host is an IP address"),
        ("192.0.2.10.host.example.net", "IsDomainIP", 1, "Host starts with an IP address"),
        ("shop.example.com:8443", "HostnameLength", 21, "Port in the link"),
        ("shop.example.com:8443", "TLDLength", 8, "Port in the link"),
        ("192.0.2.10:8080", "HostnameLength", 15, "Port in the link"),
        # The dataset's TLD is 10:8080. The IP pattern predicts 2, so the port pattern explains it.
        ("192.0.2.10:8080", "TLDLength", 7, "Port in the link"),
        ("bank.example.com@example.net", "HostnameLength", 28, "User part in the link"),
        ("bank.example.com:pw@example.net", "NoOfSubDomain", 2, "User part in the link"),
        # Both a user part and a port: the dataset keeps both.
        ("u.v@shop.example.com:8443", "HostnameLength", 25, "User part in the link"),
    ],
)
def test_each_mismatch_gets_the_pattern_that_explains_it(domain, feature, dataset_value, pattern):
    assert pattern_for(domain, _ours(domain), feature, dataset_value) == pattern


@pytest.mark.parametrize(
    ("domain", "feature", "dataset_value"),
    [
        ("shop.example.com", "HostnameLength", 20),  # no pattern fits this row
        ("192.0.2.10", "HostnameLength", 12),  # an IP host does not explain a length gap
        ("bank.example.com:pw@example.net", "TLDLength", 5),  # the user part sits before the TLD
    ],
)
def test_a_mismatch_no_pattern_explains_is_unexplained(domain, feature, dataset_value):
    assert pattern_for(domain, _ours(domain), feature, dataset_value) == UNEXPLAINED


@pytest.mark.parametrize(
    ("domain", "feature", "dataset_value"),
    [
        ("192.0.2.10", "TLDLength", 3),  # the last number, 10, is 2 characters
        ("192.0.2.10", "NoOfSubDomain", 3),
        ("shop.example.com:8443", "HostnameLength", 22),  # 21 with the port
        ("shop.example.com:8443", "TLDLength", 9),  # com:8443 is 8
        ("bank.example.com@example.net", "HostnameLength", 30),  # 28 with the user part
        ("bank.example.com:pw@example.net", "NoOfSubDomain", 5),  # 2 with the user part
    ],
)
def test_the_right_shape_with_the_wrong_difference_is_unexplained(domain, feature, dataset_value):
    # The row has the pattern's shape, but the pattern does not account for this number.
    assert pattern_for(domain, _ours(domain), feature, dataset_value) == UNEXPLAINED


def test_the_shape_is_read_from_the_dataset_domain_not_the_url():
    # The extractor reads this link as an IP host, but the shape comes from the domain.
    ours = extract_features("http://192.0.2.10/", strip_www=False)

    assert pattern_for("example.com:8080", ours, "HostnameLength", 15) == "Port in the link"


DATASET_ROWS = pd.DataFrame(
    {
        "URL": [
            "https://example.com",
            "http://192.0.2.10/",
            "http://192.0.2.20/x",
            "https://shop.example.com:8443/",
            "https://odd.example.com/",
        ],
        "Domain": ["example.com", "192.0.2.10", "192.0.2.20", "shop.example.com:8443", "odd.example.com"],
        "IsDomainIP": [0, 1, 1, 0, 0],
        "TLDLength": [3, 2, 2, 8, 3],
        "NoOfSubDomain": [0, 2, 2, 1, 1],
        # odd.example.com is 15 characters. 99 is a difference no pattern explains.
        "DomainLength": [11, 10, 10, 21, 99],
    }
)
MISMATCHES = pd.DataFrame(
    {
        "row": [1, 1, 2, 2, 3, 3, 4],
        "feature": ["NoOfSubDomain", "TLDLength", "NoOfSubDomain", "TLDLength", "HostnameLength", "TLDLength", "HostnameLength"],
    }
)


def _rows_ours():
    return recompute_features(DATASET_ROWS["URL"])[0]


def test_the_example_rows_mismatch_where_expected():
    assert find_mismatches(_rows_ours(), DATASET_ROWS).to_dict("records") == MISMATCHES.to_dict("records")


def test_patterns_table_counts_rows_and_gives_the_first_example():
    table = patterns_table(MISMATCHES, _rows_ours(), DATASET_ROWS).set_index("Pattern")

    ip = table.loc["Host is an IP address"]
    assert ip["Rows"] == 2
    assert ip["Features"] == "NoOfSubDomain, TLDLength"
    assert ip["Example row"] == 1
    assert ip["Example URL"] == "http://192.0.2.10/..."
    assert ip["Kind"] == "Definition difference"
    assert ip["Reason"]
    assert table.loc["Port in the link", "Rows"] == 1


def test_patterns_table_always_reports_the_unexplained_bucket():
    table = patterns_table(MISMATCHES, _rows_ours(), DATASET_ROWS).set_index("Pattern")

    assert table.loc[UNEXPLAINED, "Rows"] == 1
    assert table.loc[UNEXPLAINED, "Example row"] == 4

    explained = patterns_table(MISMATCHES[MISMATCHES["row"] != 4], _rows_ours(), DATASET_ROWS).set_index("Pattern")
    assert explained.loc[UNEXPLAINED, "Rows"] == 0
    assert explained.loc[UNEXPLAINED, "Example URL"] == ""


def test_patterns_table_leaves_out_patterns_with_no_rows():
    table = patterns_table(MISMATCHES, _rows_ours(), DATASET_ROWS)

    assert "User part in the link" not in table["Pattern"].tolist()


def test_patterns_table_counts_a_wrong_difference_as_unexplained():
    # The port explains TLDLength (com:8443 is 8) but not a DomainLength of 30.
    ours, dataset = _one_row("https://shop.example.com:8443/", "shop.example.com:8443", DomainLength=30, TLDLength=8)
    table = patterns_table(find_mismatches(ours, dataset), ours, dataset).set_index("Pattern")

    assert table.loc["Port in the link", "Features"] == "TLDLength"
    assert table.loc[UNEXPLAINED, "Features"] == "HostnameLength"
    assert table.loc[UNEXPLAINED, "Rows"] == 1


def test_shapes_table_counts_rows_with_each_shape_and_how_many_differ():
    domains = pd.Series(["shop.example.co.uk", "example.co.uk:8443", "xn--bcher-kva.example"])
    table = shapes_table(domains, mismatching_rows={1}).set_index("Shape")

    assert table.loc["Two-part ending such as .co.uk", "Rows with this shape"] == 2
    assert table.loc["Two-part ending such as .co.uk", "Rows with a mismatch"] == 1
    assert table.loc["Non-English name (xn--)", "Rows with this shape"] == 1
    assert table.loc["Non-English name (xn--)", "Rows with a mismatch"] == 0


NOTHING_SKIPPED = skipped_table(pd.DataFrame({"row": [], "reason": []}))


def _one_row(url, domain, **dataset_values):
    """Our features for url, and a one-row dataset equal to them except the columns given."""
    ours, _ = recompute_features(pd.Series([url]))
    values = {column: [ours.loc[0, feature]] for feature, column in COMPARED_COLUMNS.items()}
    values.update({column: [value] for column, value in dataset_values.items()})
    return ours, pd.DataFrame({"URL": [url], "Domain": [domain], **values})


def _report(url, domain, **dataset_values):
    """The report for one row, run through the same steps as main()."""
    ours, dataset = _one_row(url, domain, **dataset_values)
    mismatches = find_mismatches(ours, dataset)
    return render_report(
        summary_table(ours, dataset),
        patterns_table(mismatches, ours, dataset),
        shapes_table(dataset["Domain"], set(mismatches["row"])),
        NOTHING_SKIPPED,
        rows=1,
    )


def _patterns(example_url):
    return pd.DataFrame(
        [
            {"Pattern": UNEXPLAINED, "Kind": "Not known", "Features": "TLDLength", "Rows": 1,
             "Reason": "None.", "Example row": 0, "Example URL": example_url},
        ]
    )


def test_report_shows_urls_as_code_never_as_links():
    text = render_report(summary_table(OURS, DATASET), _patterns("http://a|b.example"), shapes_table(pd.Series(["a"]), {0}), NOTHING_SKIPPED, rows=1)

    # A | inside a table cell is escaped so it does not split the cell.
    assert "`http://a\\|b.example`" in text
    assert "](http" not in text
    assert "<http" not in text


def test_report_has_no_draft_marker_and_says_www_removal_is_off():
    text = _report("https://example.com", "example.com")

    assert "Draft reasons" not in text
    assert "Every row could be compared." in text
    assert "www." in text
    assert "No suspected extractor bug" in text


def test_report_flags_unexplained_rows_as_a_possible_bug():
    text = _report("https://odd.example.com/", "odd.example.com", DomainLength=99)

    assert "No suspected extractor bug" not in text
    assert "1 mismatching row has no explanation" in text


def test_report_names_a_pattern_marked_as_a_suspected_bug():
    patterns = pd.DataFrame(
        [
            {"Pattern": "Made-up fault", "Kind": "Suspected extractor bug", "Features": "TLDLength", "Rows": 3,
             "Reason": "Made up for the test.", "Example row": 0, "Example URL": "https://example.com"},
            {"Pattern": UNEXPLAINED, "Kind": "Not known", "Features": "", "Rows": 0,
             "Reason": "None.", "Example row": None, "Example URL": ""},
        ]
    )
    text = render_report(summary_table(OURS, DATASET), patterns, shapes_table(pd.Series(["a"]), set()), NOTHING_SKIPPED, rows=1)

    assert "Suspected extractor bug: Made-up fault." in text
    assert "No suspected extractor bug" not in text


def test_report_shows_only_the_example_host_and_hides_the_rest():
    # The path and query of a phishing link can hold a victim's email address.
    text = _report("http://192.0.2.10/login?user=someone@example.com", "192.0.2.10", TLDLength=2)

    assert "`http://192.0.2.10/...`" in text
    assert "someone" not in text


def test_report_shortens_a_very_long_example_host():
    # Four labels of 60 letters: the extractor allows up to 63 per label.
    url = "http://" + ".".join(["a" * 60] * 4) + ".example"
    text = _report(url, url.removeprefix("http://"), DomainLength=999)

    assert url not in text
    assert "`" + url[:80] + "...`" in text


@pytest.mark.parametrize(
    ("example_url", "shown"),
    [
        ("http://a`b.example", "``http://a`b.example``"),
        # The fence is one backtick longer than the longest run inside the text.
        ("http://a``b.example", "```http://a``b.example```"),
        ("http://a`b``c```d.example", "````http://a`b``c```d.example````"),
        # A backtick at the edge gets a space, so it is not read as part of the fence.
        ("`http://a.example", "`` `http://a.example ``"),
    ],
)
def test_report_fences_backticks_in_a_url_so_the_code_span_holds(example_url, shown):
    text = render_report(summary_table(OURS, DATASET), _patterns(example_url), shapes_table(pd.Series(["a"]), {0}), NOTHING_SKIPPED, rows=1)

    assert f"| {shown} |" in text


def test_report_hides_the_user_part_of_an_example_link():
    # A user:password@ part can look like a real login, so it is never written out.
    url = "http://www.example.com:911@host.example.net/login"
    domain = "www.example.com:911@host.example.net"
    text = _report(url, domain, DomainLength=len(domain))

    assert "`http://<user part hidden>@host.example.net/...`" in text
    assert "www.example.com:911" not in text


def test_example_link_stops_after_the_dataset_domain():
    # The @ and :99 are in the path, after the dataset's domain, so nothing is hidden.
    ours, dataset = _one_row("https://example.com/a@b:99", "example.com", DomainLength=20)
    table = patterns_table(find_mismatches(ours, dataset), ours, dataset).set_index("Pattern")

    assert table.loc[UNEXPLAINED, "Example URL"] == "https://example.com/..."


def test_example_link_falls_back_to_the_domain_when_the_url_does_not_hold_it():
    ours, dataset = _one_row("https://Example.com/a", "u:pw@example.com", DomainLength=20)
    table = patterns_table(find_mismatches(ours, dataset), ours, dataset).set_index("Pattern")

    assert table.loc[UNEXPLAINED, "Example URL"] == "<user part hidden>@example.com..."

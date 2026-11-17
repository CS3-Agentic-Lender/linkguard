"""Tests for the link normaliser used to compare outside links with PhiUSIIL.

The outside-test story compares links after removing the scheme, a leading www. and a
trailing slash, so small differences in how a link is written do not hide a match.
"""

import pytest

from outside.normalise import normalise


@pytest.mark.parametrize(
    ("link", "expected"),
    [
        ("https://www.bbc.com/news/", "bbc.com/news"),
        ("http://bbc.com/news", "bbc.com/news"),
        ("bbc.com/news/", "bbc.com/news"),
        ("HTTPS://WWW.bbc.com/news", "bbc.com/news"),
        ("https://www.bbc.com", "bbc.com"),
        ("https://www.bbc.com/", "bbc.com"),
    ],
)
def test_removes_scheme_leading_www_and_trailing_slash(link, expected):
    assert normalise(link) == expected


def test_keeps_the_path_and_query_string():
    assert normalise("https://shop.ie/item/5?colour=red&size=m") == "shop.ie/item/5?colour=red&size=m"


def test_only_a_leading_www_is_removed():
    assert normalise("https://news.www.example.com/a") == "news.www.example.com/a"
    assert normalise("https://wwwexample.com/a") == "wwwexample.com/a"


def test_two_ways_of_writing_one_link_match():
    assert normalise("https://www.bbc.com/news/") == normalise("http://bbc.com/news")

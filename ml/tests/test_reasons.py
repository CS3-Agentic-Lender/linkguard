"""The plain reason sentences for each feature, and the table in docs/ that lists them."""

import re
from pathlib import Path

import pytest

from features.hostname import FEATURE_NAMES
from features.reasons import NOT_SHOWN, REASON_SENTENCES, reason_for
from ranking.final_list import DROPPED, FINAL_FEATURES

REASONS_TABLE = Path(__file__).resolve().parents[2] / "docs" / "reason-sentences.md"

# Features the final feature list marks to watch, because part of their strength
# comes from the dataset's legitimate links being big sites' front pages.
WATCH_FEATURES = ("TLDLength", "NoOfSubDomain")

# Words a user should never see in a reason (ALG-33 criterion 3), plus two more
# that are jargon to most people.
TECHNICAL_WORDS = ("feature", "shap", "probability", "model", "hostname", "ratio")

TABLE_ROW = re.compile(r"^\| `(?P<name>\w+)` \| (?P<text>.+?) \|$")


def _table_rows(heading: str) -> dict[str, str]:
    """The `name` -> text rows of the table under one ## heading in the docs table."""
    section = REASONS_TABLE.read_text(encoding="utf-8").split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]
    return {match["name"]: match["text"] for line in section.splitlines() if (match := TABLE_ROW.match(line))}


# Every feature has exactly one entry


def test_every_extractor_feature_is_either_shown_or_not_shown():
    assert set(REASON_SENTENCES) | set(NOT_SHOWN) == set(FEATURE_NAMES)


def test_no_feature_is_both_shown_and_not_shown():
    assert not set(REASON_SENTENCES) & set(NOT_SHOWN)


def test_every_model_feature_has_an_entry():
    for name in FINAL_FEATURES:
        assert name in REASON_SENTENCES or name in NOT_SHOWN, name


def test_features_the_model_does_not_use_are_not_shown():
    for name in DROPPED:
        assert name in NOT_SHOWN
        assert "does not use" in NOT_SHOWN[name]


# Template bias


@pytest.mark.parametrize("name", WATCH_FEATURES)
def test_watch_features_are_not_shown_and_point_to_the_final_feature_list(name):
    assert name in NOT_SHOWN
    assert "ml/reports/final_feature_list.md" in NOT_SHOWN[name]


# Plain words


@pytest.mark.parametrize("name", sorted(REASON_SENTENCES))
def test_sentence_has_no_technical_words_or_column_names(name):
    sentence = REASON_SENTENCES[name].lower()
    for word in TECHNICAL_WORDS:
        assert word not in sentence, f"{name}: {word!r}"
    for column in FEATURE_NAMES:
        assert column.lower() not in sentence, f"{name}: {column}"


@pytest.mark.parametrize("name", sorted(REASON_SENTENCES))
def test_sentence_is_one_short_sentence(name):
    sentence = REASON_SENTENCES[name]
    assert sentence[0].isupper()
    assert sentence.endswith(".")
    assert sentence.count(".") == 1
    assert len(sentence.split()) <= 12


def test_no_two_features_share_a_sentence():
    assert len(set(REASON_SENTENCES.values())) == len(REASON_SENTENCES)


# Looking one up


def test_reason_for_gives_the_sentence_of_a_shown_feature():
    name = next(iter(REASON_SENTENCES))
    assert reason_for(name) == REASON_SENTENCES[name]


@pytest.mark.parametrize("name", WATCH_FEATURES)
def test_reason_for_gives_nothing_for_a_feature_that_is_not_shown(name):
    assert reason_for(name) is None


def test_reason_for_an_unknown_feature_stops_with_its_name():
    with pytest.raises(KeyError, match="NotAFeature"):
        reason_for("NotAFeature")


def test_the_sentences_cannot_be_changed_at_run_time():
    with pytest.raises(TypeError):
        REASON_SENTENCES["HostnameLength"] = "Changed."  # type: ignore[index]


# The docs table matches the code word for word


def test_docs_table_lists_every_shown_sentence_word_for_word():
    assert _table_rows("Shown to users") == dict(REASON_SENTENCES)


def test_docs_table_lists_every_feature_that_is_not_shown_with_its_reason():
    assert _table_rows("Never shown") == dict(NOT_SHOWN)

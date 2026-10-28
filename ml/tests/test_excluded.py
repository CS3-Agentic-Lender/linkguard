from leakage.excluded import EXCLUDED_FEATURES, PAGE_CONTENT_COLUMNS, model_feature_columns

SPEC_LEAKY = ["URLSimilarityIndex", "TLDLegitimateProb", "URLCharProb"]
SPEC_IDENTIFIERS = ["FILENAME", "URL", "Domain", "TLD", "Title"]


def test_covers_every_column_the_spec_lists():
    for column in [*SPEC_LEAKY, *SPEC_IDENTIFIERS, *PAGE_CONTENT_COLUMNS]:
        assert column in EXCLUDED_FEATURES


def test_lists_all_28_page_content_columns():
    assert len(PAGE_CONTENT_COLUMNS) == 28
    assert len(set(PAGE_CONTENT_COLUMNS)) == 28
    assert "Title" not in PAGE_CONTENT_COLUMNS


def test_every_exclusion_has_a_one_line_reason():
    for column, reason in EXCLUDED_FEATURES.items():
        assert reason.strip(), column
        assert "\n" not in reason, column


def test_model_features_drop_excluded_columns_and_the_label():
    columns = ["URL", "URLLength", "URLSimilarityIndex", "IsHTTPS", "NoOfImage", "label"]

    assert model_feature_columns(columns) == ["URLLength", "IsHTTPS"]

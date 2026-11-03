import json

import numpy as np
import pandas as pd
import pytest

from splitting.split import (
    SPLIT_SEED,
    TEST_SET,
    TRAIN_SET,
    SplitMismatchError,
    empty_sets,
    hosts_in_both,
    load_split,
    phishing_share_gap,
    plain_host,
    save_split,
    split_by_host,
)


def make_rows(host_count: int, seed: int = 0) -> tuple[pd.Series, pd.Series]:
    """Made-up labels and hosts: each host has 1 to 4 rows and one label, about 40% phishing."""
    generator = np.random.default_rng(seed)
    hosts, labels = [], []
    for number in range(host_count):
        label = int(generator.random() < 0.4)
        for _ in range(generator.integers(1, 5)):
            hosts.append(f"host{number}.example")
            labels.append(label)
    # A gap in the index, like the cleaned data after duplicates are removed.
    index = pd.Index(range(0, 3 * len(hosts), 3))
    return pd.Series(labels, index=index, name="label"), pd.Series(hosts, index=index, name="host")


def test_every_row_goes_into_exactly_one_set():
    labels, hosts = make_rows(300)

    split = split_by_host(labels, hosts)

    assert set(split.index) == set(labels.index)
    assert set(split.unique()) == {TRAIN_SET, TEST_SET}


def test_about_one_fifth_of_rows_go_to_the_test_set():
    labels, hosts = make_rows(1000)

    split = split_by_host(labels, hosts)

    test_share = (split == TEST_SET).mean()
    assert 0.17 < test_share < 0.23


def test_no_host_is_in_both_sets():
    labels, hosts = make_rows(300)

    split = split_by_host(labels, hosts)

    assert hosts_in_both(hosts, split) == set()


def test_hosts_in_both_finds_a_shared_host():
    hosts = pd.Series(["a.example", "a.example", "b.example"])
    split = pd.Series([TRAIN_SET, TEST_SET, TRAIN_SET])

    assert hosts_in_both(hosts, split) == {"a.example"}


def test_rerunning_gives_exactly_the_same_rows_in_each_set():
    labels, hosts = make_rows(300)

    first = split_by_host(labels, hosts)
    second = split_by_host(labels, hosts)

    pd.testing.assert_series_equal(first, second)


def test_a_different_seed_gives_a_different_split():
    labels, hosts = make_rows(300)

    default = split_by_host(labels, hosts, seed=SPLIT_SEED)
    other = split_by_host(labels, hosts, seed=SPLIT_SEED + 1)

    assert not default.equals(other)


def test_each_set_keeps_the_phishing_share_of_the_whole_data():
    labels, hosts = make_rows(4000)

    split = split_by_host(labels, hosts)

    assert phishing_share_gap(labels, split) <= 0.5


def test_phishing_share_gap_is_the_largest_gap_in_percentage_points():
    # Whole data 50% phishing, training 2 of 3 = 66.7%, test 0 of 1 = 0%.
    labels = pd.Series([1, 1, 0, 0])
    split = pd.Series([TRAIN_SET, TRAIN_SET, TRAIN_SET, TEST_SET])

    assert phishing_share_gap(labels, split) == pytest.approx(50.0)


def test_rejects_labels_and_hosts_with_different_rows():
    labels, hosts = make_rows(10)

    with pytest.raises(ValueError, match="same rows"):
        split_by_host(labels, hosts.iloc[1:])


def test_rejects_a_missing_host():
    labels, hosts = make_rows(10)
    hosts.iloc[0] = None

    with pytest.raises(ValueError, match="host"):
        split_by_host(labels, hosts)


def saved_split(tmp_path, host_count: int = 50):
    labels, hosts = make_rows(host_count)
    split = split_by_host(labels, hosts)
    return split, hosts, save_split(split, hosts, tmp_path / "data" / "split.csv")


def test_saved_split_reads_back_unchanged(tmp_path):
    split, hosts, path = saved_split(tmp_path)

    loaded = load_split(path, hosts)

    pd.testing.assert_series_equal(loaded, split)


def test_split_file_keeps_only_the_row_and_set_columns(tmp_path):
    # The training pipeline reads split.csv directly and expects exactly these columns.
    _, _, path = saved_split(tmp_path)

    assert pd.read_csv(path).columns.tolist() == ["row", "set"]


def test_load_split_rejects_reordered_cleaned_data(tmp_path):
    _, hosts, path = saved_split(tmp_path)
    reordered = pd.Series(hosts.to_numpy()[::-1], index=hosts.index)

    with pytest.raises(SplitMismatchError, match="different cleaned data"):
        load_split(path, reordered)


def test_load_split_rejects_cleaned_data_with_a_different_row_count(tmp_path):
    _, hosts, path = saved_split(tmp_path)

    with pytest.raises(SplitMismatchError, match="rows"):
        load_split(path, hosts.iloc[:-1])


def test_load_split_rejects_a_check_file_with_a_different_row_count(tmp_path):
    _, hosts, path = saved_split(tmp_path)
    check_path = path.with_name("split_check.json")
    check = json.loads(check_path.read_text())
    check_path.write_text(json.dumps({**check, "rows": check["rows"] + 1}))

    with pytest.raises(SplitMismatchError, match="cleaned rows, but there are"):
        load_split(path, hosts)


def test_load_split_rejects_a_row_listed_twice(tmp_path):
    _, hosts, path = saved_split(tmp_path)
    table = pd.read_csv(path)
    first = table.iloc[[0]].assign(set=TEST_SET if table["set"].iloc[0] == TRAIN_SET else TRAIN_SET)
    pd.concat([table, first]).to_csv(path, index=False)

    with pytest.raises(SplitMismatchError, match="exactly one set"):
        load_split(path, hosts)


def test_load_split_rejects_a_missing_row(tmp_path):
    _, hosts, path = saved_split(tmp_path)
    pd.read_csv(path).iloc[1:].to_csv(path, index=False)

    with pytest.raises(SplitMismatchError, match="exactly one set"):
        load_split(path, hosts)


def test_load_split_rejects_an_unknown_set_name(tmp_path):
    _, hosts, path = saved_split(tmp_path)
    pd.read_csv(path).assign(set="validation").to_csv(path, index=False)

    with pytest.raises(SplitMismatchError, match="validation"):
        load_split(path, hosts)


def test_load_split_rejects_a_split_without_its_check_file(tmp_path):
    _, hosts, path = saved_split(tmp_path)
    for check_file in path.parent.glob("*.json"):
        check_file.unlink()

    with pytest.raises(SplitMismatchError, match="splitting.build"):
        load_split(path, hosts)


@pytest.mark.parametrize(
    ("link", "host"),
    [
        ("https://www.Shop.example.com/login?x=1", "www.shop.example.com"),
        ("http://a.example:8080/page", "a.example"),
        ("//cdn.example/file", "cdn.example"),
        ("a.example/path", "a.example"),
    ],
)
def test_plain_host_reads_the_host_with_the_standard_library(link, host):
    assert plain_host(link) == host


def test_plain_host_rejects_a_link_without_a_host():
    with pytest.raises(ValueError, match="host"):
        plain_host("https://")


def test_empty_sets_names_a_set_with_no_rows():
    split = pd.Series([TRAIN_SET, TRAIN_SET])

    assert empty_sets(split) == [TEST_SET]
    assert empty_sets(pd.Series([TRAIN_SET, TEST_SET])) == []

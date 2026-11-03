import numpy as np
import pandas as pd
import pytest

from splitting.split import (
    SPLIT_SEED,
    TEST_SET,
    TRAIN_SET,
    hosts_in_both,
    load_split,
    phishing_share_gap,
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


def test_saved_split_reads_back_unchanged(tmp_path):
    labels, hosts = make_rows(50)
    split = split_by_host(labels, hosts)

    path = save_split(split, tmp_path / "data" / "split.csv")
    loaded = load_split(path)

    pd.testing.assert_series_equal(loaded, split)

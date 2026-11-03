import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cleaning.storage import CLEANED_CSV_NAME, save_cleaned
from features.hostname import FEATURE_NAMES
from splitting.build import (
    MAX_SHARE_GAP_POINTS,
    SCALING_CHART_NAME,
    build_split,
    check_run,
    cleaned_host,
    main,
    save_outputs,
)
from splitting.scaling import load_scaler
from splitting.split import TEST_SET, TRAIN_SET, load_split

REPO_ROOT = Path(__file__).resolve().parents[2]


def make_rows(host_count: int = 200) -> pd.DataFrame:
    """Made-up cleaned rows: 1 to 3 fake links per host, one label per host."""
    generator = np.random.default_rng(1)
    urls, labels = [], []
    for number in range(host_count):
        label = int(generator.random() < 0.4)
        name = f"shop{number}-{'x' * (number % 7)}.example{number % 3}.com"
        for page in range(generator.integers(1, 4)):
            prefix = "https://www." if page == 0 else "http://"
            urls.append(f"{prefix}{name}/page{page}")
            labels.append(label)
    return pd.DataFrame({"URL": urls, "label": labels}, index=range(5, 5 + 2 * len(urls), 2))


def test_cleaned_host_drops_the_scheme_path_and_www():
    assert cleaned_host("https://www.Shop.example.com/login?x=1") == "shop.example.com"


def test_links_on_one_host_share_a_cleaned_host_with_or_without_www():
    assert cleaned_host("https://www.a.example") == cleaned_host("http://a.example/page")


def test_build_keeps_every_row_and_the_ten_features_in_order():
    rows = make_rows()

    run = build_split(rows)

    assert run.split.index.equals(rows.index)
    assert run.train_features.columns.tolist() == list(FEATURE_NAMES)
    assert run.scaled_train.columns.tolist() == list(FEATURE_NAMES)


def test_build_puts_no_host_in_both_sets():
    run = build_split(make_rows())

    assert run.shared_hosts == set()


def test_build_puts_no_url_in_both_sets():
    run = build_split(make_rows())

    assert run.shared_urls == set()


def test_leak_check_finds_shared_hosts_when_the_grouping_is_wrong(monkeypatch):
    # Group by the full link instead of the host: links on one host can then land in
    # both sets. The check reads hosts from the links itself, so it must catch this.
    monkeypatch.setattr("splitting.build.cleaned_host", lambda link: link)

    run = build_split(make_rows(2000))

    assert run.shared_hosts
    assert any("both" in problem for problem in check_run(run))


def test_build_reports_the_phishing_share_gap():
    run = build_split(make_rows(2000))

    assert 0 <= run.share_gap_points <= MAX_SHARE_GAP_POINTS


def test_scaler_learns_from_training_rows_only():
    rows = make_rows()

    run = build_split(rows)

    train_index = run.split.index[run.split == TRAIN_SET]
    assert run.train_features.index.equals(train_index)
    np.testing.assert_allclose(run.scaler.mean_, run.train_features.mean().to_numpy())


def test_build_rejects_a_link_without_a_host():
    rows = make_rows(20)
    rows.loc[rows.index[0], "URL"] = "https://"

    with pytest.raises(ValueError, match="row"):
        build_split(rows)


def test_saved_outputs_read_back_unchanged(tmp_path):
    run = build_split(make_rows())

    paths = save_outputs(run, data_dir=tmp_path / "data", models_dir=tmp_path / "models", reports_dir=tmp_path / "reports")

    pd.testing.assert_series_equal(load_split(paths.split, run.hosts), run.split)
    reloaded = load_scaler(paths.scaler)
    np.testing.assert_array_equal(reloaded.mean_, run.scaler.mean_)
    assert paths.chart.name == SCALING_CHART_NAME
    assert paths.chart.read_bytes().startswith(b"\x89PNG")
    assert set(run.split.unique()) == {TRAIN_SET, TEST_SET}


@pytest.mark.parametrize("path", ["ml/data/split.csv", "ml/models/scaler.joblib"])
def test_saved_split_and_scaler_are_ignored_by_git(path):
    result = subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO_ROOT, check=False)

    assert result.returncode == 0, f"{path} would be picked up for commit"


def test_check_run_names_each_failed_check():
    run = build_split(make_rows())
    bad = type(run)(
        **{**run.__dict__, "shared_hosts": {"a.example"}, "shared_urls": {"https://a.example"}, "share_gap_points": 0.9}
    )

    problems = check_run(bad)

    assert len(problems) == 3
    assert "hosts are in both" in problems[0]
    assert "links are in both" in problems[1]
    assert "0.900" in problems[2]


def test_check_run_stops_on_an_empty_set():
    run = build_split(make_rows())
    everything_in_training = pd.Series(TRAIN_SET, index=run.split.index)
    bad = type(run)(**{**run.__dict__, "split": everything_in_training, "share_gap_points": float("nan")})

    problems = check_run(bad)

    assert any("test set is empty" in problem for problem in problems)


def test_main_saves_everything_from_the_cleaned_file(tmp_path, capsys):
    save_cleaned(make_rows(2000), tmp_path / "data" / CLEANED_CSV_NAME)

    assert main(tmp_path) == 0

    assert (tmp_path / "data" / "split.csv").exists()
    assert (tmp_path / "data" / "split_check.json").exists()
    assert (tmp_path / "models" / "scaler.joblib").exists()
    assert (tmp_path / "reports" / SCALING_CHART_NAME).exists()
    assert "Hosts in both sets: 0" in capsys.readouterr().out


def test_main_stops_without_the_cleaned_file(tmp_path, capsys):
    assert main(tmp_path) == 1

    assert "03_clean_dataset" in capsys.readouterr().out
    assert not (tmp_path / "models").exists()


def test_main_saves_nothing_when_a_check_fails(tmp_path, monkeypatch, capsys):
    save_cleaned(make_rows(), tmp_path / "data" / CLEANED_CSV_NAME)
    monkeypatch.setattr("splitting.build.check_run", lambda run: ["made-up failure"])

    assert main(tmp_path) == 1

    assert "made-up failure" in capsys.readouterr().out
    assert not (tmp_path / "models").exists()

"""Make the one shared split and the scaler from the cleaned data, and save them.

Run from ml/ with:

    uv run python -m splitting.build

It reads ml/data/phiusiil_cleaned.csv, works out the ten hostname features for
every row with the shared extractor, splits the rows by cleaned hostname, fits
the scaler on the training part only and saves:

* ml/data/split.csv: each row's index and its set (gitignored)
* ml/data/split_check.json: the row count and a fingerprint of the hosts, so the
  split cannot be used with cleaned data that was rebuilt or reordered (gitignored)
* ml/models/scaler.joblib: the fitted scaler (gitignored)
* ml/reports/scaling_distributions.png: the before-and-after charts

It stops with an error if a set is empty, a host or a link is in both sets, or a
set's phishing share is more than half a percentage point away from the whole
data's. The host check reads each link's host with Python's own URL parser, not
the clean-up the split groups by, so a mistake in the grouping cannot hide itself.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.preprocessing import StandardScaler

from cleaning.storage import CLEANED_CSV_NAME, load_cleaned
from features.hostname import FEATURE_NAMES, cleaned_host, extract_features
from splitting.scaling import SCALER_FILE_NAME, fit_scaler, save_scaler, scale
from splitting.scaling_chart import scaling_chart
from splitting.split import (
    SPLIT_CSV_NAME,
    TRAIN_SET,
    empty_sets,
    hosts_in_both,
    phishing_share_gap,
    plain_host,
    save_split,
    split_by_host,
)

ML_DIR = Path(__file__).resolve().parents[1]
MAX_SHARE_GAP_POINTS = 0.5
SCALING_CHART_NAME = "scaling_distributions.png"
CHART_DPI = 100


@dataclass(frozen=True)
class SplitRun:
    split: pd.Series
    hosts: pd.Series
    scaler: StandardScaler
    train_features: pd.DataFrame
    scaled_train: pd.DataFrame
    shared_hosts: set[str]
    shared_urls: set[str]
    share_gap_points: float


@dataclass(frozen=True)
class SavedPaths:
    split: Path
    scaler: Path
    chart: Path


def _per_row(urls: pd.Series, work) -> list:
    """Apply work to each link, naming the row if one cannot be read."""
    results = []
    for row, url in urls.items():
        try:
            results.append(work(url))
        except ValueError as error:
            raise ValueError(f"Could not read the link in row {row}: {error}") from error
    return results


def build_split(rows: pd.DataFrame) -> SplitRun:
    """Work out features and hosts, split by host and fit the scaler on the training part."""
    hosts = pd.Series(_per_row(rows["URL"], cleaned_host), index=rows.index)
    features = pd.DataFrame(_per_row(rows["URL"], extract_features), index=rows.index)
    features = features[list(FEATURE_NAMES)]
    split = split_by_host(rows["label"], hosts)
    train_features = features[split == TRAIN_SET]
    scaler = fit_scaler(train_features)
    # Hosts read independently of the grouping, so the leak check can catch a wrong grouping.
    link_hosts = pd.Series(_per_row(rows["URL"], plain_host), index=rows.index)
    return SplitRun(
        split=split,
        hosts=hosts,
        scaler=scaler,
        train_features=train_features,
        scaled_train=scale(scaler, train_features),
        shared_hosts=hosts_in_both(link_hosts, split),
        shared_urls=hosts_in_both(rows["URL"], split),
        share_gap_points=phishing_share_gap(rows["label"], split),
    )


def save_outputs(run: SplitRun, data_dir: Path, models_dir: Path, reports_dir: Path) -> SavedPaths:
    """Save the split, the scaler and the before-and-after chart."""
    chart_path = reports_dir / SCALING_CHART_NAME
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    scaling_chart(run.train_features, run.scaled_train).savefig(chart_path, dpi=CHART_DPI)
    return SavedPaths(
        split=save_split(run.split, run.hosts, data_dir / SPLIT_CSV_NAME),
        scaler=save_scaler(run.scaler, models_dir / SCALER_FILE_NAME),
        chart=chart_path,
    )


def check_run(run: SplitRun) -> list[str]:
    """Return a plain-language problem for each check the split fails."""
    empty = empty_sets(run.split)
    problems = [f"The {name} set is empty." for name in empty]
    if run.shared_hosts:
        problems.append(f"{len(run.shared_hosts)} hosts are in both the training and the test set.")
    if run.shared_urls:
        problems.append(f"{len(run.shared_urls)} links are in both the training and the test set.")
    # With an empty set the share gap has no meaning (it is NaN), so it is only checked otherwise.
    if not empty and run.share_gap_points > MAX_SHARE_GAP_POINTS:
        problems.append(
            f"A set's phishing share is {run.share_gap_points:.3f} points from the whole data's "
            f"(limit {MAX_SHARE_GAP_POINTS})."
        )
    return problems


def main(ml_dir: Path = ML_DIR) -> int:
    """Build, check and save the split and scaler. Returns 0 on success, 1 if a check fails."""
    cleaned_path = ml_dir / "data" / CLEANED_CSV_NAME
    if not cleaned_path.exists():
        print(f"Cleaned data not found at {cleaned_path}. Run 03_clean_dataset.ipynb first.")
        return 1
    run = build_split(load_cleaned(cleaned_path))
    problems = check_run(run)
    if problems:
        print("Split not saved:\n" + "\n".join(f"- {problem}" for problem in problems))
        return 1
    paths = save_outputs(run, ml_dir / "data", ml_dir / "models", ml_dir / "reports")
    counts = run.split.value_counts()
    print(f"Rows: {len(run.split):,} (training {counts.get(TRAIN_SET, 0):,}, test {len(run.split) - counts.get(TRAIN_SET, 0):,})")
    print(f"Phishing share gap: {run.share_gap_points:.3f} points. Hosts in both sets: 0")
    print(f"Saved {paths.split}, {paths.scaler} and {paths.chart}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

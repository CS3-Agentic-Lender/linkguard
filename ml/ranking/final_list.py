"""The final list of features the model trains on, with a reason for every feature dropped.

It works out the four rankings on the training split (mutual information, the forest's
built-in importance, the forest on held-out training hosts, and PCA weight), draws one chart
that compares them and writes the list with its reasons. The choice only uses the three
methods that look at the label. PCA shows which features copy each other.

Writes ml/reports/final_feature_list.md and ml/reports/feature_ranking_comparison.png.
Run from ml/:  uv run python -m ranking.final_list
"""

import sys
from pathlib import Path

import pandas as pd

from features.hostname import FEATURE_NAMES
from ranking.compare_methods import CHART_DPI, LABEL_METHODS, METHODS, comparison_chart, ordinal, pca_weights, rank_table
from ranking.forest_importance import forest_importance
from ranking.held_out_importance import held_out_importance
from ranking.mutual_info import mutual_information
from ranking.pca import PcaError, components_to_reach, fit_pca
from ranking.training_split import TrainingSplitError, load_inputs, training_split
from splitting.scaling import SCALER_FILE_NAME, load_scaler

# Each dropped feature can be worked out exactly from features that stay, so it adds nothing.
DROPPED = {
    "NoOfLettersInHostname": "It is HostnameLength minus the digits minus the special characters, so it adds nothing new.",
    "SpecialCharRatioInHostname": "The three ratios always add up to 1, so it is 1 minus the letter and digit ratios.",
}
# Kept, but they may be strong partly because of how the dataset's legitimate links were collected.
WATCH = {
    "NoOfSubDomain": "Few subdomains is typical of the big sites' front pages that make up the legitimate links.",
    "TLDLength": "Common endings like .com are typical of the big sites' front pages that make up the legitimate links.",
}
# Why each kept feature stays. IsDomainIP's reason is written with its row count in the report.
KEPT = {
    "HostnameLength": "Long hosts are a common phishing trick. It came higher than NoOfLettersInHostname, so it is the one of that pair that stays.",
    "NoOfDigitsInHostname": "It came 3rd or 4th in all three methods, so the methods agree it helps.",
    "DigitRatioInHostname": "It shows how much of the host is digits, which the count alone does not. It came 3rd by mutual information.",
    "NoOfSpecialCharsInHostname": "Many dots and hyphens are a common phishing sign. It came 2nd in two methods.",
    "LetterRatioInHostname": "It came 1st by mutual information. It shows how much of the host is letters, which no count shows.",
}
FINAL_FEATURES: tuple[str, ...] = tuple(name for name in FEATURE_NAMES if name not in DROPPED)
REPORT_NAME = "final_feature_list.md"
CHART_NAME = "feature_ranking_comparison.png"


def all_rankings(features: pd.DataFrame, split: pd.DataFrame, scaler) -> dict[str, pd.DataFrame]:
    """The four rankings, each as Rank, Feature and a score, on the training split only."""
    pca = fit_pca(features, split, scaler)
    main_count = components_to_reach(pca.explained_variance_ratio_)
    return {
        "Mutual information": mutual_information(features, split),
        "Forest (built-in)": forest_importance(features, split),
        "Forest (held-out hosts)": held_out_importance(features, split).table,
        "PCA weight": pca_weights(
            pca.components_[:main_count], pca.explained_variance_ratio_[:main_count], list(FEATURE_NAMES)
        ),
    }


def _why_kept(name: str, ip_rows: int, training_rows: int) -> str:
    if name == "IsDomainIP":
        return (
            f"It came last in every method because only {ip_rows:,} of {training_rows:,} training links use an IP address. "
            "It stays because a link that uses an IP address is a clear warning the result card can show."
        )
    if name in WATCH:
        return "Kept, but watched. " + WATCH[name]
    return KEPT[name]


def report(ranks: pd.DataFrame, ip_rows: int, training_rows: int) -> str:
    """The final list as a Markdown page."""
    def places(name: str) -> str:
        return ", ".join(ordinal(int(ranks.loc[name, method])) for method in LABEL_METHODS)

    lines = [
        "# The final feature list",
        "",
        f"The model trains on these {len(FINAL_FEATURES)} of the ten hostname features. "
        "Each method put the ten features in order, 1st to 10th, on the training split only.",
        "",
        f"![How the methods rank the features]({CHART_NAME})",
        "",
        "## Kept",
        "",
        "| Feature | Places (mutual information, forest, forest on held-out hosts) | Why it stays |",
        "|---|---|---|",
        *(f"| `{name}` | {places(name)} | {_why_kept(name, ip_rows, training_rows)} |" for name in FINAL_FEATURES),
        "",
        "## Dropped",
        "",
        "PCA showed that two of the ten features are exact copies of others. Each one also came lower than the features it copies.",
        "",
        "| Feature | Places | Why it goes |",
        "|---|---|---|",
        *(f"| `{name}` | {places(name)} | {reason} |" for name, reason in DROPPED.items()),
        "",
        "## Where the methods disagree",
        "",
        "- `NoOfSubDomain` and `TLDLength` come low by mutual information but high for the forest. "
        "Mutual information scores each feature on its own. The forest uses them together with the other features. "
        "On held-out training hosts, shuffling either one costs the forest the most accuracy. Both stay.",
        "- `LetterRatioInHostname` comes 1st by mutual information but lower for the forest. "
        "On its own it separates the classes well. The forest gets much of the same signal from the counts. It stays.",
        "- `NoOfSpecialCharsInHostname` comes higher in the forest's built-in importance than on held-out hosts. "
        "The built-in importance favours features with many different values. It stays.",
        "- PCA weight is not usefulness. PCA never looks at the label. "
        "`IsDomainIP` weighs a lot on two PCA components but is rare. `NoOfSubDomain` weighs little in PCA but leads the forest. "
        "So PCA was only used to find the copies.",
        "",
        "## How it follows the team's decisions",
        "",
        "- Every kept feature is one of the ten hostname features in the template-bias decision record "
        "(`docs/adr/0002-hostname-features-for-template-bias.md`). None is a URL-wide or page feature. None is a precomputed dataset column.",
        "- The leakage recheck found no single feature over the 95% line. So none of the eight gives the answer away on its own.",
        "- Two kept features are marked to watch. The legitimate links in the dataset are mostly front pages of big sites. "
        "Part of these features' strength may come from that, not from phishing itself:",
        *(f"  - `{name}`: {reason}" for name, reason in WATCH.items()),
        "",
        "## All four rankings",
        "",
        "| Feature | " + " | ".join(METHODS) + " |",
        "|---|" + "---|" * len(METHODS),
        *(f"| `{name}` | " + " | ".join(ordinal(int(ranks.loc[name, m])) for m in METHODS) + " |" for name in ranks.index),
        "",
        "Made by `uv run python -m ranking.final_list`.",
    ]
    return "\n".join(lines) + "\n"


def main(ml_dir: Path) -> int:
    """Work out the rankings, then save the chart and the list. Returns 1 and saves nothing if the inputs are wrong."""
    scaler_path = ml_dir / "models" / SCALER_FILE_NAME
    try:
        features, split = load_inputs(ml_dir / "data")
        if not scaler_path.is_file():
            raise PcaError(f'{scaler_path} was not found. Make it with "uv run python -m splitting.build" (see ml/README.md).')
        ranks = rank_table(all_rankings(features, split, load_scaler(scaler_path)))
    except (TrainingSplitError, PcaError) as error:
        print(f"Final feature list stopped: {error}")
        return 1
    training = training_split(features, split)
    reports_dir = ml_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    chart_path = reports_dir / CHART_NAME
    comparison_chart(ranks, set(DROPPED), set(WATCH)).savefig(chart_path, dpi=CHART_DPI)
    page = report(ranks, int(training["IsDomainIP"].sum()), len(training))
    report_path = reports_dir / REPORT_NAME
    report_path.write_text(page)
    print(page)
    print(f"Saved {report_path} and {chart_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parents[1]))

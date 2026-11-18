"""Score the saved chosen model on the outside test set, next to its PhiUSIIL test scores.

The outside test set is two CSVs collected by the outside link scripts: legitimate links with
paths and query strings, and recent phishing links from a public feed. Both live in
ml/data/outside/, which git ignores, because the phishing file holds live phishing links.

No link is opened. Each link goes through the same feature extractor the live app uses
(features.hostname.extract_features), which reads the link text only. Then the saved scaler
and the saved model score it, through the evaluation script's own load_model, score and
measures, so there is no second copy of the scoring code.

The PhiUSIIL side of the table is read from ml/reports/evaluation_results.json, which the
evaluation script saves. The test split is not scored again here.

Writes ml/reports/outside_results.json (numbers only, no links) and prints the table.

The model and scaler files are pickles, and loading a pickle runs code. Only load the files
our own steps saved to ml/models/, never ones from anywhere else.

Run from ml/:  uv run python -m evaluation.outside
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from cleaning.labels import LABEL_COLUMN, LEGITIMATE, PHISHING
from evaluation.evaluate import (
    MODEL_PATH,
    RESULTS_PATH,
    EvaluationError,
    ScoredRows,
    confusion_matrix,
    counts,
    load_model,
    measures,
    save_results,
    score,
)
from features.hostname import FEATURE_NAMES, cleaned_host, extract_features
from training.pipeline import FEATURES_PATH, HOSTNAME_COLUMN, ML_DIR, SCALER_PATH, PipelineError, load_scaler

OUTSIDE_DIR = ML_DIR / "data" / "outside"
LEGIT_PATH = OUTSIDE_DIR / "legit_links.csv"
PHISHING_PATH = OUTSIDE_DIR / "phishing_links.csv"
OUTSIDE_RESULTS_PATH = ML_DIR / "reports" / "outside_results.json"
URL_COLUMN = "url"
LABEL = "Outside test set: links collected outside PhiUSIIL, scored once by the saved chosen model."
# The measures shown side by side, in table order.
TABLE = (
    ("recall", "Phishing recall"),
    ("precision", "Precision"),
    ("f1", "F1"),
    ("roc_auc", "ROC-AUC"),
    ("false_alarm_rate", "False alarm rate (legitimate)"),
    ("accuracy", "Accuracy"),
)
# A drop bigger than this, in percentage points, must be explained in the write-up.
BIG_DROP_POINTS = 10


def load_outside_links(legit_path: Path, phishing_path: Path) -> pd.DataFrame:
    """Both outside CSVs as one table of url and label. Checks each file holds only its own label."""
    frames = []
    for path, expected in ((legit_path, LEGITIMATE), (phishing_path, PHISHING)):
        if not path.is_file():
            raise EvaluationError(f"Missing {path}. See the outside test set sections in ml/README.md to collect it.")
        frame = pd.read_csv(path, usecols=[URL_COLUMN, LABEL_COLUMN], dtype={URL_COLUMN: str}, keep_default_na=False)
        if frame.empty:
            raise EvaluationError(f"{path} has no links.")
        if set(frame[LABEL_COLUMN]) != {expected}:
            raise EvaluationError(f"Every link in {path} must have label {expected}.")
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def outside_features(links: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """The ten features of every link the extractor can read, and how many it could not.

    Uses the live app's extractor on the link text. A link it cannot read is left out and
    counted, the same way the app would refuse to score it.
    """
    rows, kept, skipped = [], [], 0
    for index, link in links[URL_COLUMN].items():
        try:
            rows.append(extract_features(link))
        except ValueError:
            skipped += 1
            continue
        kept.append(index)
    features = pd.DataFrame(rows, columns=list(FEATURE_NAMES), index=kept)
    return features, skipped


def known_hosts(features_path: Path) -> set[str]:
    """The cleaned hosts in the PhiUSIIL feature set, training and test rows together."""
    if not features_path.is_file():
        raise EvaluationError(f"Missing {features_path}. It is saved by the feature set step.")
    hosts = pd.read_csv(features_path, usecols=[HOSTNAME_COLUMN], keep_default_na=False, dtype={HOSTNAME_COLUMN: str})
    return set(hosts[HOSTNAME_COLUMN])


def mistakes_by_host(links: pd.Series, scored: ScoredRows, phiusiil_hosts: set[str]) -> dict:
    """False alarms and misses, split by whether the link's host is also in PhiUSIIL."""
    in_phiusiil = np.array([cleaned_host(link) in phiusiil_hosts for link in links])
    actual, predicted = scored.labels == PHISHING, scored.predicted == PHISHING
    result = {}
    for name, rows in (("host_in_phiusiil", in_phiusiil), ("new_host", ~in_phiusiil)):
        result[name] = {
            "legitimate": int(np.sum(rows & ~actual)),
            "false_alarms": int(np.sum(rows & ~actual & predicted)),
            "phishing": int(np.sum(rows & actual)),
            "missed": int(np.sum(rows & actual & ~predicted)),
        }
    return result


def drops(outside: dict, phiusiil: dict) -> dict[str, float]:
    """How many percentage points each measure is worse on the outside set. Negative means better.

    A higher false alarm rate is worse, so its drop is outside minus PhiUSIIL. For every other
    measure higher is better, so the drop is PhiUSIIL minus outside.
    """
    result = {}
    for name, _ in TABLE:
        gap = outside[name] - phiusiil[name] if name == "false_alarm_rate" else phiusiil[name] - outside[name]
        result[name] = round(gap * 100, 2)
    return result


def load_phiusiil_scores(path: Path) -> dict:
    if not path.is_file():
        raise EvaluationError(f"Missing {path}. Run 'uv run python -m evaluation.evaluate' first.")
    saved = json.loads(path.read_text())
    return {name: saved["test"][name] for name, _ in TABLE}


def evaluate_outside(
    legit_path: Path, phishing_path: Path, features_path: Path, scaler_path: Path, model_path: Path, phiusiil_path: Path
) -> dict:
    links = load_outside_links(legit_path, phishing_path)
    features, unreadable = outside_features(links)
    readable = links.loc[features.index]
    scaler = load_scaler(scaler_path)
    model = load_model(model_path)
    scaled = np.asarray(scaler.transform(features), dtype=float)
    scored = score(model, scaled, readable[LABEL_COLUMN])
    outside = measures(scored)
    phiusiil = load_phiusiil_scores(phiusiil_path)
    outside_scores = {name: outside["scores"][name] for name, _ in TABLE}
    gaps = drops(outside_scores, phiusiil)
    return {
        "label": LABEL,
        "model": model_path.name,
        "positive_class": "phishing (label 1)",
        "decision": "the model's own predict(): phishing when its phishing score is above 0.5",
        "outside_rows": int(scored.labels.size),
        "outside_class_counts": {
            "phishing": int(np.sum(scored.labels == PHISHING)),
            "legitimate": int(np.sum(scored.labels == LEGITIMATE)),
        },
        "unreadable_links": unreadable,
        "outside": outside_scores,
        "phiusiil_test": phiusiil,
        "drop_points": gaps,
        "big_drops": [name for name, gap in gaps.items() if gap > BIG_DROP_POINTS],
        "confusion_matrix": confusion_matrix(counts(scored)),
        "mistakes_by_host": mistakes_by_host(readable[URL_COLUMN], scored, known_hosts(features_path)),
    }


def table(found: dict) -> str:
    """The outside and PhiUSIIL measures side by side, as a Markdown table."""
    lines = ["| Measure | Outside set | PhiUSIIL test split | Drop (points) |", "|---|---|---|---|"]
    for name, title in TABLE:
        lines.append(
            f"| {title} | {found['outside'][name]:.4f} | {found['phiusiil_test'][name]:.4f} | {found['drop_points'][name]:+.2f} |"
        )
    return "\n".join(lines)


def summary(found: dict) -> str:
    counts_line = found["outside_class_counts"]
    lines = [
        found["label"],
        f"Outside rows: {found['outside_rows']:,} ({counts_line['phishing']:,} phishing, "
        f"{counts_line['legitimate']:,} legitimate). Links the extractor could not read: {found['unreadable_links']}.",
        "",
        table(found),
        "",
        f"Drops over {BIG_DROP_POINTS} points: {', '.join(found['big_drops']) or 'none'}.",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--legit", type=Path, default=LEGIT_PATH, help="legitimate outside links CSV")
    parser.add_argument("--phishing", type=Path, default=PHISHING_PATH, help="phishing outside links CSV")
    parser.add_argument("--features", type=Path, default=FEATURES_PATH, help="PhiUSIIL feature set CSV")
    parser.add_argument("--scaler", type=Path, default=SCALER_PATH, help="saved scaler (.joblib)")
    parser.add_argument("--model", type=Path, default=MODEL_PATH, help="saved chosen model (.joblib)")
    parser.add_argument("--phiusiil", type=Path, default=RESULTS_PATH, help="saved PhiUSIIL evaluation results")
    parser.add_argument("--results", type=Path, default=OUTSIDE_RESULTS_PATH, help="where to save the results")
    args = parser.parse_args(argv)

    try:
        found = evaluate_outside(args.legit, args.phishing, args.features, args.scaler, args.model, args.phiusiil)
    except (PipelineError, EvaluationError) as error:
        print(f"Outside evaluation stopped: {error}", file=sys.stderr)
        return 1
    print(summary(found))
    print(f"Saved {save_results(found, args.results).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

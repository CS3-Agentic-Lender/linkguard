"""Check the reasons on five made-up links by hand, and time a scan with reasons.

For each link it prints the full explanation (every model feature's scaled value,
coefficient and push on the score) next to the reasons picked from it, so a person can check
the reasons against the full list. It also times the scan steps for one link: extract the
features, scale them, score them and pick the reasons.

The links are made up and only ever handled as text. Nothing is fetched or opened.

Needs the saved scaler and the saved model (see "The final model" in ml/README.md). Both are
pickles, and loading a pickle runs code, so only load the files saved to ml/models/.
Writes ml/reports/explanation_check.md.

Run from ml/:  uv run python -m training.explanation_check
"""

import argparse
import sys
import time
from collections.abc import Sequence
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from features.explain import (
    DIGIT_PAIR,
    MAX_REASONS,
    can_be_reason,
    linear_contributions,
    model_coefficients,
    reasons_for_link,
)
from features.hostname import FEATURE_NAMES, cleaned_host, extract_features
from features.reasons import NOT_SHOWN, reason_for
from training.pipeline import ML_DIR, SCALER_PATH, PipelineError, load_scaler

MODEL_PATH = ML_DIR / "models" / "model.joblib"
REPORT_PATH = ML_DIR / "reports" / "explanation_check.md"
TIMING_RUNS = 200
TIME_LIMIT_SECONDS = 2.0

# Made-up links, one per kind of warning sign. 192.0.2.0/24 and .example are reserved for
# documentation, so none of these can be a real site.
SAMPLE_LINKS = (
    "http://192.0.2.44/account/verify",
    "https://secure-login-account-update-verification.example.com/",
    "https://pay8812-34ref77.example.net/",
    "https://www.example.com/",
    "https://mail.service.example.co.uk/",
)


class CheckError(Exception):
    """The saved model could not be loaded."""


def load_model(model_path: Path):
    if not model_path.is_file():
        raise CheckError(
            f"The saved model was not found at {model_path}. Run `uv run python -m training.final_model` first."
        )
    return joblib.load(model_path)


def scaled_features(link: str, scaler) -> dict[str, float]:
    """The link's ten feature values after the saved scaler, by name."""
    frame = pd.DataFrame([extract_features(link)], columns=list(FEATURE_NAMES))
    return dict(zip(FEATURE_NAMES, (float(value) for value in scaler.transform(frame)[0])))


def explain(link: str, scaler, model) -> dict:
    """Everything the hand check needs for one link."""
    scaled = scaled_features(link, scaler)
    row = np.array([[scaled[name] for name in FEATURE_NAMES]])
    contributions = linear_contributions(model_coefficients(model), scaled)
    return {
        "link": link,
        "host": cleaned_host(link),
        "score": float(model.predict_proba(row)[0, 1]),
        "scaled": scaled,
        "coefficients": model_coefficients(model),
        "contributions": contributions,
        "reasons": reasons_for_link(model, scaled),
    }


def slowest_scan_seconds(link: str, scaler, model, runs: int = TIMING_RUNS) -> float:
    """The slowest of `runs` scans of one link: features, scaling, score and reasons."""
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        scaled = scaled_features(link, scaler)
        model.predict_proba(np.array([[scaled[name] for name in FEATURE_NAMES]]))
        reasons_for_link(model, scaled)
        times.append(time.perf_counter() - start)
    return max(times)


def why_shown_or_not(name: str, entry: dict) -> str:
    """Why a feature is, or is not, one of the link's reasons, in the order the rules apply."""
    contributions, scaled = entry["contributions"], entry["scaled"]
    if name in entry["reasons"]:
        return f"**Reason {entry['reasons'].index(name) + 1}**"
    if name in NOT_SHOWN:
        return "never shown"
    if contributions[name] <= 0:
        return "lowered the score"
    if not can_be_reason(name, contributions, scaled):
        return "its sentence is not true for this link"
    if name in DIGIT_PAIR:
        count, share = DIGIT_PAIR
        other = share if name == count else count
        smaller = share if contributions[count] >= contributions[share] else count
        if name == smaller and can_be_reason(other, contributions, scaled):
            return "the other digit reason pushed more"
    return f"not in the top {MAX_REASONS}"


def link_section(entry: dict) -> list[str]:
    rows = sorted(entry["contributions"], key=lambda name: -entry["contributions"][name])
    reasons = [f"{place}. {reason_for(name)} (`{name}`)" for place, name in enumerate(entry["reasons"], start=1)]
    return [
        f"### `{entry['link']}`",
        "",
        f"Host measured: `{entry['host']}`. Phishing score: {entry['score']:.3f}.",
        "",
        "| Feature | Scaled value | Coefficient | Push on the score | Shown? |",
        "|---|---|---|---|---|",
        *(
            f"| `{name}` | {entry['scaled'][name]:+.3f} | {entry['coefficients'][name]:+.3f} "
            f"| {entry['contributions'][name]:+.3f} | {why_shown_or_not(name, entry)} |"
            for name in rows
        ),
        "",
        "Reasons picked:" if reasons else "Reasons picked: none.",
        "",
        *reasons,
        "",
    ]


def report(entries: Sequence[dict], slowest: float) -> str:
    verdict = "under" if slowest < TIME_LIMIT_SECONDS else "OVER"
    return "\n".join(
        [
            "# Reasons hand check",
            "",
            (
                "The reasons picked for five made-up links, next to the full explanation they come from. "
                "Each push is the coefficient times the scaled value, in log-odds, compared with an average "
                "training link (every scaled value 0). Above zero pushed the score towards phishing. "
                f"The rules for picking up to {MAX_REASONS} are in `docs/adr/0004-explanation-method.md`."
            ),
            "",
            (
                "The links are made up and were only handled as text. The phishing score is the model's "
                "probability. Whether a result is Suspicious or High risk depends on the risk cut-offs, "
                "which are set elsewhere, so reasons are shown here for every link."
            ),
            "",
            *(line for entry in entries for line in link_section(entry)),
            "## Timing",
            "",
            (
                f"The slowest of {TIMING_RUNS} scans of each link (features, scaling, score and reasons): "
                f"**{slowest * 1000:.1f} ms**, {verdict} the {TIME_LIMIT_SECONDS:g} s limit. "
                "Loading the model and scaler happens once at start-up and is not included."
            ),
            "",
            "Made by `uv run python -m training.explanation_check`.",
            "",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scaler", type=Path, default=SCALER_PATH, help="saved scaler (.joblib)")
    parser.add_argument("--model", type=Path, default=MODEL_PATH, help="saved model (.joblib)")
    parser.add_argument("--report", type=Path, default=REPORT_PATH, help="where to save the Markdown report")
    args = parser.parse_args(argv)

    try:
        scaler = load_scaler(args.scaler)
        model = load_model(args.model)
    except (PipelineError, CheckError) as error:
        print(f"Explanation check stopped: {error}", file=sys.stderr)
        return 1
    entries = [explain(link, scaler, model) for link in SAMPLE_LINKS]
    slowest = max(slowest_scan_seconds(link, scaler, model) for link in SAMPLE_LINKS)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report(entries, slowest))
    for entry in entries:
        print(f"{entry['host']}: {', '.join(entry['reasons']) or 'no reasons'}")
    print(f"Slowest scan: {slowest * 1000:.1f} ms. Saved {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

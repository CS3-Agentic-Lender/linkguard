"""Fit the tuned model on every training row, save it as one file, and check it loads.

The settings come from ml/reports/tuning_results.json, which the tuning search saves. The model
is fitted on the training rows only, after the saved scaler from the split-and-scale story has
transformed them. The test split is never loaded.

How the backend uses the two files, for each link:

    the ten hostname features, in the extractor's order (FEATURE_NAMES)
    -> the saved scaler (ml/models/scaler.joblib), transform only
    -> the saved model (ml/models/model.joblib), predict or predict_proba

The scaler works on all ten features. The model keeps only the 8 in the final feature list as
its first step, so the backend passes all ten scaled values and cannot pick the wrong columns.
Scaling ten columns and then keeping 8 gives exactly the same numbers as scaling only those 8,
because the scaler treats each column on its own.

After saving, a fresh Python process loads the file and predicts a handful of training rows.
The run stops if those predictions differ from the ones made before saving.

The model file is a pickle, and loading a pickle runs code. Only load the file this script
saved to ml/models/, never one from anywhere else. *.joblib files are gitignored.

Run from ml/:  uv run python -m training.final_model
"""

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import joblib
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

from cleaning.labels import PHISHING
from features.hostname import FEATURE_NAMES
from ranking.final_list import FINAL_FEATURES
from training.pipeline import FEATURES_PATH, ML_DIR, SCALER_PATH, SPLIT_PATH, PipelineError, load_training_set
from training.tuning import RESULTS_PATH, base_model

MODEL_PATH = ML_DIR / "models" / "model.joblib"
CHECK_ROWS = 10  # training rows the load check predicts, spread evenly over the training set
CHECK_TIMEOUT_SECONDS = 120


class FinalModelError(Exception):
    """The tuning results are missing or the saved model does not behave like the fitted one."""


def chosen_settings(results_path: Path) -> dict[str, float]:
    """The C and l1_ratio the tuning search chose."""
    if not results_path.is_file():
        raise FinalModelError(
            f"The tuning results were not found at {results_path}. Run `uv run python -m training.tuning` first."
        )
    try:
        results = json.loads(results_path.read_text())
        features, chosen = results.get("features"), results["chosen"]
        settings = {"C": float(chosen["C"]), "l1_ratio": float(chosen["l1_ratio"])}
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise FinalModelError(
            f"The tuning results at {results_path} could not be read ({error!r}). Run the tuning again."
        )
    if features != list(FINAL_FEATURES):
        raise FinalModelError("The tuning results were not made with the final feature list.")
    return settings


def build_model(settings: dict[str, float]) -> Pipeline:
    """Keep the 8 final features out of the ten scaled ones, then the tuned logistic regression."""
    keep = [FEATURE_NAMES.index(name) for name in FINAL_FEATURES]
    return Pipeline(
        [
            ("keep_final_features", ColumnTransformer([("final", "passthrough", keep)], remainder="drop")),
            # The same fixed settings as the search (base_model), with the chosen C and l1_ratio.
            ("model", base_model().set_params(C=settings["C"], l1_ratio=settings["l1_ratio"])),
        ]
    )


def save_model(model: Pipeline, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    return path


# Runs in a separate Python process, so nothing from this one (the fitted model, imports) is reused.
_LOAD_CHECK = """
import json, sys
import joblib, numpy as np
rows = np.asarray(json.loads(sys.stdin.read()), dtype=float)
model = joblib.load(sys.argv[1])
phishing = list(model.classes_).index(1)
print(json.dumps({"labels": model.predict(rows).tolist(), "scores": model.predict_proba(rows)[:, phishing].tolist()}))
"""


def load_check(path: Path, rows: np.ndarray, model: Pipeline) -> None:
    """Load the saved file in a fresh Python process and compare its predictions with the fitted model's."""
    try:
        done = subprocess.run(
            [sys.executable, "-c", _LOAD_CHECK, str(path)],
            input=json.dumps(rows.tolist()),
            capture_output=True,
            text=True,
            check=False,
            timeout=CHECK_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise FinalModelError(f"Loading the saved model in a fresh Python session took over {CHECK_TIMEOUT_SECONDS} s.")
    if done.returncode != 0:
        raise FinalModelError(f"The saved model could not be loaded in a fresh Python session: {done.stderr.strip()}")
    loaded = json.loads(done.stdout)
    if loaded["labels"] != model.predict(rows).tolist():
        raise FinalModelError("The saved model predicts different labels from the model before saving.")
    phishing = list(model.classes_).index(PHISHING)
    if not np.allclose(loaded["scores"], model.predict_proba(rows)[:, phishing], rtol=0, atol=1e-12):
        raise FinalModelError("The saved model gives different phishing scores from the model before saving.")


def check_rows(scaled: np.ndarray) -> np.ndarray:
    """CHECK_ROWS training rows spread evenly from the first to the last, not just the first few."""
    return scaled[np.linspace(0, len(scaled) - 1, CHECK_ROWS).astype(int)]


def save_checked(model: Pipeline, path: Path, rows: np.ndarray) -> Path:
    """Save to a temporary file, load-check it, and only then move it to path.

    A file that fails the check is deleted, so it never sits where the backend loads the model.
    """
    temporary = path.with_name(path.name + ".checking")
    save_model(model, temporary)
    try:
        load_check(temporary, rows, model)
    except FinalModelError:
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(path)
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--features", type=Path, default=FEATURES_PATH, help="training feature set CSV")
    parser.add_argument("--split", type=Path, default=SPLIT_PATH, help="saved train/test split CSV")
    parser.add_argument("--scaler", type=Path, default=SCALER_PATH, help="saved scaler (.joblib)")
    parser.add_argument("--results", type=Path, default=RESULTS_PATH, help="tuning results JSON")
    parser.add_argument("--model", type=Path, default=MODEL_PATH, help="where to save the model (.joblib)")
    args = parser.parse_args(argv)

    try:
        settings = chosen_settings(args.results)
        training = load_training_set(args.features, args.split, args.scaler)
        model = build_model(settings).fit(training.scaled, training.labels.to_numpy())
        save_checked(model, args.model, check_rows(training.scaled))
    except (PipelineError, FinalModelError) as error:
        print(f"Saving the final model stopped: {error}", file=sys.stderr)
        return 1
    print(
        f"Fitted on {len(training.rows):,} training rows with C = {settings['C']:g}, l1_ratio = {settings['l1_ratio']:g}"
    )
    print(f"Saved {args.model}")
    print(f"Load check passed: a fresh Python session gave the same predictions on {CHECK_ROWS} training rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

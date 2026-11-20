from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any
import warnings

import joblib
from features.explain import tree_explainer
from features.hostname import FEATURE_NAMES, extract_features

# The training code saves both files here (see ml/README.md). They are shared
# outside git, like the dataset. LINKGUARD_MODEL_DIR points the backend at
# another folder, which the tests use for their small fixture model.
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[2] / "ml" / "models"
MODEL_DIR_VARIABLE = "LINKGUARD_MODEL_DIR"
SCALER_FILE = "scaler.joblib"
MODEL_FILE = "model.joblib"
# The model's label for phishing, as in training (1 = phishing after recoding).
PHISHING = 1


class ModelFileMissing(RuntimeError):
    """Start-up stops with this when the scaler or the model file isn't there."""


class ModelFileWrong(RuntimeError):
    """Start-up stops with this when a file is there but can't be used as it is."""


@dataclass(frozen=True)
class LoadedModel:
    scaler: Any
    model: Any
    # Gives each kept feature's push on a link's score, for the reasons. Built once
    # here, because building SHAP's tree explainer takes far longer than one scan.
    explainer: Any


def model_dir() -> Path:
    return Path(os.environ.get(MODEL_DIR_VARIABLE) or DEFAULT_MODEL_DIR)


def load_model(folder: Path) -> LoadedModel:
    """Load the scaler and the model once. Both are checked before either is loaded,
    so a missing file is named straight away instead of after a slow load."""
    paths = {name: folder / name for name in (SCALER_FILE, MODEL_FILE)}
    for path in paths.values():
        if not path.is_file():
            raise ModelFileMissing(
                f"Can't start: {path} is missing. "
                "Make it with the training code in ml/, as ml/README.md explains."
            )
    scaler = joblib.load(paths[SCALER_FILE])
    # The training code fits the scaler on a table, so it remembers the column order.
    # Each check sends the features in FEATURE_NAMES order, so recorded names are
    # required and must match that order.
    names = getattr(scaler, "feature_names_in_", None)
    if names is None:
        raise ModelFileWrong(
            f"Can't start: {paths[SCALER_FILE]} has no recorded feature order. "
            "Make it again with the training code in ml/."
        )
    if tuple(names) != FEATURE_NAMES:
        raise ModelFileWrong(
            f"Can't start: {paths[SCALER_FILE]} expects the features in a different order "
            f"({', '.join(names)}). Make it again with the training code in ml/."
        )
    model = joblib.load(paths[MODEL_FILE])
    try:
        explainer = tree_explainer(model)
    except ValueError as error:
        raise ModelFileWrong(f"Can't start: {paths[MODEL_FILE]} is not the saved model's shape. {error}") from None
    return LoadedModel(scaler=scaler, model=model, explainer=explainer)


def scaled_features(loaded: LoadedModel, link: str) -> list[float]:
    """A cleaned link's ten features, scaled like the training rows, in FEATURE_NAMES order.

    They are worked out from the link's text alone, with the same shared extractor the
    training code uses.
    """
    features = extract_features(link)
    row = [[features[name] for name in FEATURE_NAMES]]
    return [float(value) for value in loaded.scaler.transform(row)[0]]


# What scikit-learn says when a fitted scaler gets a plain row with no column names.
COLUMN_NAME_WARNING = "X does not have valid feature names"


def silence_column_name_warning() -> None:
    """Hide scikit-learn's column-name warning for the rest of the process.

    Each check hands the scaler a plain row, so scikit-learn would warn on every scan.
    load_model has already checked that the scaler's order matches the row, so the
    warning says nothing new. This is called once at start-up, not around each scan:
    scans run side by side in FastAPI's thread pool, and a filter switched on and off
    per scan is shared by the whole process, so two scans could undo each other's.
    Only this one message is hidden; every other warning still shows.
    """
    warnings.filterwarnings("ignore", message=COLUMN_NAME_WARNING, category=UserWarning)


def score_of(loaded: LoadedModel, scaled: list[float]) -> float:
    """The model's phishing score, from 0 to 1, for one link's ten scaled features.

    The model keeps the final features itself, so all ten scaled values go in.
    """
    phishing = list(loaded.model.classes_).index(PHISHING)
    return float(loaded.model.predict_proba([scaled])[0][phishing])


def phishing_score(loaded: LoadedModel, link: str) -> float:
    """The model's phishing score, from 0 to 1, for a cleaned link.

    /scan works out the scaled features once and reuses them for the reasons, so it
    calls scaled_features and score_of itself. This is kept for the tests.
    """
    return score_of(loaded, scaled_features(loaded, link))

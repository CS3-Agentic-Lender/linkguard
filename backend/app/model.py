from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import joblib

# The training code saves both files here (see ml/README.md). They are shared
# outside git, like the dataset. LINKGUARD_MODEL_DIR points the backend at
# another folder, which the tests use for their small fixture model.
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[2] / "ml" / "models"
MODEL_DIR_VARIABLE = "LINKGUARD_MODEL_DIR"
SCALER_FILE = "scaler.joblib"
MODEL_FILE = "model.joblib"


class ModelFileMissing(RuntimeError):
    """Start-up stops with this when the scaler or the model file isn't there."""


@dataclass(frozen=True)
class LoadedModel:
    scaler: Any
    model: Any


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
    return LoadedModel(
        scaler=joblib.load(paths[SCALER_FILE]),
        model=joblib.load(paths[MODEL_FILE]),
    )

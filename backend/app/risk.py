from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal

from app.model import ModelFileMissing, ModelFileWrong

# The cut-offs story saves the two cut-offs here, next to the model files, as
# {"lower": 0.20, "upper": 0.60}. They are read from the file, never typed into
# the code, so changing the file changes the levels without a code change.
CUTOFFS_FILE = "cutoffs.json"

RiskLevel = Literal["Safe", "Suspicious", "High risk"]


@dataclass(frozen=True)
class Cutoffs:
    lower: float
    upper: float


def load_cutoffs(folder: Path) -> Cutoffs:
    """Read the two cut-offs once, at start-up, and check they make sense."""
    path = folder / CUTOFFS_FILE
    if not path.is_file():
        raise ModelFileMissing(
            f"Can't start: {path} is missing. "
            "It holds the two risk-level cut-offs, as ml/README.md explains."
        )
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ModelFileWrong(f"Can't start: {path} is not valid JSON.") from None

    if not isinstance(values, dict) or set(values) != {"lower", "upper"}:
        raise ModelFileWrong(f'Can\'t start: {path} must hold exactly "lower" and "upper".')
    # bool is a kind of int in Python, so true and false are ruled out by name.
    if any(isinstance(value, bool) or not isinstance(value, int | float) for value in values.values()):
        raise ModelFileWrong(f"Can't start: the cut-offs in {path} must be numbers.")
    lower, upper = float(values["lower"]), float(values["upper"])
    if not 0 <= lower < upper <= 1:
        raise ModelFileWrong(
            f"Can't start: the cut-offs in {path} must be between 0 and 1, with lower below upper "
            f"(they are {lower} and {upper})."
        )
    return Cutoffs(lower=lower, upper=upper)


def risk_level(score: float, cutoffs: Cutoffs) -> RiskLevel:
    """Below the lower cut-off is Safe, from the lower up to below the upper is
    Suspicious, and at or above the upper is High risk."""
    if score < cutoffs.lower:
        return "Safe"
    if score < cutoffs.upper:
        return "Suspicious"
    return "High risk"

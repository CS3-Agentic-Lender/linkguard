"""Before-and-after charts of each feature on the training set, around scaling.

Each feature gets one row: its original values on the left, its scaled values on
the right. Scaling only moves and stretches the values, so the two shapes should
match and only the numbers on the axis change. A shape that changes would point
to a bug.

Built on matplotlib's Figure directly, not pyplot, so it draws the same way in
tests, scripts and notebooks without needing a screen.
"""

import pandas as pd
from matplotlib.figure import Figure

BIN_COUNT = 40
PANEL_WIDTH_INCHES = 4.5
PANEL_HEIGHT_INCHES = 2.2
BEFORE_COLOUR = "#5b7a99"
AFTER_COLOUR = "#2e8b57"


def scaling_chart(before: pd.DataFrame, after: pd.DataFrame) -> Figure:
    """Return a figure with a before and an after histogram for each feature."""
    if list(before.columns) != list(after.columns):
        raise ValueError("Before and after must have the same columns, in the same order.")
    feature_count = len(before.columns)
    figure = Figure(
        figsize=(2 * PANEL_WIDTH_INCHES, feature_count * PANEL_HEIGHT_INCHES),
        layout="constrained",
    )
    axes = figure.subplots(feature_count, 2, squeeze=False)
    for row, feature in enumerate(before.columns):
        before_axis, after_axis = axes[row]
        before_axis.hist(before[feature], bins=BIN_COUNT, color=BEFORE_COLOUR)
        before_axis.set_title(f"{feature}: before")
        before_axis.set_xlabel("Original value")
        before_axis.set_ylabel("Training rows")
        after_axis.hist(after[feature], bins=BIN_COUNT, color=AFTER_COLOUR)
        after_axis.set_title(f"{feature}: after")
        after_axis.set_xlabel("Scaled value (mean 0, spread 1)")
    figure.suptitle("Each feature on the training set, before and after scaling")
    return figure

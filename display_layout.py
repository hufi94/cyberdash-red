#!/usr/bin/env python3
"""Display-independent sizing helpers for the 640x480 dashboard canvas."""


DESIGN_WIDTH = 640
DESIGN_HEIGHT = 480


def fit_design_to_window(
    window_width: float,
    window_height: float,
    design_width: float = DESIGN_WIDTH,
    design_height: float = DESIGN_HEIGHT,
) -> tuple[float, float, float]:
    """Return uniform scale and centered offsets without distorting the UI."""

    if window_width <= 0 or window_height <= 0:
        return 1.0, 0.0, 0.0
    scale = min(window_width / design_width, window_height / design_height)
    offset_x = (window_width - design_width * scale) / 2.0
    offset_y = (window_height - design_height * scale) / 2.0
    return scale, offset_x, offset_y

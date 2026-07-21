#!/usr/bin/env python3
"""Display-independent sizing helpers for the dashboard canvas."""


DESIGN_WIDTH = 640
DESIGN_HEIGHT = 480
MAX_DESIGN_WIDTH = 854
SAFE_SCREEN_INSET = 6


def design_width_for_window(
    window_width: float,
    window_height: float,
    design_height: float = DESIGN_HEIGHT,
    minimum_width: float = DESIGN_WIDTH,
    maximum_width: float = MAX_DESIGN_WIDTH,
) -> float:
    """Match wide displays without stretching the 640x480 design."""

    if window_width <= 0 or window_height <= 0:
        return minimum_width
    aspect_width = round(design_height * window_width / window_height)
    return max(minimum_width, min(maximum_width, aspect_width))


def fit_design_to_window(
    window_width: float,
    window_height: float,
    design_width: float = DESIGN_WIDTH,
    design_height: float = DESIGN_HEIGHT,
    safe_inset: float = 0,
) -> tuple[float, float, float]:
    """Return uniform scale and centered offsets without distorting the UI."""

    if window_width <= 0 or window_height <= 0:
        return 1.0, 0.0, 0.0
    inset = max(0.0, safe_inset)
    available_width = max(1.0, window_width - inset * 2.0)
    available_height = max(1.0, window_height - inset * 2.0)
    scale = min(
        available_width / design_width,
        available_height / design_height,
    )
    offset_x = (window_width - design_width * scale) / 2.0
    offset_y = (window_height - design_height * scale) / 2.0
    return scale, offset_x, offset_y

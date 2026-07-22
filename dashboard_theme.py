#!/usr/bin/env python3
"""Pure geometry and colour helpers for the 640x480 dashboard theme."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PanelRect:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y + self.height


@dataclass(frozen=True)
class DashboardPanels:
    top_left: PanelRect
    top_right: PanelRect
    bottom_left: PanelRect
    bottom_right: PanelRect
    header_y: float
    header_height: float


COMPACT_WIDTH_LIMIT = 680.0
COMPACT_UI_SCALE = 1.08


def dashboard_panels(
    design_width: float,
    design_height: float = 480.0,
    margin: float = 10.0,
    gap: float = 6.0,
    header_height: float = 42.0,
) -> DashboardPanels:
    """Return the balanced four-module geometry used by the dashboard."""

    usable_width = design_width - margin * 2.0
    column_width = (usable_width - gap) / 2.0
    content_top = design_height - margin - header_height - gap
    content_height = content_top - margin
    top_height = round((content_height - gap) * 0.48)
    bottom_height = content_height - gap - top_height
    top_y = margin + bottom_height + gap
    right_x = margin + column_width + gap

    return DashboardPanels(
        top_left=PanelRect(margin, top_y, column_width, top_height),
        top_right=PanelRect(right_x, top_y, column_width, top_height),
        bottom_left=PanelRect(margin, margin, column_width, bottom_height),
        bottom_right=PanelRect(right_x, margin, column_width, bottom_height),
        header_y=design_height - margin - header_height,
        header_height=header_height,
    )


def responsive_dashboard_panels(
    design_width: float,
    design_height: float = 480.0,
) -> DashboardPanels:
    """Use more of the physical area only on compact 640-pixel displays."""

    if design_width <= COMPACT_WIDTH_LIMIT:
        return dashboard_panels(
            design_width,
            design_height,
            margin=7.0,
            gap=4.0,
            header_height=39.0,
        )
    return dashboard_panels(design_width, design_height)


def dashboard_ui_scale(design_width: float) -> float:
    """Return a restrained legibility boost for the 3.5-inch display."""

    if design_width <= COMPACT_WIDTH_LIMIT:
        return COMPACT_UI_SCALE
    return 1.0


def clipped_outline_points(
    x: float,
    y: float,
    width: float,
    height: float,
    cut: float,
) -> tuple[float, ...]:
    """Return an eight-point rectangle with clipped corners."""

    clipped = max(0.0, min(cut, width / 2.0, height / 2.0))
    return (
        x + clipped,
        y,
        x + width - clipped,
        y,
        x + width,
        y + clipped,
        x + width,
        y + height - clipped,
        x + width - clipped,
        y + height,
        x + clipped,
        y + height,
        x,
        y + height - clipped,
        x,
        y + clipped,
    )


def active_temperature_segments(
    temperature: float,
    minimum: float,
    maximum: float,
    segment_count: int,
) -> int:
    """Map one temperature to a clamped number of illuminated segments."""

    if segment_count <= 0:
        raise ValueError("segment_count must be positive")
    if maximum <= minimum:
        raise ValueError("maximum must be greater than minimum")
    value = max(minimum, min(maximum, temperature))
    ratio = (value - minimum) / (maximum - minimum)
    return max(0, min(segment_count, round(ratio * segment_count)))


def visualizer_row_color(
    row_index: int,
    row_count: int,
) -> tuple[float, float, float, float]:
    """Blend solid racing red at the baseline into white at full height."""

    if row_count <= 1:
        raise ValueError("row_count must be greater than one")
    row = max(0, min(row_count - 1, row_index))
    ratio = row / (row_count - 1)
    # Keep the lower third strongly red before opening into coral and white.
    blend = ratio**1.35
    red = (1.0, 0.025, 0.045)
    return (
        1.0,
        red[1] + (1.0 - red[1]) * blend,
        red[2] + (1.0 - red[2]) * blend,
        1.0,
    )

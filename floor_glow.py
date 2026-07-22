#!/usr/bin/env python3
"""Texture and tracking helpers for the Civic floor reflection."""

import csv
from dataclasses import dataclass
from math import pow
from pathlib import Path


@dataclass(frozen=True)
class FloorGlowGeometry:
    """Glow placement in the source frame's top-left pixel coordinates."""

    center_x: float
    center_y: float
    width: float
    height: float


def read_floor_glow_tracking(
    tracking_path: Path,
) -> dict[str, FloorGlowGeometry]:
    """Load frame-locked glow geometry keyed by PNG filename."""

    with tracking_path.open(encoding="utf-8", newline="") as tracking_file:
        rows = csv.DictReader(tracking_file, delimiter="\t")
        return {
            row["frame"]: FloorGlowGeometry(
                center_x=float(row["center_x"]),
                center_y=float(row["center_y"]),
                width=float(row["width"]),
                height=float(row["height"]),
            )
            for row in rows
        }


def build_floor_glow_rgba(
    width: int = 256,
    height: int = 64,
    maximum_alpha: int = 205,
) -> bytes:
    """Return a soft red ellipse with fully transparent outer edges.

    The texture is generated in memory at startup.  It contains no line or
    hard-edged shape, so scaling it on the small display produces a pool of
    reflected light rather than a separate animated object.
    """

    if width < 3 or height < 3:
        raise ValueError("floor glow texture must be at least 3 by 3 pixels")
    if not 0 <= maximum_alpha <= 255:
        raise ValueError("maximum_alpha must be between 0 and 255")

    center_x = (width - 1) / 2.0
    center_y = (height - 1) * 0.56
    radius_x = center_x
    radius_y_below = center_y
    radius_y_above = (height - 1) - center_y
    pixels = bytearray(width * height * 4)

    offset = 0
    for y in range(height):
        radius_y = radius_y_below if y <= center_y else radius_y_above
        normalized_y = (y - center_y) / max(radius_y, 1.0)

        for x in range(width):
            normalized_x = (x - center_x) / radius_x
            radius_squared = (
                normalized_x * normalized_x
                + normalized_y * normalized_y
            )

            alpha = 0
            if radius_squared < 1.0:
                # A high-order falloff removes the visible red strip that the
                # previous underglow versions produced.
                falloff = pow(1.0 - radius_squared, 2.35)
                alpha = round(maximum_alpha * falloff)

            pixels[offset : offset + 4] = (255, 8, 18, alpha)
            offset += 4

    return bytes(pixels)

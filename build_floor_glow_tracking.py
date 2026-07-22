#!/usr/bin/env python3
"""Derive smooth, frame-locked floor-glow anchors from Civic silhouettes."""

import argparse
import csv
import re
from pathlib import Path

import numpy as np
from PIL import Image


EXPECTED_FRAME_COUNT = 220
ALPHA_THRESHOLD = 24
SMOOTH_RADIUS = 4
GLOW_WIDTH_FROM_CAR = 0.58
MINIMUM_GLOW_WIDTH = 150.0
GLOW_HEIGHT_FROM_WIDTH = 0.11
MINIMUM_GLOW_HEIGHT = 30.0
CONTACT_OFFSET = 5.0

PROJECT = Path(__file__).resolve().parent
DEFAULT_FRAMES = PROJECT / "assets" / "civic_frames_outline"
DEFAULT_OUTPUT = DEFAULT_FRAMES / "floor_glow_tracking.tsv"


def natural_key(path: Path) -> list[object]:
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


def circular_smooth(values: list[float], radius: int) -> list[float]:
    """Smooth a complete 360-degree loop without a seam at frame zero."""

    data = np.asarray(values, dtype=np.float64)
    if data.size == 0 or radius <= 0:
        return data.tolist()
    weights = np.hanning(radius * 2 + 3)[1:-1]
    weights /= weights.sum()
    offsets = range(-radius, radius + 1)
    return [
        float(
            sum(
                data[(index + offset) % data.size] * weight
                for offset, weight in zip(offsets, weights)
            )
        )
        for index in range(data.size)
    ]


def frame_bounds(frame_path: Path) -> tuple[int, int, int, int]:
    """Return the visible Civic bounds, ignoring near-transparent noise."""

    with Image.open(frame_path) as image:
        alpha = np.asarray(image.convert("RGBA"))[..., 3]
    y_coordinates, x_coordinates = np.nonzero(alpha >= ALPHA_THRESHOLD)
    if not x_coordinates.size:
        raise RuntimeError(f"No Civic pixels detected: {frame_path}")
    return (
        int(x_coordinates.min()),
        int(y_coordinates.min()),
        int(x_coordinates.max()) + 1,
        int(y_coordinates.max()) + 1,
    )


def build_tracking_rows(frame_paths: list[Path]) -> list[dict[str, object]]:
    """Build one smooth glow anchor for every ordered Civic frame."""

    if len(frame_paths) != EXPECTED_FRAME_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_FRAME_COUNT} frames; found {len(frame_paths)}"
        )

    raw_centers = []
    raw_widths = []
    raw_bottoms = []
    for frame_path in frame_paths:
        left, _top, right, bottom = frame_bounds(frame_path)
        raw_centers.append((left + right) / 2.0)
        raw_widths.append(float(right - left))
        raw_bottoms.append(float(bottom))

    centers = circular_smooth(raw_centers, SMOOTH_RADIUS)
    car_widths = circular_smooth(raw_widths, SMOOTH_RADIUS)
    bottoms = circular_smooth(raw_bottoms, SMOOTH_RADIUS)

    rows = []
    for frame_path, center_x, car_width, bottom in zip(
        frame_paths,
        centers,
        car_widths,
        bottoms,
    ):
        glow_width = max(
            MINIMUM_GLOW_WIDTH,
            car_width * GLOW_WIDTH_FROM_CAR,
        )
        glow_height = max(
            MINIMUM_GLOW_HEIGHT,
            glow_width * GLOW_HEIGHT_FROM_WIDTH,
        )
        rows.append(
            {
                "frame": frame_path.name,
                "center_x": center_x,
                "center_y": bottom + CONTACT_OFFSET,
                "width": glow_width,
                "height": glow_height,
            }
        )
    return rows


def write_tracking(rows: list[dict[str, object]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=("frame", "center_x", "center_y", "width", "height"),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "frame": row["frame"],
                    "center_x": f"{float(row['center_x']):.3f}",
                    "center_y": f"{float(row['center_y']):.3f}",
                    "width": f"{float(row['width']):.3f}",
                    "height": f"{float(row['height']):.3f}",
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=Path, default=DEFAULT_FRAMES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()

    frame_paths = sorted(
        arguments.frames.glob("frame_*.png"),
        key=natural_key,
    )
    rows = build_tracking_rows(frame_paths)
    write_tracking(rows, arguments.output)
    print(f"Wrote {len(rows)} glow anchors to {arguments.output}")


if __name__ == "__main__":
    main()

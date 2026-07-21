#!/usr/bin/env python3
"""Bake a hidden, frame-locked red underbody glow into Civic PNGs."""

import argparse
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps


EXPECTED_FRAME_COUNT = 220
ALPHA_THRESHOLD = 24
GLOW_WIDTH_RATIO = 0.74
GLOW_HEIGHT_RATIO = 0.10
SOURCE_INSET_RATIO = 0.055
MIN_SEQUENCE_WIDTH_RATIO = 0.36
MAX_SEQUENCE_WIDTH_RATIO = 0.70
GEOMETRY_SMOOTH_RADIUS = 7
PIVOT_CORRECTION_ITERATIONS = 12
MAX_SOURCE_SHIFT_RATIO = 0.24
SOURCE_OPACITY = 255
BROAD_BLUR = 11.0
MEDIUM_BLUR = 5.0
BROAD_OPACITY = 1.0
MEDIUM_OPACITY = 0.95
CONTACT_FADE_PIXELS = 6
GLOW_COLOR = (255, 0, 18)

PROJECT = Path(__file__).resolve().parent
DEFAULT_SOURCE = PROJECT / "assets" / "civic_frames_outline"
DEFAULT_OUTPUT = PROJECT / "assets" / "civic_frames_bottom_glow"


def natural_key(path: Path) -> list[object]:
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


def hidden_glow_source(
    frame: Image.Image,
    geometry: tuple[float, float, float, float] | None = None,
) -> Image.Image:
    """Place a wide light source just inside the car's lower silhouette."""

    box = frame.getchannel("A").getbbox()
    if box is None:
        raise RuntimeError("No Civic pixels detected")
    left, top, right, bottom = box
    car_width = right - left
    car_height = bottom - top
    if geometry is None:
        center_x = frame.width / 2.0
        center_y = bottom - car_height * SOURCE_INSET_RATIO
        glow_width = car_width * GLOW_WIDTH_RATIO
        glow_height = max(8.0, car_height * GLOW_HEIGHT_RATIO)
    else:
        center_x, center_y, glow_width, glow_height = geometry

    source = Image.new("L", frame.size, 0)
    ImageDraw.Draw(source).ellipse(
        (
            center_x - glow_width / 2.0,
            center_y - glow_height / 2.0,
            center_x + glow_width / 2.0,
            center_y + glow_height / 2.0,
        ),
        fill=SOURCE_OPACITY,
    )
    return source


def solid_silhouette_and_bottoms(
    frame: Image.Image,
) -> tuple[Image.Image, dict[int, int]]:
    """Fill the car per column and retain its bottom edge for contact fading."""

    alpha = np.asarray(frame.getchannel("A"))
    _height, width = alpha.shape
    silhouette = Image.new("L", frame.size, 0)
    draw = ImageDraw.Draw(silhouette)
    bottoms = {}
    for x in range(width):
        visible_y = np.flatnonzero(alpha[:, x] >= ALPHA_THRESHOLD)
        if not visible_y.size:
            continue
        top = int(visible_y[0])
        bottom = int(visible_y[-1])
        draw.line((x, top, x, bottom), fill=255, width=1)
        bottoms[x] = bottom
    return silhouette, bottoms


def scaled_mask(mask: Image.Image, factor: float) -> Image.Image:
    return mask.point(lambda pixel: round(pixel * factor))


def circular_smooth(values: list[float], radius: int) -> list[float]:
    """Smooth a complete rotation without introducing a seam at frame zero."""

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


def sequence_glow_geometry(
    frame_paths: list[Path],
) -> list[tuple[float, float, float, float]]:
    """Build one stable turntable-centered footprint for every frame."""

    sizes = []
    raw_center_y = []
    car_heights = []
    for frame_path in frame_paths:
        with Image.open(frame_path) as frame:
            width, height = frame.size
            box = frame.convert("RGBA").getchannel("A").getbbox()
        if box is None:
            raise RuntimeError(f"No Civic pixels detected: {frame_path}")
        left, top, right, bottom = box
        sizes.append((width, height))
        car_height = bottom - top
        car_heights.append(car_height)
        raw_center_y.append(bottom - car_height * SOURCE_INSET_RATIO)

    if len(set(sizes)) != 1:
        raise RuntimeError("All Civic frames must share one canvas size")

    canvas_width, _canvas_height = sizes[0]
    center_x = canvas_width / 2.0
    center_y_values = circular_smooth(raw_center_y, GEOMETRY_SMOOTH_RADIUS)
    glow_height = max(8.0, float(np.median(car_heights)) * GLOW_HEIGHT_RATIO)
    minimum_width = canvas_width * MIN_SEQUENCE_WIDTH_RATIO
    maximum_width = canvas_width * MAX_SEQUENCE_WIDTH_RATIO

    result = []
    frame_count = len(frame_paths)
    for index, center_y in enumerate(center_y_values):
        # Frame zero is the rear view, a side view occurs one quarter-turn
        # later, and the front appears at half a turn. This analytic footprint
        # changes width continuously while its turntable pivot never wanders.
        phase = 2.0 * np.pi * index / frame_count
        projected_length = minimum_width * float(np.cos(phase))
        projected_side = maximum_width * float(np.sin(phase))
        glow_width = float(np.hypot(projected_length, projected_side))
        result.append((center_x, center_y, glow_width, glow_height))

    # The solid car mask can hide more of one half of the bloom at oblique
    # angles. Correct the hidden source position until the *visible* reflected
    # light remains centered on the fixed turntable pivot. This eliminates the
    # apparent sideways slide without adding a second animation layer.
    stabilized = []
    for frame_path, geometry in zip(frame_paths, result):
        with Image.open(frame_path) as frame:
            frame.load()
            rgba = frame.convert("RGBA")
        stabilized.append(
            stabilize_visible_pivot(rgba, geometry, target_x=center_x)
        )
    return stabilized


def visible_glow_center_x(
    frame: Image.Image,
    geometry: tuple[float, float, float, float],
) -> float:
    glow_alpha = np.asarray(glow_alpha_for_geometry(frame, geometry)).copy()
    glow_alpha[np.asarray(frame.getchannel("A")) > 0] = 0
    column_weights = glow_alpha.sum(axis=0, dtype=np.float64)
    total = float(column_weights.sum())
    if total <= 0:
        return geometry[0]
    x_coordinates = np.arange(frame.width, dtype=np.float64)
    return float(np.dot(column_weights, x_coordinates) / total)


def stabilize_visible_pivot(
    frame: Image.Image,
    geometry: tuple[float, float, float, float],
    target_x: float,
) -> tuple[float, float, float, float]:
    _source_x, center_y, glow_width, glow_height = geometry
    maximum_shift = glow_width * MAX_SOURCE_SHIFT_RATIO
    lower_x = target_x - maximum_shift
    upper_x = target_x + maximum_shift
    lower_geometry = (lower_x, center_y, glow_width, glow_height)
    upper_geometry = (upper_x, center_y, glow_width, glow_height)
    lower_center = visible_glow_center_x(frame, lower_geometry)
    upper_center = visible_glow_center_x(frame, upper_geometry)
    if target_x <= lower_center:
        return lower_geometry
    if target_x >= upper_center:
        return upper_geometry

    for _iteration in range(PIVOT_CORRECTION_ITERATIONS):
        source_x = (lower_x + upper_x) / 2.0
        candidate = (source_x, center_y, glow_width, glow_height)
        visible_center = visible_glow_center_x(frame, candidate)
        if visible_center < target_x:
            lower_x = source_x
        else:
            upper_x = source_x
    source_x = (lower_x + upper_x) / 2.0
    return (source_x, center_y, glow_width, glow_height)


def glow_alpha_for_geometry(
    rgba: Image.Image,
    geometry: tuple[float, float, float, float] | None,
) -> Image.Image:
    """Return only the masked, contact-faded underglow opacity."""

    source = hidden_glow_source(rgba, geometry)
    broad = scaled_mask(
        source.filter(ImageFilter.GaussianBlur(BROAD_BLUR)),
        BROAD_OPACITY,
    )
    medium = scaled_mask(
        source.filter(ImageFilter.GaussianBlur(MEDIUM_BLUR)),
        MEDIUM_OPACITY,
    )
    glow_alpha = ImageChops.lighter(broad, medium)

    # Hide the light source inside a filled per-column car silhouette. Only its
    # downward reflection can escape below the frame's real lower body edge.
    silhouette, bottoms = solid_silhouette_and_bottoms(rgba)
    glow_alpha = ImageChops.multiply(
        glow_alpha,
        ImageOps.invert(silhouette),
    )

    # Fade up from zero immediately below the car. This removes the visible
    # red contact line while keeping a stronger bloom farther down.
    glow_array = np.asarray(glow_alpha, dtype=np.float32).copy()
    height = glow_array.shape[0]
    for x, bottom in bottoms.items():
        start = min(height, bottom + 1)
        stop = min(height, start + CONTACT_FADE_PIXELS)
        if start >= stop:
            continue
        glow_array[start:stop, x] *= np.linspace(
            0.0,
            1.0,
            stop - start,
            endpoint=False,
        )
    glow_alpha = Image.fromarray(
        np.clip(glow_array, 0, 255).astype(np.uint8),
        "L",
    )
    return glow_alpha


def add_bottom_glow(
    frame: Image.Image,
    geometry: tuple[float, float, float, float] | None = None,
) -> Image.Image:
    """Composite a line-free downward glow behind the unchanged Civic."""

    rgba = frame.convert("RGBA")
    glow_alpha = glow_alpha_for_geometry(rgba, geometry)

    glow = Image.new("RGBA", rgba.size, (*GLOW_COLOR, 0))
    glow.putalpha(glow_alpha)
    result = np.asarray(Image.alpha_composite(glow, rgba)).copy()
    original = np.asarray(rgba)
    civic_pixels = original[..., 3] > 0
    result[civic_pixels] = original[civic_pixels]
    return Image.fromarray(result, "RGBA")


def read_frames(source: Path) -> list[Path]:
    return sorted(source.glob("frame_*.png"), key=natural_key)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    frames = read_frames(args.source)
    if len(frames) != EXPECTED_FRAME_COUNT:
        raise SystemExit(
            f"Expected {EXPECTED_FRAME_COUNT} source frames, found {len(frames)}"
        )
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"Output folder is not empty: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)

    geometry = sequence_glow_geometry(frames)
    order = []
    geometry_rows = ["frame\tcenter_x\tcenter_y\twidth\theight"]
    for index, source_path in enumerate(frames):
        with Image.open(source_path) as source:
            source.load()
            result = add_bottom_glow(source, geometry[index])
        destination = args.output / f"frame_{index:04d}.png"
        result.save(destination, "PNG", optimize=False, compress_level=6)
        order.append(f"{destination.name}\t{source_path.name}")
        center_x, center_y, glow_width, glow_height = geometry[index]
        geometry_rows.append(
            f"{destination.name}\t{center_x:.3f}\t{center_y:.3f}\t"
            f"{glow_width:.3f}\t{glow_height:.3f}"
        )
        if index == 0 or (index + 1) % 20 == 0 or index + 1 == len(frames):
            print(f"[{index + 1:03d}/{len(frames):03d}] {destination.name}")

    (args.output / "frame_order.txt").write_text(
        "\n".join(order) + "\n",
        encoding="utf-8",
    )
    (args.output / "glow_geometry.tsv").write_text(
        "\n".join(geometry_rows) + "\n",
        encoding="utf-8",
    )
    print(f"Created {len(frames)} frame-locked bottom-glow images.")


if __name__ == "__main__":
    main()

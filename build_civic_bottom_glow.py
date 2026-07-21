#!/usr/bin/env python3
"""Bake a frame-locked red bottom-edge glow into approved Civic PNGs."""

import argparse
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps


EXPECTED_FRAME_COUNT = 220
ALPHA_THRESHOLD = 32
EDGE_OFFSET = 1
MAX_VERTICAL_STEP = 9
CORE_WIDTH = 2
BROAD_BLUR = 7.0
MEDIUM_BLUR = 3.0
BROAD_OPACITY = 0.65
MEDIUM_OPACITY = 0.82
GLOW_COLOR = (255, 0, 18)

PROJECT = Path(__file__).resolve().parent
DEFAULT_SOURCE = PROJECT / "assets" / "civic_frames_outline"
DEFAULT_OUTPUT = PROJECT / "assets" / "civic_frames_bottom_glow"


def natural_key(path: Path) -> list[object]:
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


def bottom_edge_mask(frame: Image.Image) -> Image.Image:
    """Trace the actual lowest visible Civic pixel in each image column."""

    alpha = np.asarray(frame.getchannel("A"))
    height, width = alpha.shape
    box = frame.getchannel("A").getbbox()
    if box is None:
        raise RuntimeError("No Civic pixels detected")
    _left, top, _right, bottom = box
    minimum_bottom_y = top + (bottom - top) * 0.55
    points = []
    for x in range(width):
        visible_y = np.flatnonzero(alpha[:, x] >= ALPHA_THRESHOLD)
        if visible_y.size and visible_y[-1] >= minimum_bottom_y:
            points.append(
                (
                    x,
                    min(height - 1, int(visible_y[-1]) + EDGE_OFFSET),
                )
            )

    edge = Image.new("L", frame.size, 0)
    draw = ImageDraw.Draw(edge)
    segment = []
    for point in points:
        discontinuity = segment and (
            point[0] != segment[-1][0] + 1
            or abs(point[1] - segment[-1][1]) > MAX_VERTICAL_STEP
        )
        if discontinuity:
            if len(segment) > 1:
                draw.line(segment, fill=255, width=CORE_WIDTH)
            segment = []
        segment.append(point)
    if len(segment) > 1:
        draw.line(segment, fill=255, width=CORE_WIDTH)
    return edge


def scaled_mask(mask: Image.Image, factor: float) -> Image.Image:
    return mask.point(lambda pixel: round(pixel * factor))


def add_bottom_glow(frame: Image.Image) -> Image.Image:
    """Composite glow behind the car while preserving its white pixels."""

    rgba = frame.convert("RGBA")
    edge = bottom_edge_mask(rgba)
    broad = scaled_mask(
        edge.filter(ImageFilter.GaussianBlur(BROAD_BLUR)),
        BROAD_OPACITY,
    )
    medium = scaled_mask(
        edge.filter(ImageFilter.GaussianBlur(MEDIUM_BLUR)),
        MEDIUM_OPACITY,
    )
    glow_alpha = ImageChops.lighter(broad, medium)

    # Never tint the approved white Civic line work. The red pixels only occupy
    # transparent space immediately outside its real per-frame bottom edge.
    civic_guard = rgba.getchannel("A").point(
        lambda pixel: 255 if pixel > 0 else 0
    )
    glow_alpha = ImageChops.multiply(
        glow_alpha,
        ImageOps.invert(civic_guard),
    )

    glow = Image.new("RGBA", rgba.size, (*GLOW_COLOR, 0))
    glow.putalpha(glow_alpha)
    return Image.alpha_composite(glow, rgba)


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

    order = []
    for index, source_path in enumerate(frames):
        with Image.open(source_path) as source:
            source.load()
            result = add_bottom_glow(source)
        destination = args.output / f"frame_{index:04d}.png"
        result.save(destination, "PNG", optimize=False, compress_level=6)
        order.append(f"{destination.name}\t{source_path.name}")
        if index == 0 or (index + 1) % 20 == 0 or index + 1 == len(frames):
            print(f"[{index + 1:03d}/{len(frames):03d}] {destination.name}")

    (args.output / "frame_order.txt").write_text(
        "\n".join(order) + "\n",
        encoding="utf-8",
    )
    print(f"Created {len(frames)} frame-locked bottom-glow images.")


if __name__ == "__main__":
    main()

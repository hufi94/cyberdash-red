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


def hidden_glow_source(frame: Image.Image) -> Image.Image:
    """Place a wide light source just inside the car's lower silhouette."""

    box = frame.getchannel("A").getbbox()
    if box is None:
        raise RuntimeError("No Civic pixels detected")
    left, top, right, bottom = box
    car_width = right - left
    car_height = bottom - top
    center_x = (left + right) / 2.0
    center_y = bottom - car_height * SOURCE_INSET_RATIO
    glow_width = car_width * GLOW_WIDTH_RATIO
    glow_height = max(8.0, car_height * GLOW_HEIGHT_RATIO)

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


def add_bottom_glow(frame: Image.Image) -> Image.Image:
    """Composite a line-free downward glow behind the unchanged Civic."""

    rgba = frame.convert("RGBA")
    source = hidden_glow_source(rgba)
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

#!/usr/bin/env python3
"""Build the approved no-red Civic sequence with 70% white lamp fills."""

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from convert_civic_outline import (
    make_object_mask,
    make_outline,
    read_frames,
)


EXPECTED_FRAME_COUNT = 220
# Use conventional half-up rounding: 70% of 255 is 178.5, stored as 179.
LAMP_OPACITY = 179


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def headlight_fade(index: int) -> float:
    """Fade early and late around the complete front-facing half-turn."""

    if 25 <= index < 75:
        return smoothstep((index - 25) / 50.0)
    if 75 <= index <= 135:
        return 1.0
    if 135 < index < 185:
        return smoothstep((185 - index) / 50.0)
    return 0.0


def tail_light_fade(index: int) -> float:
    """Use the identical fade curve exactly one half-rotation later."""

    return headlight_fade((index + EXPECTED_FRAME_COUNT // 2) % EXPECTED_FRAME_COUNT)


def ellipse_mask(
    size: tuple[int, int],
    center_x: float,
    center_y: float,
    radius_x: float,
    radius_y: float,
) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse(
        (
            center_x - radius_x,
            center_y - radius_y,
            center_x + radius_x,
            center_y + radius_y,
        ),
        fill=255,
    )
    return mask


def projected_lamp_searches(
    box: tuple[int, int, int, int],
    index: int,
    front: bool,
    size: tuple[int, int],
) -> list[Image.Image]:
    """Create generous searches around the rendered front or rear housings."""

    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    center_x = (left + right) / 2.0
    angle = 2.0 * math.pi * index / EXPECTED_FRAME_COUNT
    sine = math.sin(angle)
    cosine = math.cos(angle)
    longitudinal = 1.0 if front else -1.0
    length_half = width * 0.43
    front_visibility = (1.0 - cosine) / 2.0
    if front:
        # Lamp spacing is tied to the car height because the apparent object
        # width changes dramatically during rotation. Using the full bounding
        # width here makes a three-quarter search drift into the front fender.
        lamp_half = height * (0.36 + 0.05 * front_visibility)
        vertical_fraction = 0.52 + 0.10 * front_visibility
        radius_x = height * (0.10 + 0.04 * front_visibility)
        radius_y = height * (0.07 + 0.035 * front_visibility)
    else:
        rear_visibility = 1.0 - front_visibility
        lamp_half = width * (0.11 + 0.29 * rear_visibility**3)
        vertical_fraction = 0.43 + 0.05 * rear_visibility
        radius_x = width * (0.045 + 0.07 * rear_visibility**2)
        radius_y = height * (0.07 + 0.09 * rear_visibility)
    center_y = top + height * vertical_fraction

    searches = []
    for lateral in (-1.0, 1.0):
        projected_x = (
            center_x
            - longitudinal * sine * length_half
            + lateral * cosine * lamp_half
        )
        searches.append(
            ellipse_mask(size, projected_x, center_y, radius_x, radius_y)
        )
    return searches


def close_mask(mask: Image.Image, grow: int, shrink: int) -> Image.Image:
    if grow > 1:
        mask = mask.filter(ImageFilter.MaxFilter(grow))
    if shrink > 1:
        mask = mask.filter(ImageFilter.MinFilter(shrink))
    return mask


def headlight_mask(
    source: Image.Image,
    object_mask: Image.Image,
    box: tuple[int, int, int, int],
    index: int,
) -> Image.Image:
    rgb = np.asarray(source.convert("RGB"), dtype=np.int16)
    alpha = np.asarray(object_mask) > 0
    maximum = rgb.max(axis=2)
    minimum = rgb.min(axis=2)
    luminance = (
        rgb[..., 0] * 30 + rgb[..., 1] * 59 + rgb[..., 2] * 11
    ) // 100
    # The rendered lens reflector is almost perfectly neutral grey, while the
    # silver paint has a visible blue channel bias. Use that material identity
    # as the tracking anchor so a projected search can never become the lamp.
    # This keeps the fill attached to real housing pixels frame by frame.
    neutral_lens_core = (
        alpha
        & (maximum - minimum <= 3)
        & (luminance >= 88)
        & (luminance <= 166)
    )
    housing_guard = (
        alpha
        & (maximum - minimum <= 14)
        & (luminance >= 68)
        & (luminance <= 182)
    )
    evidence = Image.fromarray(neutral_lens_core.astype(np.uint8) * 255, "L")
    guard = Image.fromarray(housing_guard.astype(np.uint8) * 255, "L")
    guard = close_mask(guard, 3, 3)

    result = Image.new("L", source.size, 0)
    for search in projected_lamp_searches(box, index, True, source.size):
        candidate = ImageChops.multiply(evidence, search)
        candidate = close_mask(candidate, 9, 7)
        candidate = ImageChops.multiply(candidate, guard)
        result = ImageChops.lighter(result, candidate)
    return result


def tail_light_mask(
    source: Image.Image,
    object_mask: Image.Image,
    box: tuple[int, int, int, int],
    index: int,
) -> Image.Image:
    rgb = np.asarray(source.convert("RGB"), dtype=np.int16)
    alpha = np.asarray(object_mask) > 0
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    coloured_lamp = (
        alpha
        & (red >= 95)
        & (red >= green + 24)
        & (red >= blue + 28)
    )
    evidence = Image.fromarray(coloured_lamp.astype(np.uint8) * 255, "L")

    result = Image.new("L", source.size, 0)
    for search in projected_lamp_searches(box, index, False, source.size):
        candidate = ImageChops.multiply(evidence, search)
        candidate = close_mask(candidate, 7, 7)
        candidate = ImageChops.multiply(candidate, evidence)
        result = ImageChops.lighter(result, candidate)
    return result


def common_object_crop(
    frame_paths: list[Path],
    background_threshold: int,
    alpha_threshold: int,
    padding: int,
) -> tuple[int, int, int, int]:
    """Find one shared crop so the car never jumps between animation frames."""

    union_box = None
    canvas_size = None
    for frame_path in frame_paths:
        with Image.open(frame_path) as source:
            rgba = ImageOps.exif_transpose(source).convert("RGBA")
            canvas_size = rgba.size
            box = make_object_mask(
                rgba,
                background_threshold,
                alpha_threshold,
            ).getbbox()
        if box is None:
            continue
        if union_box is None:
            union_box = box
        else:
            union_box = (
                min(union_box[0], box[0]),
                min(union_box[1], box[1]),
                max(union_box[2], box[2]),
                max(union_box[3], box[3]),
            )

    if union_box is None or canvas_size is None:
        raise RuntimeError("No Civic pixels detected in the source sequence")
    width, height = canvas_size
    return (
        max(0, union_box[0] - padding),
        max(0, union_box[1] - padding),
        min(width, union_box[2] + padding),
        min(height, union_box[3] + padding),
    )


def grayscale_white_artwork(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    white = Image.new("RGBA", image.size, (248, 248, 248, 0))
    white.putalpha(alpha)
    return white


def build_frame(
    source: Image.Image,
    index: int,
    outline_args: argparse.Namespace,
) -> tuple[Image.Image, Image.Image, Image.Image]:
    rgba = ImageOps.exif_transpose(source).convert("RGBA")
    object_mask = make_object_mask(
        rgba,
        outline_args.background_threshold,
        outline_args.alpha_threshold,
    )
    box = object_mask.getbbox()
    if box is None:
        raise RuntimeError("No Civic pixels detected")

    outline = grayscale_white_artwork(make_outline(rgba, outline_args))
    head_mask = headlight_mask(rgba, object_mask, box, index)
    tail_mask = tail_light_mask(rgba, object_mask, box, index)

    head_alpha = head_mask.point(
        lambda pixel: round(pixel * LAMP_OPACITY * headlight_fade(index) / 255)
    )
    tail_alpha = tail_mask.point(
        lambda pixel: round(pixel * LAMP_OPACITY * tail_light_fade(index) / 255)
    )
    lamp_alpha = ImageChops.lighter(head_alpha, tail_alpha)
    lamp_layer = Image.new("RGBA", rgba.size, (248, 248, 248, 0))
    lamp_layer.putalpha(lamp_alpha)

    # Lamp fill sits under the original white detail edges. Internal lens and
    # grille details therefore remain visible instead of becoming flat blobs.
    result = Image.alpha_composite(lamp_layer, outline)
    return result, head_alpha, tail_alpha


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--line-thickness", type=int, default=1)
    parser.add_argument("--edge-threshold", type=int, default=18)
    parser.add_argument("--background-threshold", type=int, default=24)
    parser.add_argument("--alpha-threshold", type=int, default=8)
    parser.add_argument(
        "--crop-padding",
        type=int,
        default=16,
        help="Shared transparent padding around the complete rotation",
    )
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

    outline_args = argparse.Namespace(
        line_thickness=args.line_thickness,
        edge_threshold=args.edge_threshold,
        background_threshold=args.background_threshold,
        alpha_threshold=args.alpha_threshold,
        underglow="off",
        glow_opacity=0,
        glow_blur=0.0,
    )
    crop_box = common_object_crop(
        frames,
        args.background_threshold,
        args.alpha_threshold,
        max(0, args.crop_padding),
    )

    order = []
    tracking = ["frame\tsource\theadlight_fade\ttaillight_fade\theadlight_pixels\ttaillight_pixels"]
    previews = []
    preview_indexes = {0, 20, 40, 55, 75, 90, 110, 135, 165, 185, 200, 219}
    for index, source_path in enumerate(frames):
        with Image.open(source_path) as source:
            source.load()
            result, head_alpha, tail_alpha = build_frame(
                source,
                index,
                outline_args,
            )
        result = result.crop(crop_box)
        destination = args.output / f"frame_{index:04d}.png"
        result.save(destination, "PNG", optimize=False, compress_level=6)
        order.append(f"{destination.name}\t{source_path.name}")
        tracking.append(
            f"{destination.name}\t{source_path.name}\t"
            f"{headlight_fade(index):.4f}\t{tail_light_fade(index):.4f}\t"
            f"{int(np.count_nonzero(np.asarray(head_alpha)))}\t"
            f"{int(np.count_nonzero(np.asarray(tail_alpha)))}"
        )
        if index in preview_indexes:
            previews.append((index, result.copy()))
        if index == 0 or (index + 1) % 10 == 0 or index + 1 == len(frames):
            print(f"[{index + 1:03d}/{len(frames):03d}] {source_path.name}")

    (args.output / "frame_order.txt").write_text(
        "\n".join(order) + "\n",
        encoding="utf-8",
    )
    (args.output / "lamp_tracking.tsv").write_text(
        "\n".join(tracking) + "\n",
        encoding="utf-8",
    )
    if args.preview:
        cell_width, cell_height, columns = 427, 270, 3
        rows = math.ceil(len(previews) / columns)
        sheet = Image.new(
            "RGB",
            (cell_width * columns, cell_height * rows),
            (5, 6, 9),
        )
        draw = ImageDraw.Draw(sheet)
        for position, (index, frame) in enumerate(previews):
            height = round(frame.height * cell_width / frame.width)
            resized = frame.resize(
                (cell_width, height),
                Image.Resampling.LANCZOS,
            )
            dark = Image.new("RGBA", resized.size, (5, 6, 9, 255))
            dark.alpha_composite(resized)
            row, column = divmod(position, columns)
            x, y = column * cell_width, row * cell_height
            sheet.paste(dark.convert("RGB"), (x, y))
            draw.text((x + 10, y + 10), f"frame_{index:04d}", fill=(180, 185, 195))
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(args.preview, "PNG", compress_level=6)

    print(f"Created {len(frames)} approved no-red frames in {args.output}")


if __name__ == "__main__":
    main()

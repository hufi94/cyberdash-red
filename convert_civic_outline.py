#!/usr/bin/env python3
"""Convert rotating car renders into transparent white etch frames."""

import argparse
import re
from pathlib import Path

from PIL import (
    Image,
    ImageChops,
    ImageDraw,
    ImageFilter,
    ImageOps,
    ImageStat,
)


PROJECT = Path(__file__).resolve().parent
DEFAULT_SOURCE = PROJECT / "assets" / "civic_frames"
DEFAULT_OUTPUT = PROJECT / "assets" / "civic_frames_outline"
DEFAULT_PREVIEW = PROJECT / "assets" / "civic_outline_preview.png"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def natural_key(path: Path) -> list[object]:
    """Return a key that sorts frame_2 before frame_10."""

    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


def threshold(image: Image.Image, value: int) -> Image.Image:
    """Convert an 8-bit image into a binary mask."""

    return image.point(lambda pixel: 255 if pixel >= value else 0)


def estimate_background(rgb: Image.Image) -> tuple[int, int, int]:
    """Estimate a flat opaque background colour from all four corners."""

    width, height = rgb.size
    sample_size = max(2, min(width, height) // 40)
    boxes = (
        (0, 0, sample_size, sample_size),
        (width - sample_size, 0, width, sample_size),
        (0, height - sample_size, sample_size, height),
        (
            width - sample_size,
            height - sample_size,
            width,
            height,
        ),
    )
    corner_means = [ImageStat.Stat(rgb.crop(box)).mean for box in boxes]

    return tuple(
        round(
            sum(mean[channel] for mean in corner_means)
            / len(corner_means)
        )
        for channel in range(3)
    )


def make_object_mask(
    rgba: Image.Image,
    background_threshold: int,
    alpha_threshold: int,
) -> Image.Image:
    """Use source transparency, or remove a flat opaque background."""

    alpha = rgba.getchannel("A")
    alpha_min, _alpha_max = alpha.getextrema()

    if alpha_min < 250:
        return threshold(alpha, alpha_threshold)

    rgb = rgba.convert("RGB")
    background = Image.new("RGB", rgb.size, estimate_background(rgb))
    difference = ImageChops.difference(rgb, background)
    red, green, blue = difference.split()
    difference_strength = ImageChops.lighter(
        ImageChops.lighter(red, green),
        blue,
    )
    mask = threshold(difference_strength, background_threshold)
    return mask.filter(ImageFilter.MedianFilter(3))


def make_outline(source_image: Image.Image, args: argparse.Namespace) -> Image.Image:
    """Return one transparent white etch frame with optional red glow."""

    rgba = source_image.convert("RGBA")
    object_mask = make_object_mask(
        rgba,
        background_threshold=args.background_threshold,
        alpha_threshold=args.alpha_threshold,
    )
    bounding_box = object_mask.getbbox()

    if bounding_box is None:
        raise RuntimeError(
            "No car pixels were detected. Lower --background-threshold "
            "or --alpha-threshold."
        )

    grey = ImageOps.grayscale(rgba.convert("RGB"))
    grey = grey.filter(ImageFilter.GaussianBlur(0.65))
    detail_edges = grey.filter(ImageFilter.FIND_EDGES)
    detail_edges = ImageChops.multiply(detail_edges, object_mask)
    detail_edges = threshold(detail_edges, args.edge_threshold)

    expanded_mask = object_mask.filter(ImageFilter.MaxFilter(3))
    contracted_mask = object_mask.filter(ImageFilter.MinFilter(3))
    body_boundary = ImageChops.difference(expanded_mask, contracted_mask)
    edge_mask = ImageChops.lighter(detail_edges, body_boundary)

    if args.line_thickness > 1:
        filter_size = (args.line_thickness * 2) - 1
        edge_mask = edge_mask.filter(ImageFilter.MaxFilter(filter_size))

    edge_mask = edge_mask.filter(ImageFilter.GaussianBlur(0.35))
    result = Image.new("RGBA", rgba.size, (0, 0, 0, 0))

    if args.underglow == "on":
        left, top, right, bottom = bounding_box
        car_width = right - left
        car_height = bottom - top
        glow_width = max(8, round(car_width * 0.78))
        glow_height = max(5, round(car_height * 0.09))
        centre_x = (left + right) // 2
        centre_y = min(
            rgba.height - 1,
            bottom - max(1, round(car_height * 0.015)),
        )

        glow_mask = Image.new("L", rgba.size, 0)
        draw = ImageDraw.Draw(glow_mask)
        draw.ellipse(
            (
                centre_x - glow_width // 2,
                centre_y - glow_height // 2,
                centre_x + glow_width // 2,
                centre_y + glow_height // 2,
            ),
            fill=args.glow_opacity,
        )
        glow_mask = glow_mask.filter(
            ImageFilter.GaussianBlur(args.glow_blur)
        )
        red_glow = Image.new("RGBA", rgba.size, (255, 16, 32, 0))
        red_glow.putalpha(glow_mask)
        result = Image.alpha_composite(result, red_glow)

    white_etch = Image.new("RGBA", rgba.size, (248, 250, 255, 0))
    white_etch.putalpha(edge_mask)
    return Image.alpha_composite(result, white_etch)


def read_frames(source: Path) -> list[Path]:
    """Return supported image files in natural animation order."""

    if not source.exists():
        raise SystemExit(f"Source folder not found: {source}")

    frames = sorted(
        [
            path
            for path in source.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ],
        key=natural_key,
    )

    if not frames:
        raise SystemExit(f"No image frames found in: {source}")

    return frames


def convert_frame(path: Path, args: argparse.Namespace) -> Image.Image:
    """Load and process one source image without modifying it."""

    with Image.open(path) as image:
        image.load()
        image = ImageOps.exif_transpose(image)
        return make_outline(image, args)


def create_preview(frames: list[Path], args: argparse.Namespace) -> None:
    """Create a dark six-angle contact sheet for quick visual tuning."""

    sample_count = min(6, len(frames))
    indexes = (
        [0]
        if sample_count == 1
        else [
            round(index * (len(frames) - 1) / (sample_count - 1))
            for index in range(sample_count)
        ]
    )
    samples = [
        (frames[index], convert_frame(frames[index], args))
        for index in indexes
    ]
    cell_width = max(image.width for _path, image in samples)
    cell_height = max(image.height for _path, image in samples) + 28
    columns = min(3, len(samples))
    rows = (len(samples) + columns - 1) // columns
    sheet = Image.new(
        "RGBA",
        (cell_width * columns, cell_height * rows),
        (7, 7, 11, 255),
    )
    draw = ImageDraw.Draw(sheet)

    for sample_index, (path, image) in enumerate(samples):
        column = sample_index % columns
        row = sample_index // columns
        x = column * cell_width
        y = row * cell_height
        sheet.alpha_composite(image, dest=(x, y))
        draw.text(
            (x + 8, y + image.height + 5),
            path.name,
            fill=(255, 45, 62, 255),
        )

    args.preview.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(args.preview, "PNG", compress_level=5)
    print(f"Preview created: {args.preview}")


def convert_all(frames: list[Path], args: argparse.Namespace) -> None:
    """Convert the complete sequence and write an order map."""

    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(
            f"Output folder is not empty: {args.output}\n"
            "Back it up or rename it, then run this command again."
        )

    args.output.mkdir(parents=True, exist_ok=True)
    frame_map = []

    for index, source_path in enumerate(frames):
        destination = args.output / f"frame_{index:04d}.png"
        converted = convert_frame(source_path, args)
        converted.save(destination, "PNG", optimize=False, compress_level=5)
        frame_map.append(f"{destination.name}\t{source_path.name}")
        print(
            f"[{index + 1:03d}/{len(frames):03d}] "
            f"{source_path.name} -> {destination.name}"
        )

    (args.output / "frame_order.txt").write_text(
        "\n".join(frame_map) + "\n",
        encoding="utf-8",
    )
    print()
    print(f"Created {len(frames)} transparent outline frames.")
    print(f"Output folder: {args.output}")
    print("Animation order map: frame_order.txt")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Convert rotating Civic frames into transparent white etch frames."
        )
    )
    parser.add_argument("mode", choices=("preview", "all"))
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--preview", type=Path, default=DEFAULT_PREVIEW)
    parser.add_argument("--line-thickness", type=int, default=2)
    parser.add_argument("--edge-threshold", type=int, default=28)
    parser.add_argument("--background-threshold", type=int, default=24)
    parser.add_argument("--alpha-threshold", type=int, default=8)
    parser.add_argument("--underglow", choices=("on", "off"), default="on")
    parser.add_argument("--glow-opacity", type=int, default=135)
    parser.add_argument("--glow-blur", type=float, default=12.0)
    return parser


def parse_args() -> argparse.Namespace:
    """Parse and validate command-line settings."""

    parser = build_parser()
    args = parser.parse_args()

    if not 1 <= args.line_thickness <= 6:
        parser.error("--line-thickness must be between 1 and 6")

    for name in (
        "edge_threshold",
        "background_threshold",
        "alpha_threshold",
        "glow_opacity",
    ):
        if not 0 <= getattr(args, name) <= 255:
            parser.error(
                f"--{name.replace('_', '-')} must be between 0 and 255"
            )

    if args.glow_blur < 0:
        parser.error("--glow-blur cannot be negative")

    return args


def main() -> None:
    """Run preview or full conversion mode."""

    args = parse_args()
    frames = read_frames(args.source)
    print(f"Found {len(frames)} source frames in natural animation order.")

    if args.mode == "preview":
        create_preview(frames, args)
    else:
        convert_all(frames, args)


if __name__ == "__main__":
    main()

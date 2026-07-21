import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw

from build_civic_bottom_glow import add_bottom_glow
from build_approved_civic_frames import (
    EXPECTED_FRAME_COUNT,
    LAMP_OPACITY,
    common_object_crop,
    headlight_fade,
    tail_light_fade,
)


PROJECT = Path(__file__).resolve().parents[1]
FRAMES = PROJECT / "assets" / "civic_frames_outline"
GLOW_FRAMES = PROJECT / "assets" / "civic_frames_bottom_glow"


class ApprovedFrameSetTest(unittest.TestCase):
    def test_complete_ordered_transparent_grayscale_sequence(self):
        frame_paths = sorted(FRAMES.glob("frame_*.png"))
        self.assertEqual(len(frame_paths), EXPECTED_FRAME_COUNT)
        self.assertEqual(
            [path.name for path in frame_paths],
            [f"frame_{index:04d}.png" for index in range(EXPECTED_FRAME_COUNT)],
        )

        expected_size = None
        for frame_path in frame_paths:
            with Image.open(frame_path) as frame:
                self.assertEqual(frame.mode, "RGBA")
                if expected_size is None:
                    expected_size = frame.size
                self.assertEqual(frame.size, expected_size)

                alpha_min, alpha_max = frame.getchannel("A").getextrema()
                self.assertEqual(alpha_min, 0)
                self.assertGreater(alpha_max, 0)

                rgb = frame.convert("RGB")
                red, green, blue = rgb.split()
                self.assertIsNone(ImageChops.difference(red, green).getbbox())
                self.assertIsNone(ImageChops.difference(green, blue).getbbox())

    def test_order_and_tracking_metadata_cover_every_frame(self):
        order_lines = (FRAMES / "frame_order.txt").read_text(
            encoding="utf-8"
        ).splitlines()
        self.assertEqual(len(order_lines), EXPECTED_FRAME_COUNT)
        self.assertTrue(order_lines[0].startswith("frame_0000.png\t"))
        self.assertTrue(order_lines[-1].startswith("frame_0219.png\t"))

        with (FRAMES / "lamp_tracking.tsv").open(
            encoding="utf-8", newline=""
        ) as tracking_file:
            rows = list(csv.DictReader(tracking_file, delimiter="\t"))
        self.assertEqual(len(rows), EXPECTED_FRAME_COUNT)
        self.assertEqual(rows[0]["frame"], "frame_0000.png")
        self.assertEqual(rows[-1]["frame"], "frame_0219.png")

    def test_lamp_fades_are_symmetric_and_limited_to_seventy_percent(self):
        self.assertEqual(LAMP_OPACITY, 179)
        self.assertEqual(headlight_fade(25), 0.0)
        self.assertEqual(headlight_fade(75), 1.0)
        self.assertEqual(headlight_fade(135), 1.0)
        self.assertEqual(headlight_fade(185), 0.0)

        half_turn = EXPECTED_FRAME_COUNT // 2
        for index in range(EXPECTED_FRAME_COUNT):
            self.assertEqual(
                tail_light_fade(index),
                headlight_fade((index + half_turn) % EXPECTED_FRAME_COUNT),
            )

    def test_common_crop_uses_one_union_for_the_complete_rotation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            frame_paths = []
            for index, rectangle in enumerate(
                ((10, 20, 30, 40), (50, 10, 70, 30))
            ):
                frame = Image.new("RGBA", (100, 60), (0, 0, 0, 0))
                ImageDraw.Draw(frame).rectangle(
                    rectangle,
                    fill=(180, 180, 180, 255),
                )
                frame_path = root / f"frame_{index:04d}.png"
                frame.save(frame_path, "PNG")
                frame_paths.append(frame_path)

            self.assertEqual(
                common_object_crop(
                    frame_paths,
                    background_threshold=24,
                    alpha_threshold=8,
                    padding=5,
                ),
                (5, 5, 76, 46),
            )


class BottomGlowFrameSetTest(unittest.TestCase):
    def test_complete_baked_sequence_preserves_car_and_adds_bottom_glow(self):
        source_paths = sorted(FRAMES.glob("frame_*.png"))
        glow_paths = sorted(GLOW_FRAMES.glob("frame_*.png"))
        self.assertEqual(len(glow_paths), EXPECTED_FRAME_COUNT)
        self.assertEqual(
            [path.name for path in glow_paths],
            [path.name for path in source_paths],
        )

        for source_path, glow_path in zip(source_paths, glow_paths):
            with Image.open(source_path) as source_image:
                source = np.asarray(source_image.convert("RGBA"))
            with Image.open(glow_path) as glow_image:
                glow = np.asarray(glow_image.convert("RGBA"))

            self.assertEqual(source.shape, glow.shape)
            civic_pixels = source[..., 3] > 0
            self.assertTrue(np.array_equal(source[civic_pixels], glow[civic_pixels]))

            glow_rgb = glow[..., :3].astype(np.int16)
            red_pixels = (
                (glow[..., 3] > 0)
                & (glow_rgb[..., 0] >= glow_rgb[..., 1] + 24)
                & (glow_rgb[..., 0] >= glow_rgb[..., 2] + 24)
            )
            self.assertGreater(int(np.count_nonzero(red_pixels)), 0)

            alpha_box = Image.fromarray(source[..., 3], "L").getbbox()
            self.assertIsNotNone(alpha_box)
            _left, top, _right, bottom = alpha_box
            first_red_y = int(np.flatnonzero(red_pixels)[0] // red_pixels.shape[1])
            self.assertGreater(first_red_y, top + (bottom - top) * 0.48)

    def test_generator_keeps_original_pixels_exact(self):
        source = Image.new("RGBA", (100, 60), (0, 0, 0, 0))
        ImageDraw.Draw(source).rectangle(
            (20, 10, 80, 49),
            fill=(248, 248, 248, 255),
        )
        result = np.asarray(add_bottom_glow(source))
        original = np.asarray(source)
        civic_pixels = original[..., 3] > 0
        self.assertTrue(np.array_equal(result[civic_pixels], original[civic_pixels]))
        self.assertGreater(int(np.count_nonzero(result[..., 3]) - np.count_nonzero(original[..., 3])), 0)


if __name__ == "__main__":
    unittest.main()

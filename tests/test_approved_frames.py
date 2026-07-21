import csv
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from build_approved_civic_frames import (
    EXPECTED_FRAME_COUNT,
    LAMP_OPACITY,
    circular_smooth_geometry,
    common_object_crop,
    headlight_fade,
    tail_light_fade,
    underglow_geometry,
)


PROJECT = Path(__file__).resolve().parents[1]
FRAMES = PROJECT / "assets" / "civic_frames_outline"


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

        with (FRAMES / "underglow_tracking.tsv").open(
            encoding="utf-8", newline=""
        ) as tracking_file:
            underglow_rows = list(
                csv.DictReader(tracking_file, delimiter="\t")
            )
        self.assertEqual(len(underglow_rows), EXPECTED_FRAME_COUNT)
        self.assertEqual(underglow_rows[0]["frame"], "frame_0000.png")
        self.assertEqual(underglow_rows[-1]["frame"], "frame_0219.png")
        for row in underglow_rows:
            self.assertGreater(float(row["center_x"]), 0.0)
            self.assertLess(float(row["center_x"]), 1.0)
            self.assertGreater(float(row["floor_y"]), 0.0)
            self.assertLessEqual(float(row["floor_y"]), 1.0)
            self.assertGreater(float(row["width"]), 0.0)
            self.assertLess(float(row["width"]), 1.0)

        # The floor effect narrows at end-on views and widens at side views.
        self.assertGreater(
            float(underglow_rows[55]["width"]),
            float(underglow_rows[0]["width"]),
        )
        self.assertGreater(
            float(underglow_rows[165]["width"]),
            float(underglow_rows[110]["width"]),
        )

        raw_geometry = []
        for frame_path in sorted(FRAMES.glob("frame_*.png")):
            with Image.open(frame_path) as frame:
                raw_geometry.append(underglow_geometry(frame.convert("RGBA")))
        expected_geometry = circular_smooth_geometry(raw_geometry)
        for row, expected in zip(underglow_rows, expected_geometry):
            self.assertAlmostEqual(
                float(row["center_x"]), expected[0], delta=0.00000051
            )
            self.assertAlmostEqual(
                float(row["floor_y"]), expected[1], delta=0.00000051
            )
            self.assertAlmostEqual(
                float(row["width"]), expected[2], delta=0.00000051
            )

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

    def test_underglow_geometry_tracks_alpha_bounds_and_smooths_loop(self):
        frame = Image.new("RGBA", (100, 60), (0, 0, 0, 0))
        ImageDraw.Draw(frame).rectangle(
            (20, 10, 80, 49),
            fill=(248, 248, 248, 255),
        )
        center_x, floor_y, width = underglow_geometry(frame)
        self.assertAlmostEqual(center_x, 0.505)
        self.assertAlmostEqual(floor_y, 51 / 60)
        self.assertAlmostEqual(width, 61 * 0.70 / 100)

        geometry = [(0.0, 0.0, 0.0), (3.0, 3.0, 3.0), (6.0, 6.0, 6.0)]
        self.assertEqual(
            circular_smooth_geometry(geometry, radius=1),
            [(3.0, 3.0, 3.0)] * 3,
        )


if __name__ == "__main__":
    unittest.main()

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


PROJECT = Path(__file__).resolve().parents[1]
CONVERTER = PROJECT / "convert_civic_outline.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_car_frame(path: Path, wheel_offset: int) -> None:
    image = Image.new("RGBA", (160, 100), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.polygon(
        [(20, 65), (40, 45), (105, 42), (140, 63), (135, 76), (22, 76)],
        fill=(175, 180, 190, 255),
    )
    draw.line([(42, 46), (60, 65), (108, 65)], fill=(45, 50, 60, 255), width=3)
    draw.ellipse((34 + wheel_offset, 65, 54 + wheel_offset, 85), fill=(30, 30, 34, 255))
    draw.ellipse((108 - wheel_offset, 65, 128 - wheel_offset, 85), fill=(30, 30, 34, 255))
    image.save(path, "PNG")


class ConverterIntegrationTest(unittest.TestCase):
    def test_preview_and_full_conversion_preserve_order_and_source(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            output = root / "output"
            preview = root / "preview.png"
            source.mkdir()

            for name, offset in (
                ("frame_10.png", 2),
                ("frame_2.png", 1),
                ("frame_1.png", 0),
            ):
                create_car_frame(source / name, offset)

            original_digests = {
                path.name: digest(path)
                for path in source.iterdir()
            }

            common_arguments = [
                "--source",
                str(source),
                "--output",
                str(output),
                "--preview",
                str(preview),
                "--line-thickness",
                "2",
                "--edge-threshold",
                "20",
                "--underglow",
                "off",
            ]

            subprocess.run(
                [sys.executable, str(CONVERTER), "preview", *common_arguments],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(preview.is_file())

            subprocess.run(
                [sys.executable, str(CONVERTER), "all", *common_arguments],
                check=True,
                capture_output=True,
                text=True,
            )

            generated = sorted(output.glob("frame_*.png"))
            self.assertEqual(len(generated), 3)
            self.assertEqual(
                (output / "frame_order.txt").read_text(encoding="utf-8").splitlines(),
                [
                    "frame_0000.png\tframe_1.png",
                    "frame_0001.png\tframe_2.png",
                    "frame_0002.png\tframe_10.png",
                ],
            )

            with Image.open(generated[0]) as converted:
                self.assertEqual(converted.mode, "RGBA")
                alpha_min, alpha_max = converted.getchannel("A").getextrema()
                self.assertEqual(alpha_min, 0)
                self.assertGreater(alpha_max, 0)
                raw_pixels = converted.tobytes()
                visible_colours = {
                    tuple(raw_pixels[index : index + 3])
                    for index in range(0, len(raw_pixels), 4)
                    if raw_pixels[index + 3] > 0
                }
                self.assertEqual(visible_colours, {(248, 250, 255)})

            final_digests = {
                path.name: digest(path)
                for path in source.iterdir()
            }
            self.assertEqual(final_digests, original_digests)


if __name__ == "__main__":
    unittest.main()

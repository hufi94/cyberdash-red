import unittest
from pathlib import Path

from PIL import Image


PROJECT = Path(__file__).resolve().parents[1]


class StartupLoaderTests(unittest.TestCase):
    def test_loader_assets_are_small_transparent_png_files(self):
        for name in ("sir_loader_logo.png",):
            with self.subTest(asset=name):
                path = PROJECT / "assets" / "startup" / name
                with Image.open(path) as image:
                    self.assertEqual(image.size, (520, 96))
                    self.assertIn("A", image.convert("RGBA").getbands())
                    alpha = image.convert("RGBA").getchannel("A")
                    self.assertEqual(alpha.getextrema()[0], 0)
                    self.assertGreater(alpha.getextrema()[1], 0)

    def test_loader_waits_for_civic_rotation_and_has_a_safe_timeout(self):
        source = (PROJECT / "startup_loader.py").read_text(encoding="utf-8")

        self.assertIn('__events__ = ("on_complete",)', source)
        self.assertIn("MINIMUM_VISIBLE_SECONDS = 3.0", source)
        self.assertIn("rotation_started_at", source)
        self.assertIn("MAXIMUM_VISIBLE_SECONDS", source)
        self.assertIn("MINIMUM_VISIBLE_SECONDS", source)
        self.assertIn("PULSE_DOWN_SECONDS", source)
        self.assertIn("glow_logo", source)

    def test_dashboard_wraps_the_live_interface_with_the_loader(self):
        source = (PROJECT / "dashboard_v2.py").read_text(encoding="utf-8")

        self.assertIn("Window.clearcolor = (0, 0, 0, 1)", source)
        self.assertIn("DashboardWithStartupLoader", source)
        self.assertIn(
            "return DashboardWithStartupLoader(ResponsiveDashboard)",
            source,
        )


if __name__ == "__main__":
    unittest.main()

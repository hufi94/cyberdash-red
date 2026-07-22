import unittest
from pathlib import Path

from floor_glow import build_floor_glow_rgba


PROJECT = Path(__file__).resolve().parents[1]


class FloorGlowTest(unittest.TestCase):
    def test_texture_is_soft_and_fully_transparent_at_every_edge(self):
        width, height = 128, 32
        pixels = build_floor_glow_rgba(width, height)
        self.assertEqual(len(pixels), width * height * 4)

        alpha = pixels[3::4]
        top = alpha[(height - 1) * width : height * width]
        bottom = alpha[:width]
        left = alpha[0::width]
        right = alpha[width - 1 :: width]
        self.assertTrue(all(value == 0 for value in top))
        self.assertTrue(all(value == 0 for value in bottom))
        self.assertTrue(all(value == 0 for value in left))
        self.assertTrue(all(value == 0 for value in right))
        self.assertGreater(max(alpha), 180)
        self.assertGreater(len(set(alpha)), 60)

    def test_player_uses_clean_frames_and_not_baked_glow_frames(self):
        player_source = (PROJECT / "civic_360_widget.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('    / "civic_frames_outline"', player_source)
        self.assertNotIn('    / "civic_frames_bottom_glow"', player_source)


if __name__ == "__main__":
    unittest.main()

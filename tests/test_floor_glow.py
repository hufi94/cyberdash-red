import unittest
from pathlib import Path

from floor_glow import build_floor_glow_rgba, read_floor_glow_tracking


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

    def test_tracking_covers_the_complete_rotation_smoothly(self):
        tracking_path = (
            PROJECT
            / "assets"
            / "civic_frames_outline"
            / "floor_glow_tracking.tsv"
        )
        tracking = read_floor_glow_tracking(tracking_path)
        names = [f"frame_{index:04d}.png" for index in range(220)]
        self.assertEqual(list(tracking), names)

        geometry = [tracking[name] for name in names]

        def largest_loop_step(values):
            return max(
                abs(values[(index + 1) % len(values)] - values[index])
                for index in range(len(values))
            )

        self.assertLess(
            largest_loop_step([item.center_x for item in geometry]),
            5.0,
        )
        self.assertLess(
            largest_loop_step([item.center_y for item in geometry]),
            1.5,
        )
        self.assertLess(
            largest_loop_step([item.width for item in geometry]),
            7.0,
        )
        self.assertGreater(max(item.center_x for item in geometry), 318.0)
        self.assertLess(min(item.center_x for item in geometry), 263.0)


if __name__ == "__main__":
    unittest.main()

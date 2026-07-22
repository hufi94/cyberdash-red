import unittest
from pathlib import Path

from floor_glow import (
    EDGE_GLOW_THICKNESS,
    GLOW_FALLOFF_POWER,
    GLOW_MAXIMUM_ALPHA,
    Point,
    build_floor_glow_rgba,
    glow_strip_corners,
    projected_edge_strengths,
    projected_floor_corners,
)


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
        self.assertGreater(max(alpha), 240)
        self.assertGreater(len(set(alpha)), 60)

    def test_default_glow_is_large_and_high_intensity(self):
        self.assertGreaterEqual(EDGE_GLOW_THICKNESS, 50.0)
        self.assertGreaterEqual(GLOW_MAXIMUM_ALPHA, 245)
        self.assertLessEqual(GLOW_FALLOFF_POWER, 1.6)

    def test_player_uses_clean_frames_and_not_baked_glow_frames(self):
        player_source = (PROJECT / "civic_360_widget.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('    / "civic_frames_outline"', player_source)
        self.assertNotIn('    / "civic_frames_bottom_glow"', player_source)

    def test_projected_frame_rotates_instead_of_resizing_one_bar(self):
        rear = projected_floor_corners(0)
        diagonal = projected_floor_corners(27)
        side = projected_floor_corners(55)

        self.assertAlmostEqual(rear[1].y, rear[2].y, places=6)
        self.assertGreater(rear[2].x - rear[1].x, 210.0)

        diagonal_side_x = diagonal[1].x - diagonal[0].x
        diagonal_side_y = diagonal[1].y - diagonal[0].y
        self.assertGreater(abs(diagonal_side_x), 230.0)
        self.assertGreater(abs(diagonal_side_y), 60.0)

        self.assertAlmostEqual(side[0].y, side[1].y, places=6)
        self.assertGreater(side[1].x - side[0].x, 350.0)

    def test_projected_loop_has_no_frame_zero_jump(self):
        frames = [projected_floor_corners(index) for index in range(220)]
        largest_step = 0.0
        for index, current in enumerate(frames):
            following = frames[(index + 1) % len(frames)]
            for current_point, following_point in zip(current, following):
                largest_step = max(
                    largest_step,
                    abs(following_point.x - current_point.x),
                    abs(following_point.y - current_point.y),
                )
        self.assertLess(largest_step, 6.0)

    def test_closest_facing_edge_is_brightest(self):
        rear = projected_floor_corners(0)
        rear_strengths = projected_edge_strengths(0, rear)
        self.assertEqual(rear_strengths[1], max(rear_strengths))
        self.assertGreater(rear_strengths[1], 0.95)
        self.assertLess(rear_strengths[3], 0.1)

        side = projected_floor_corners(55)
        side_strengths = projected_edge_strengths(55, side)
        self.assertEqual(side_strengths[0], max(side_strengths))
        self.assertGreater(side_strengths[0], 0.95)

    def test_strip_is_built_around_a_diagonal_edge(self):
        strip = glow_strip_corners(Point(10, 20), Point(110, 70), 20)
        self.assertEqual(len(strip), 4)
        self.assertNotEqual(strip[0].y, strip[1].y)
        self.assertNotEqual(strip[0].x, strip[3].x)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path

from dashboard_theme import (
    active_temperature_segments,
    clipped_outline_points,
    dashboard_ui_scale,
    dashboard_panels,
    responsive_dashboard_panels,
    visualizer_row_color,
)


PROJECT = Path(__file__).resolve().parents[1]


class DashboardGeometryTest(unittest.TestCase):
    def test_compact_layout_fills_640_by_480_without_overlap(self):
        layout = dashboard_panels(640, 480)

        self.assertEqual(layout.top_left.x, 10)
        self.assertEqual(layout.bottom_left.y, 10)
        self.assertEqual(layout.top_right.right, 630)
        self.assertEqual(layout.bottom_right.right, 630)
        self.assertEqual(layout.top_right.x - layout.top_left.right, 6)
        self.assertEqual(layout.bottom_left.top + 6, layout.top_left.y)
        self.assertEqual(layout.top_left.width, layout.top_right.width)
        self.assertEqual(layout.bottom_left.width, layout.bottom_right.width)

    def test_wide_layout_uses_the_added_width_without_stretching_rows(self):
        compact = dashboard_panels(640, 480)
        wide = dashboard_panels(853, 480)

        self.assertEqual(wide.top_right.right, 843)
        self.assertGreater(wide.top_left.width, compact.top_left.width)
        self.assertEqual(wide.top_left.height, compact.top_left.height)
        self.assertEqual(wide.bottom_left.height, compact.bottom_left.height)

    def test_compact_display_uses_tighter_panels_and_moderate_ui_boost(self):
        compact = responsive_dashboard_panels(640, 480)

        self.assertEqual(compact.top_left.x, 7)
        self.assertEqual(compact.top_right.right, 633)
        self.assertEqual(compact.top_right.x - compact.top_left.right, 4)
        self.assertGreater(compact.bottom_left.height, 211)
        self.assertEqual(dashboard_ui_scale(640), 1.08)

    def test_wide_display_keeps_original_scale_and_spacing(self):
        wide = responsive_dashboard_panels(853, 480)

        self.assertEqual(wide.top_left.x, 10)
        self.assertEqual(wide.top_right.right, 843)
        self.assertEqual(wide.top_right.x - wide.top_left.right, 6)
        self.assertEqual(dashboard_ui_scale(853), 1.0)

    def test_clipped_outline_has_eight_ordered_corners(self):
        points = clipped_outline_points(10, 20, 100, 60, 8)

        self.assertEqual(len(points), 16)
        self.assertEqual(points[:4], (18, 20, 102, 20))
        self.assertEqual(points[-4:], (10, 72, 10, 28))


class DashboardColourTest(unittest.TestCase):
    def test_temperature_segments_are_clamped_and_fill_progressively(self):
        self.assertEqual(active_temperature_segments(-40, -20, 50, 10), 0)
        self.assertEqual(active_temperature_segments(15, -20, 50, 10), 5)
        self.assertEqual(active_temperature_segments(80, -20, 50, 10), 10)

    def test_invalid_temperature_ranges_are_rejected(self):
        with self.assertRaises(ValueError):
            active_temperature_segments(20, 50, 50, 10)
        with self.assertRaises(ValueError):
            active_temperature_segments(20, -20, 50, 0)

    def test_visualizer_is_solid_red_at_bottom_and_white_at_top(self):
        colours = [visualizer_row_color(index, 18) for index in range(18)]

        self.assertEqual(colours[0], (1.0, 0.025, 0.045, 1.0))
        self.assertEqual(colours[-1], (1.0, 1.0, 1.0, 1.0))
        self.assertTrue(
            all(
                current[1] <= following[1]
                and current[2] <= following[2]
                and current[3] == following[3] == 1.0
                for current, following in zip(colours, colours[1:])
            )
        )

    def test_dashboard_source_uses_the_approved_components(self):
        source = (PROJECT / "dashboard_v2.py").read_text(encoding="utf-8")

        self.assertIn("SegmentedTemperatureBar", source)
        self.assertIn("ThermometerIcon", source)
        self.assertIn("visualizer_row_color", source)
        self.assertIn("HONDA CIVIC EG9", source)
        self.assertNotIn("self.background_lines", source)


if __name__ == "__main__":
    unittest.main()

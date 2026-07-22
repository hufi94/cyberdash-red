import unittest

from display_layout import (
    SAFE_SCREEN_INSET,
    design_width_for_window,
    fit_design_to_window,
)


class DisplayLayoutTest(unittest.TestCase):
    def test_native_640_by_480_display(self):
        self.assertEqual(fit_design_to_window(640, 480), (1.0, 0.0, 0.0))

    def test_full_hd_display_is_centered_without_stretching(self):
        scale, offset_x, offset_y = fit_design_to_window(1920, 1080)
        self.assertEqual(scale, 2.25)
        self.assertEqual(offset_x, 240.0)
        self.assertEqual(offset_y, 0.0)

    def test_portrait_display_is_centered_vertically(self):
        scale, offset_x, offset_y = fit_design_to_window(480, 800)
        self.assertEqual(scale, 0.75)
        self.assertEqual(offset_x, 0.0)
        self.assertEqual(offset_y, 220.0)

    def test_uninitialized_window_uses_safe_defaults(self):
        self.assertEqual(fit_design_to_window(0, 0), (1.0, 0.0, 0.0))

    def test_wide_small_display_uses_its_complete_width(self):
        self.assertEqual(design_width_for_window(800, 480), 800)

    def test_full_hd_uses_sixteen_by_nine_design_width(self):
        self.assertEqual(design_width_for_window(1920, 1080), 853)

    def test_safe_inset_leaves_a_small_edge_margin(self):
        scale, offset_x, offset_y = fit_design_to_window(
            800,
            480,
            design_width=800,
            safe_inset=6,
        )
        self.assertAlmostEqual(scale, 0.975)
        self.assertAlmostEqual(offset_x, 10.0)
        self.assertAlmostEqual(offset_y, 6.0)

    def test_runtime_inset_is_tight_for_the_small_physical_screen(self):
        self.assertEqual(SAFE_SCREEN_INSET, 3)
        scale, offset_x, offset_y = fit_design_to_window(
            640,
            480,
            safe_inset=SAFE_SCREEN_INSET,
        )
        self.assertAlmostEqual(scale, 0.9875)
        self.assertAlmostEqual(offset_x, 4.0)
        self.assertAlmostEqual(offset_y, 3.0)


if __name__ == "__main__":
    unittest.main()

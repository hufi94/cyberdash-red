import unittest

from display_layout import fit_design_to_window


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


if __name__ == "__main__":
    unittest.main()

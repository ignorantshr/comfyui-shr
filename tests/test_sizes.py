import math
import unittest

from resizer.sizes import encoder_size, select_size, _fixed_sizes


class SizeTests(unittest.TestCase):
    def test_fixed_points_across_supported_resolutions(self):
        for resolution in range(32, 4097, 32):
            for width, height in ((1920, 1080), (4000, 3000), (1080, 1920), (100, 1000), (1, 10000)):
                w, h = select_size(width, height, resolution)
                # Independent expression from the official encoder.
                r = w / h
                expected = (max(32, round(math.sqrt(resolution**2 * r) / 32) * 32),
                            max(32, round(math.sqrt(resolution**2 / r) / 32) * 32))
                self.assertEqual((w, h), expected)
                self.assertEqual(select_size(w, h, resolution), (w, h))

    def test_search_completeness_against_small_exhaustive_grids(self):
        for n in range(1, 17):
            expected = {
                (32 * k, 32 * m)
                for k in range(1, n*n+n+2)
                for m in range(1, n*n+n+2)
                if encoder_size(32*k, 32*m, 32*n) == (32*k, 32*m)
            }
            self.assertEqual(set(_fixed_sizes(32*n)), expected)

    def test_zero_resolution_and_rounding(self):
        self.assertEqual(select_size(1920, 1080, 0), (1920, 1088))
        self.assertEqual(select_size(1, 1, 0), (32, 32))
        self.assertEqual(select_size(80, 112, 0), (64, 128))

    def test_matching_canvas_stays_unchanged(self):
        self.assertEqual(select_size(1920, 1088, 1440), (1920, 1088))

    def test_invalid_inputs(self):
        for r in (-32, 33, 4097, True, 1440.0):
            with self.assertRaises(ValueError):
                select_size(100, 100, r)
        for w, h in ((0, 100), (-1, 100), (100, 0), (1.5, 2)):
            with self.assertRaises(ValueError):
                select_size(w, h, 1440)


if __name__ == "__main__":
    unittest.main()

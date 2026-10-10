import math
import unittest
from processing import ndvi, temperature_c, clear_landsat, aggregate

class ProcessingTests(unittest.TestCase):
    def test_ndvi_uses_asset_offset_and_rejects_invalid_pixels(self):
        self.assertAlmostEqual(ndvi(2000, 3000, .0001, -.1), 1/3)
        self.assertIsNone(ndvi(0, 3000, .0001, -.1))
        self.assertIsNone(ndvi(1000, 1000, .0001, -.1))

    def test_landsat_scale_and_quality(self):
        self.assertAlmostEqual(temperature_c(45000), 29.6609, places=4)
        self.assertIsNone(temperature_c(0))
        self.assertTrue(clear_landsat(64, 0))
        for bit in range(6):
            self.assertFalse(clear_landsat(64 | (1 << bit), 0))
        self.assertFalse(clear_landsat(64, 1))

    def test_cells_require_half_the_pixels_and_json_safe_numbers(self):
        self.assertIsNone(aggregate([None, None, .2, math.nan]))
        self.assertEqual(aggregate([None, .2, .4, None]), .3)
        self.assertIsNone(aggregate([]))

if __name__ == '__main__':
    unittest.main()

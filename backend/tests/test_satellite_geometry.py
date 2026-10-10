import importlib
import math
import sys
import unittest
from pathlib import Path
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
try:
    geometry = importlib.import_module('satellite_geometry')
except ModuleNotFoundError:
    geometry = None


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(geometry, 'Satellite tile geometry is not implemented')

    def test_metric_tiles_cover_400_cells_and_both_hemispheres(self):
        for lat, lng, epsg in [(12.9767, 77.5929, 32643), (-10, 0, 32731)]:
            tile = geometry.tile_for_location(lat, lng)
            self.assertEqual(tile['epsg'], epsg)
            self.assertEqual(tile['rows'], 20)
            self.assertEqual(tile['columns'], 20)
            self.assertEqual(tile['center']['x'] % 1000, 0)
            self.assertEqual(tile['bounds'][2]-tile['bounds'][0], 2000)
            self.assertEqual(len(geometry.build_cells(tile)), 400)
            self.assertEqual(geometry.tile_from_id(tile['id']), tile)

    def test_half_up_rounding_and_exact_cell_boundaries(self):
        self.assertEqual(geometry.snap_center(500500), 501000)
        self.assertEqual(geometry.snap_center(-500), 0)
        tile = geometry.tile_from_id('p1-32643-500000-1400000')
        inverse = Transformer.from_crs(32643, 4326, always_xy=True)
        for x, y, expected in [(499000, 1401000, 0), (499100, 1400900, 21),
                               (501000, 1399000, 399), (498999, 1400000, None)]:
            lng, lat = inverse.transform(x, y)
            self.assertEqual(geometry.cell_index(tile, lat, lng), expected)

    def test_display_neighborhood_fits_tile_at_ownership_extremes(self):
        inverse = Transformer.from_crs(32643, 4326, always_xy=True)
        for x, y in [(499500.1, 1399500.1), (500499.9, 1400499.9)]:
            lng, lat = inverse.transform(x, y)
            tile = geometry.tile_for_location(lat, lng)
            w, s, e, n = tile['bounds']
            self.assertGreaterEqual(x-450, w)
            self.assertLessEqual(x+450, e)
            self.assertGreaterEqual(y-450, s)
            self.assertLessEqual(y+450, n)

    def test_rotated_bbox_corner_is_not_coverage(self):
        tile = geometry.tile_for_location(26.8879, 80.9494)
        w, s, e, n = tile['bbox']
        self.assertIsNone(geometry.cell_index(tile, n-1e-10, e-1e-10))

    def test_invalid_coordinates_and_wrapped_tiles_are_rejected(self):
        for lat, lng in [(True, 80), (85, 0), (-81, 0), (0, math.nan), (0, 181), (0, 179.9999)]:
            with self.subTest(lat=lat, lng=lng), self.assertRaises(ValueError):
                geometry.tile_for_location(lat, lng)

    def test_ids_cannot_select_arbitrary_paths_or_noncanonical_tiles(self):
        for value in ['../secret', 'p1-32600-500000-1400000', 'p1-32643-500001-1400000']:
            with self.assertRaises(ValueError):
                geometry.tile_from_id(value)
        self.assertEqual(geometry.parse_dataset_id('p1-32643-500000-1400000.'+'a'*32+'.ndvi'),
                         ('p1-32643-500000-1400000', 'a'*32, 'ndvi'))
        with self.assertRaises(ValueError):
            geometry.parse_dataset_id('p1-32643-500000-1400000.bad.final')

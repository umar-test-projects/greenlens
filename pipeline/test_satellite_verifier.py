import importlib
import unittest
import numpy as np
try:
    verifier=importlib.import_module('verify_satellite_window')
except ModuleNotFoundError:
    verifier=None


class IndependentVerifierTests(unittest.TestCase):
    def test_known_thermal_scaling_clear_zero_flags_and_mask_threshold(self):
        self.assertIsNotNone(verifier)
        arrays={'lwir11':np.full((10,10),45000),'qa_pixel':np.zeros((10,10),dtype='uint16'),'qa_radsat':np.zeros((10,10),dtype='uint16')}
        self.assertAlmostEqual(verifier.calculate('tempC',arrays,{}),29.6609,places=4)
        arrays['qa_pixel'].flat[:51]=8
        self.assertIsNone(verifier.calculate('tempC',arrays,{}))
        arrays['qa_pixel'].flat[50]=0
        self.assertAlmostEqual(verifier.calculate('tempC',arrays,{}),29.6609,places=4)
        arrays['lwir11'][:]=0
        self.assertIsNone(verifier.calculate('tempC',arrays,{}))

    def test_independent_reflectance_offsets_and_cloud_exclusion(self):
        self.assertIsNotNone(verifier)
        arrays={'red':np.full((10,10),2000),'nir':np.full((10,10),5000),'scl':np.full((10,10),4)}
        assets={'red':{'raster:bands':[{'scale':.0001,'offset':-.1}]},'nir':{'raster:bands':[{'scale':.0001,'offset':0}]}}
        self.assertAlmostEqual(verifier.calculate('ndvi',arrays,assets),.6667,places=4)
        arrays['scl'][:]=9
        self.assertIsNone(verifier.calculate('ndvi',arrays,assets))

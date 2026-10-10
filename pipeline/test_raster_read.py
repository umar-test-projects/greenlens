import tempfile
import unittest
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin
from build_grid import read_asset


class RasterReadTests(unittest.TestCase):
    def test_valid_zero_quality_flags_are_preserved_when_warped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'quality.tif'
            transform = from_origin(499500,2974500,10,10)
            with rasterio.open(path,'w',driver='GTiff',width=10,height=10,
                               count=1,dtype='uint16',crs='EPSG:32644',
                               transform=transform) as dataset:
                dataset.write(np.zeros((10,10),dtype='uint16'),1)
            result=read_asset({'href':str(path),'roles':['saturation']},
                              transform,'EPSG:32644',10,local=path)
            np.testing.assert_array_equal(result,np.zeros((10,10),dtype='uint16'))
            outside=read_asset({'href':str(path),'roles':['saturation']},
                               from_origin(510000,2974500,10,10),
                               'EPSG:32644',10,local=path)
            np.testing.assert_array_equal(outside,np.full((10,10),65535,dtype='uint16'))

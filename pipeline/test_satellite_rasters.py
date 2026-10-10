import importlib
import sys
import tempfile
import time
import unittest
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend/src'))
from satellite_geometry import tile_from_id
try:
    rasters = importlib.import_module('satellite_rasters')
except ModuleNotFoundError:
    rasters = None


class SatelliteRasterTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(rasters, 'Satellite scientific processing is not implemented')
        self.tile = tile_from_id('p1-32643-500000-1400000')
        self.red = np.full((200, 200), 2000)
        self.nir = np.full((200, 200), 5000)
        self.scl = np.full((200, 200), 4)
        self.rmeta = {'scale': .0001, 'offset': -.1}
        self.nmeta = {'scale': .0001, 'offset': 0}

    def test_independent_offsets_and_mask_threshold(self):
        self.scl[:5, :10] = 9
        self.scl[:5, 10:20] = 9; self.scl[5, 10] = 9
        values = rasters.ndvi_cells(self.red, self.nir, self.scl, self.rmeta, self.nmeta)
        self.assertEqual(values[0], .6667)
        self.assertIsNone(values[1])
        self.assertEqual(len(values), 400)
        for bad in [0, 1, 2, 3, 7, 8, 9, 10, 11]:
            self.assertIsNone(rasters.ndvi_cells(self.red,self.nir,np.full((200,200),bad),self.rmeta,self.nmeta)[0])

    def test_invalid_reflectance_is_not_an_observation(self):
        self.assertIsNone(rasters.ndvi_cells(self.red*0,self.nir,self.scl,self.rmeta,self.nmeta)[0])
        self.assertIsNone(rasters.ndvi_cells(self.red,self.nir,self.scl,{'scale':.0001,'offset':-1},self.nmeta)[0])
        with self.assertRaises(ValueError):
            rasters.ndvi_cells(self.red,self.nir,self.scl,{},self.nmeta)

    def test_temperature_scaling_and_quality_bits(self):
        dn, qa, sat = np.full((200,200),45000), np.zeros((200,200),dtype='uint16'), np.zeros((200,200),dtype='uint16')
        self.assertEqual(rasters.temperature_cells(dn,qa,sat)[0],29.6609)
        for bit in range(6):
            self.assertIsNone(rasters.temperature_cells(dn,qa+(1<<bit),sat)[0])
        self.assertIsNone(rasters.temperature_cells(dn,qa,sat+1)[0])
        self.assertIsNone(rasters.temperature_cells(dn*0,qa,sat)[0])

    def test_20m_quality_is_reprojected_and_valid_zero_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'qa.tif'
            with rasterio.open(path,'w',driver='GTiff',width=100,height=100,count=1,dtype='uint16',
                               crs='EPSG:32643',transform=from_origin(499000,1401000,20,20)) as dataset:
                dataset.write(np.zeros((100,100),dtype='uint16'),1)
            result = rasters.read_asset({},self.tile,local=path)
            self.assertEqual(result.shape,(200,200))
            self.assertFalse(np.any(result))
            outside = dict(self.tile,bounds=[498000,1398000,500000,1400000])
            with self.assertRaises(rasters.UnusableScene):
                rasters.read_asset({},outside,local=path)

    def scene(self, name):
        assets = {key:{'href':f'https://sentinel-cogs.s3.us-west-2.amazonaws.com/{name}/{key}.tif',
                        'raster:bands':[self.rmeta if key=='red' else self.nmeta]} for key in ['red','nir','scl']}
        return {'id':name,'collection':'sentinel-2-l2a','properties':{'datetime':'2026-05-12T05:25:00Z'},'assets':assets}

    def test_partial_scene_is_skipped_and_latest_valid_scene_is_selected(self):
        read = []
        def reader(asset,tile,**kwargs):
            read.append(asset['href'])
            if '/partial/' in asset['href']:
                raise rasters.UnusableScene('Partial source coverage')
            return self.scl if asset['href'].endswith('/scl.tif') else self.red if asset['href'].endswith('/red.tif') else self.nir
        result = rasters.process_field('ndvi',self.tile,time.monotonic()+100,
            catalog_search=lambda field,tile:[self.scene('partial'),self.scene('valid'),self.scene('older')],reader=reader)
        self.assertEqual(result['provenance']['sceneId'],'valid')
        self.assertEqual(result['values'][0],.6667)
        self.assertFalse(any('/older/' in href for href in read))

    def test_four_attempt_limit_and_provider_failure_is_error(self):
        reads = []
        def cloudy(asset,tile,**kwargs):
            reads.append(asset['href']); return self.scl*0
        result = rasters.process_field('ndvi',self.tile,time.monotonic()+100,
            catalog_search=lambda field,tile:[self.scene(str(i)) for i in range(12)],reader=cloudy)
        self.assertEqual(result['fieldStatus']['status'],'no_data')
        self.assertEqual(len(reads),12)
        def broken(asset,tile,**kwargs):
            raise OSError('private provider details')
        result = rasters.process_field('ndvi',self.tile,time.monotonic()+100,
            catalog_search=lambda field,tile:[self.scene('broken')],reader=broken)
        self.assertEqual(result['fieldStatus']['status'],'error')
        self.assertNotIn('private provider',str(result))

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from super_resolution import build

class SuperResolutionTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name)
  self.directory=self.root/'public/data'
  self.directory.mkdir(parents=True)
  cv2.imwrite(str(self.directory/'satellite-rgb.png'),np.full((5,7,3),110,np.uint8))
  self.meta={'image':'/data/satellite-rgb.png','resolutionM':10,'cells':[{'row':0,'column':0}],'sceneId':'fixture'}
  (self.directory/'imagery.json').write_text(json.dumps(self.meta))
  (self.directory/'grid.json').write_text('{"temperature":31,"vegetation":0.7}')
  self.original=(self.directory/'satellite-rgb.png').read_bytes()
 def check_preserved(self):
  self.assertEqual((self.directory/'satellite-rgb.png').read_bytes(),self.original)
  self.assertEqual((self.directory/'grid.json').read_text(),'{"temperature":31,"vegetation":0.7}')
  result=json.loads((self.directory/'imagery.json').read_text())
  for key,value in self.meta.items(): self.assertEqual(result[key],value)
  return result
 def test_missing_weights_falls_back_and_clears_stale_metadata(self):
  stale={**self.meta,'superResolvedImage':'/data/stale.png'}
  (self.directory/'imagery.json').write_text(json.dumps(stale))
  (self.directory/'satellite-sr.png').write_bytes(b'stale')
  build(self.root,self.root/'missing.pth')
  self.assertFalse((self.directory/'satellite-sr.png').exists())
  result=self.check_preserved()
  self.assertNotIn('superResolvedImage',result)
  self.assertEqual(result['superResolution']['status'],'fallback')
 def test_success_records_provenance_and_exact_fourfold_dimensions(self):
  weights=self.root/'model.pth';weights.write_bytes(b'fixture')
  with patch('super_resolution.infer',return_value=(np.full((20,28,3),125,np.uint8),{'device':'cpu','versions':{}})):
   build(self.root,weights)
  result=self.check_preserved()
  self.assertTrue(result['superResolution']['generatedDetail'])
  self.assertEqual(len(result['superResolution']['weightsSha256']),64)
  self.assertEqual(cv2.imread(str(self.directory/'satellite-sr.png')).shape,(20,28,3))
 def test_inference_failure_or_invalid_size_falls_back(self):
  weights=self.root/'model.pth';weights.write_bytes(b'fixture')
  for response in [RuntimeError('CUDA out of memory'),ImportError('Optional dependency unavailable'),None]:
   with patch('super_resolution.infer',side_effect=response,return_value=(np.zeros((5,7,3),np.uint8),{})):
    build(self.root,weights)
   self.assertNotIn('superResolvedImage',self.check_preserved())

if __name__=='__main__':unittest.main()

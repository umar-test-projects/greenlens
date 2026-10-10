import unittest
import numpy as np
from enhance_imagery import enhance_rgb

class EnhancementTests(unittest.TestCase):
 def test_low_contrast_detail_gets_more_separation(self):
  source=np.tile(np.linspace(100,150,100,dtype=np.uint8),(100,1))
  rgb=np.repeat(source[:,:,None],3,axis=2)
  result=enhance_rgb(rgb)
  self.assertEqual(result.shape,rgb.shape)
  self.assertEqual(result.dtype,np.uint8)
  self.assertGreater(float(np.percentile(result,95)-np.percentile(result,5)),float(np.percentile(rgb,95)-np.percentile(rgb,5)))
  self.assertGreater(float(result[:,-10:].mean()),float(result[:,:10].mean()))
 def test_constant_scene_stays_constant_without_invented_edges(self):
  rgb=np.full((40,40,3),120,dtype=np.uint8)
  np.testing.assert_array_equal(enhance_rgb(rgb),rgb)
 def test_input_is_preserved(self):
  rgb=np.arange(300,dtype=np.uint8).reshape(10,10,3)
  copy=rgb.copy()
  enhance_rgb(rgb)
  np.testing.assert_array_equal(rgb,copy)

if __name__=='__main__':unittest.main()

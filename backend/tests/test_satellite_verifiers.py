import importlib
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    verifier=importlib.import_module('verify_satellite')
except ModuleNotFoundError:
    verifier=None


class VerifierTests(unittest.TestCase):
    def test_citations_require_exact_cell_value_scene_and_date(self):
        self.assertIsNotNone(verifier)
        source={'field':'ndvi','sceneId':'S2','acquiredAt':'2026-09-01'}
        result={'grid':{'cells':[{'lat':12,'lng':77,'ndvi':.45,'tempC':None}]},'metadata':{'provenance':[source]}}
        citation={**source,'lat':12,'lng':77,'value':.45}
        verifier.check_citations(result,{'citations':[citation]})
        for key,value in [('value',.46),('sceneId','old'),('acquiredAt','2025-01-01')]:
            with self.assertRaises(AssertionError):verifier.check_citations(result,{'citations':[{**citation,key:value}]})


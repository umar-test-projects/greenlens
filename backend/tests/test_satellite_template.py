import unittest
from pathlib import Path
import yaml


class IntrinsicLoader(yaml.SafeLoader):
    pass


def intrinsic(loader, tag, node):
    return {tag: loader.construct_scalar(node) if isinstance(node,yaml.ScalarNode) else
            loader.construct_sequence(node) if isinstance(node,yaml.SequenceNode) else loader.construct_mapping(node)}


IntrinsicLoader.add_multi_constructor('!', intrinsic)


class SatelliteTemplateTests(unittest.TestCase):
    def test_public_api_routes_to_bounded_private_processing(self):
        template=yaml.load((Path(__file__).resolve().parents[2]/'template.yaml').read_text(),Loader=IntrinsicLoader)
        resources=template['Resources']
        self.assertIn('SatelliteWorker',resources,'Raster processing worker is not configured')
        worker=resources['SatelliteWorker']['Properties']
        self.assertEqual((worker['Timeout'],worker['MemorySize'],worker['EphemeralStorage']['Size']),(300,2048,1024))
        self.assertNotIn('ReservedConcurrentExecutions',worker)
        async_config=resources['SatelliteAsyncConfig']['Properties']
        self.assertEqual((async_config['MaximumEventAgeInSeconds'],async_config['MaximumRetryAttempts']),(60,0))
        query=resources['QueryFunction']['Properties']
        self.assertEqual(query['Events']['Satellite']['Properties']['Path'],'/satellite')
        self.assertEqual(query['Events']['Satellite']['Properties']['Method'],'POST')
        self.assertEqual(query['Events']['Query']['Properties']['Path'],'/query')
        cache=resources['ProcessingBucket']['Properties']
        self.assertTrue(all(cache['PublicAccessBlockConfiguration'].values()))
        self.assertEqual(cache['LifecycleConfiguration']['Rules'][0]['ExpirationInDays'],7)
        self.assertIn('SatelliteUrl',template['Outputs'])
        self.assertEqual(resources['QueryApi']['Properties']['DefaultRouteSettings']['ThrottlingRateLimit'],1)

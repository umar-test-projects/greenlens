import importlib
import json
import sys
import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from satellite_geometry import tile_for_location, build_cells
from satellite_store import SatelliteStore
from satellite_fakes import MemoryS3
from app import handler
try:
    api = importlib.import_module('satellite_api')
except ModuleNotFoundError:
    api = None


class LambdaTransport:
    def __init__(self):
        self.jobs, self.fail = [], False

    def invoke(self, **options):
        if self.fail:
            raise RuntimeError('private invocation detail')
        if options['InvocationType'] != 'Event':
            raise AssertionError('Worker must be asynchronous')
        self.jobs.append(json.loads(options['Payload']))
        return {'StatusCode': 202}


class SatelliteApiTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(api, 'Satellite processing API is not implemented')
        self.now = datetime(2026,10,11,tzinfo=timezone.utc)
        self.store = SatelliteStore(MemoryS3(),'cache',billing=lambda now:Decimal(0))
        self.provider = LambdaTransport()
        self.origin = {'lat':12.9767,'lng':77.5929}

    def request(self, body=None, now=None):
        return api.handle(body or self.origin,self.store,self.provider,now or self.now)

    def test_start_poll_and_jitter_do_not_invoke_duplicate_work(self):
        status, body, _ = self.request()
        self.assertEqual(status,202)
        job=body['jobId']
        self.assertEqual(self.provider.jobs,[{'jobId':job}])
        self.assertEqual(self.request(dict(self.origin,jobId=job))[1]['jobId'],job)
        self.assertEqual(len(self.provider.jobs),1)
        self.assertEqual(self.request({'lat':12.97671,'lng':77.59291})[1]['jobId'],job)
        self.assertEqual(len(self.provider.jobs),1)

    def test_busy_and_budget_fail_without_creating_another_job(self):
        self.request()
        status,body,headers=self.request({'lat':26.8879,'lng':80.9494})
        self.assertEqual(status,429)
        self.assertEqual(body['error']['code'],'PROCESSING_BUSY')
        self.assertEqual(headers['Retry-After'],'15')
        self.assertEqual(len(self.provider.jobs),1)
        self.store = SatelliteStore(MemoryS3(),'cache',billing=lambda now:Decimal('10.01'))
        status,body,_=self.request()
        self.assertEqual(status,503)
        self.assertEqual(body['error']['code'],'BUDGET_LIMIT')

    def test_invalid_inputs_do_not_call_sources(self):
        for changes in [{'lat':True},{'lng':float('nan')},{'jobId':'../private'},
                        {'retryFailed':'yes'},{'jobId':'bad','retryFailed':True},{'assetUrl':'https://evil.example'}]:
            status,_,_=self.request(dict(self.origin,**changes))
            self.assertEqual(status,400)
        self.assertEqual(self.provider.jobs,[])

    def test_invocation_failure_releases_admission_and_requires_explicit_retry(self):
        self.provider.fail=True
        status,body,_=self.request()
        self.assertEqual(status,503)
        self.assertNotIn('private invocation',str(body))
        self.assertEqual(self.store._read('admission/global.json')['body']['owner'],'')
        self.provider.fail=False
        self.assertEqual(self.request()[0],503)
        self.assertEqual(self.request(dict(self.origin,retryFailed=True))[0],503)
        self.assertEqual(self.request(dict(self.origin,retryFailed=True),self.now+timedelta(seconds=61))[0],202)

    def test_poll_expired_job_does_not_restart_work(self):
        _,body,_=self.request()
        status,error,_=self.request(dict(self.origin,jobId=body['jobId']),self.now+timedelta(seconds=421))
        self.assertEqual(status,503)
        self.assertEqual(error['error']['code'],'JOB_EXPIRED')
        self.assertEqual(len(self.provider.jobs),1)

    def test_retry_expired_worker_preserves_published_ndvi_and_original_expiry(self):
        _,body,_=self.request()
        job=body['jobId']
        self.store.claim_worker(job,self.now)
        tile=tile_for_location(**self.origin)
        cells=build_cells(tile)
        for cell in cells:
            cell['ndvi']=.45
        expiry=self.now.timestamp()+86400
        result={'grid':{**tile,'cells':cells},'metadata':{'source':'satellite','expiresAt':expiry,
            'provenance':[{'field':'ndvi','dataset':'sentinel-2-l2a','sceneId':'ORIGINAL-NDVI','acquiredAt':'2026-05-12T00:00:00Z'}]},
            'fieldStatus':{'ndvi':{'status':'ready','expiresAt':expiry},'tempC':{'status':'processing'}}}
        self.store.publish(job,'ndvi',result,'processing',self.now)
        status,retried,_=self.request(dict(self.origin,retryFailed=True),self.now+timedelta(seconds=421))
        self.assertEqual(status,202)
        self.assertNotEqual(retried['jobId'],job)
        self.assertEqual(retried['fieldStatus']['ndvi'],result['fieldStatus']['ndvi'])
        saved=self.store.read_state(tile['id'])['body']['carry']
        self.assertEqual(saved['grid']['cells'][0]['ndvi'],.45)
        self.assertEqual(saved['metadata']['expiresAt'],expiry)
        self.assertEqual(saved['metadata']['provenance'][0]['sceneId'],'ORIGINAL-NDVI')

    def prime(self):
        _,body,_=self.request(); job=body['jobId']
        self.store.claim_worker(job,self.now)
        tile=tile_for_location(**self.origin)
        grid={**tile,'cells':build_cells(tile)}
        for cell in grid['cells']:
            cell['ndvi']=.45
        result={'grid':grid,'metadata':{'source':'satellite','expiresAt':self.now.timestamp()+86400,
            'provenance':[{'field':'ndvi','dataset':'sentinel-2-l2a','sceneId':'NDVI-SCENE','acquiredAt':'2026-05-12T00:00:00Z'}]},
            'fieldStatus':{'ndvi':{'status':'ready','expiresAt':self.now.timestamp()+86400},'tempC':{'status':'processing'}}}
        self.store.publish(job,'ndvi',result,'processing',self.now)
        final=json.loads(json.dumps(result))
        for cell in final['grid']['cells']:
            cell['tempC']=30
        final['metadata']['provenance'].append({'field':'tempC','dataset':'landsat-c2-l2','sceneId':'HEAT-SCENE','acquiredAt':'2026-05-11T00:00:00Z'})
        final['fieldStatus']['tempC']={'status':'ready','expiresAt':self.now.timestamp()+86400}
        self.store.publish(job,'final',final,'ready',self.now)
        return job

    def test_summary_uses_exact_revision_after_temperature_arrives(self):
        job=self.prime()
        payload=dict(self.origin,heading=0,question='What are the temperature and NDVI here?',datasetId=job+'.ndvi')
        with patch('app.get_processing_store',return_value=self.store,create=True), patch('app.utcnow',return_value=self.now,create=True):
            response=handler({'body':json.dumps(payload)},None)
            self.assertEqual(response['statusCode'],200)
            answer=json.loads(response['body'])['answer']
            self.assertTrue(answer['citations'])
            self.assertEqual({c['field'] for c in answer['citations']},{'ndvi'})
            self.assertEqual(answer['citations'][0]['sceneId'],'NDVI-SCENE')
            payload['datasetId']=job+'.final'
            answer=json.loads(handler({'body':json.dumps(payload)},None)['body'])['answer']
            self.assertEqual({c['field'] for c in answer['citations']},{'ndvi','tempC'})
            payload.update(lat=0,lng=0)
            response=handler({'body':json.dumps(payload)},None)
            self.assertEqual(json.loads(response['body'])['layers']['status'],'no_data')

    def test_fresh_cache_does_not_start_or_refresh_job(self):
        job=self.prime()
        status,body,_=self.request(dict(self.origin,retryFailed=True))
        self.assertEqual(status,200)
        self.assertEqual(body['datasetId'],job+'.final')
        self.assertEqual(len(self.provider.jobs),1)

    def test_http_satellite_validation_describes_gps_inputs(self):
        response=handler({'routeKey':'POST /satellite','body':json.dumps({'lat':True,'lng':80})},None)
        self.assertEqual(response['statusCode'],400)
        self.assertIn('GPS',json.loads(response['body'])['error']['message'])

import importlib
import sys
import time
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend/src'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend/tests'))
from satellite_geometry import tile_for_location
from satellite_store import SatelliteStore
from satellite_fakes import MemoryS3
from decimal import Decimal
from unittest.mock import Mock
from satellite_api import handle
try:
    worker = importlib.import_module('satellite_worker')
except ModuleNotFoundError:
    worker = None


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(worker,'Asynchronous satellite worker is not implemented')
        self.now = datetime(2026,10,11,tzinfo=timezone.utc)
        self.tile = tile_for_location(12.9767,77.5929)
        self.job = self.tile['id']+'.'+'a'*32
        self.store = SatelliteStore(MemoryS3(),'cache',billing=lambda now:Decimal(0))
        self.store.acquire(self.job,self.now)
        self.store.create_job(self.tile,'a'*32,self.now)

    def field(self, field, status='ready'):
        data = {'values':[.4 if field=='ndvi' else 30]*400 if status=='ready' else [None]*400,
                'fieldStatus':{'status':status,'reason':'Fixture','expiresAt':self.now.timestamp()+86400}}
        if status=='ready':
            data['provenance']={'field':field,'dataset':'sentinel-2-l2a' if field=='ndvi' else 'landsat-c2-l2',
                'sceneId':field+'-scene','acquiredAt':'2026-05-12T00:00:00Z' if field=='ndvi' else '2026-05-11T00:00:00Z'}
        return data

    def test_ndvi_published_before_temperature_and_duplicate_event_does_no_reads(self):
        calls = []
        def process(field,tile,deadline):
            calls.append(field)
            if field=='tempC':
                partial=self.store.read_result(self.job+'.ndvi',self.now)
                self.assertEqual(partial['grid']['cells'][0]['ndvi'],.4)
                self.assertIsNone(partial['grid']['cells'][0]['tempC'])
            return self.field(field)
        result=worker.run_job({'jobId':self.job},self.store,process,lambda:self.now,time.monotonic()+100)
        self.assertEqual(result['status'],'ready')
        self.assertEqual(self.store.read_result(self.job+'.final',self.now)['grid']['cells'][0]['tempC'],30)
        worker.run_job({'jobId':self.job},self.store,process,lambda:self.now,time.monotonic()+100)
        self.assertEqual(calls,['ndvi','tempC'])

    def test_temperature_error_retains_measured_ndvi_and_releases_slot(self):
        result=worker.run_job({'jobId':self.job},self.store,
            lambda field,tile,deadline:self.field(field,'ready' if field=='ndvi' else 'error'),
            lambda:self.now,time.monotonic()+100)
        self.assertEqual(result['status'],'partial')
        final=self.store.read_result(self.job+'.final',self.now)
        self.assertEqual(final['grid']['cells'][0]['ndvi'],.4)
        self.assertIsNone(final['grid']['cells'][0]['tempC'])
        self.assertIsNotNone(self.store.acquire('next',self.now))

    def test_both_empty_is_no_data_with_no_fake_provenance(self):
        result=worker.run_job({'jobId':self.job},self.store,
            lambda field,tile,deadline:self.field(field,'no_data'),lambda:self.now,time.monotonic()+100)
        self.assertEqual(result['status'],'no_data')
        self.assertEqual(self.store.read_result(self.job+'.final',self.now)['metadata']['provenance'],[])

    def test_expired_partial_worker_retry_processes_only_temperature(self):
        self.store.claim_worker(self.job,self.now)
        partial=worker.make_result(self.tile,{'ndvi':self.field('ndvi')},self.now)
        self.store.publish(self.job,'ndvi',partial,'processing',self.now)
        later=self.now+timedelta(seconds=421)
        status,body,_=handle({'lat':12.9767,'lng':77.5929,'retryFailed':True},self.store,
            Mock(invoke=Mock(return_value={'StatusCode':202})),later)
        self.assertEqual(status,202)
        calls=[]
        def process(field,tile,deadline):
            calls.append(field)
            return self.field(field)
        worker.run_job({'jobId':body['jobId']},self.store,process,lambda:later,time.monotonic()+100)
        final=self.store.read_result(body['jobId']+'.final',later)
        self.assertEqual(calls,['tempC'])
        self.assertEqual(final['fieldStatus']['ndvi']['expiresAt'],partial['fieldStatus']['ndvi']['expiresAt'])
        self.assertEqual(final['grid']['cells'][0]['ndvi'],.4)
        self.assertEqual(final['grid']['cells'][0]['tempC'],30)

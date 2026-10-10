import importlib
import sys
import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from satellite_geometry import tile_for_location, build_cells
from satellite_fakes import MemoryS3
try:
    module = importlib.import_module('satellite_store')
except ModuleNotFoundError:
    module = None


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(module, 'Satellite cache/admission is not implemented')
        self.s3 = MemoryS3()
        self.cost = Decimal('0')
        self.store = module.SatelliteStore(self.s3, 'cache', billing=lambda now: self.cost)
        self.now = datetime(2026, 10, 11, tzinfo=timezone.utc)
        self.tile = tile_for_location(12.9767, 77.5929)
        self.job = self.tile['id']+'.'+'a'*32

    def admitted(self):
        lease = self.store.acquire(self.job, self.now)
        self.store.create_job(self.tile, 'a'*32, self.now)
        return lease

    def result(self, field='ndvi'):
        grid = {**self.tile, 'cells': build_cells(self.tile)}
        grid['cells'][0][field] = .4 if field == 'ndvi' else 30
        expiry = self.now.timestamp()+86400
        return {'grid': grid, 'metadata': {'provenance': [], 'expiresAt': expiry},
                'fieldStatus': {field: {'status': 'ready', 'expiresAt': expiry},
                                ('tempC' if field == 'ndvi' else 'ndvi'): {'status': 'processing'}}}

    def test_two_distinct_tiles_share_one_slot_and_crash_claim_expires(self):
        lease = self.admitted()
        self.assertEqual(lease['body']['expiresAt']-self.now.timestamp(), 420)
        self.assertIsNone(self.store.acquire('other', self.now))
        newer = self.store.acquire('other', self.now+timedelta(seconds=421))
        self.assertIsNotNone(newer)
        self.assertFalse(self.store.release(lease))

    def test_duplicate_worker_claim_is_noop(self):
        self.admitted()
        self.assertIsNotNone(self.store.claim_worker(self.job, self.now))
        self.assertIsNone(self.store.claim_worker(self.job, self.now))

    def test_result_revisions_are_immutable_and_old_generation_cannot_publish(self):
        self.admitted()
        self.store.claim_worker(self.job, self.now)
        result = self.result()
        self.assertTrue(self.store.publish(self.job, 'ndvi', result, 'processing', self.now))
        ndvi_id = self.job+'.ndvi'
        self.assertEqual(self.store.read_result(ndvi_id, self.now)['grid']['cells'][0]['tempC'], None)
        final = self.result(); final['grid']['cells'][0]['tempC'] = 30
        self.assertTrue(self.store.publish(self.job, 'final', final, 'ready', self.now))
        self.assertIsNone(self.store.read_result(ndvi_id, self.now)['grid']['cells'][0]['tempC'])
        self.assertFalse(self.store.publish(self.job, 'ndvi', final, 'processing', self.now))
        with self.assertRaises(module.ExpiredResult):
            self.store.read_result(ndvi_id, self.now+timedelta(days=1))

    def test_old_generation_cannot_release_new_admission(self):
        lease = self.admitted()
        self.store.release(lease)
        newer = self.store.acquire('newer', self.now)
        self.assertFalse(self.store.release(lease))
        self.assertEqual(self.s3.body('admission/global.json')['owner'], 'newer')

    def test_retry_preserves_success_expiry(self):
        self.admitted(); self.store.claim_worker(self.job, self.now)
        partial = self.result()
        partial['fieldStatus']['tempC'] = {'status': 'error', 'retryAfterAt': self.now.timestamp()+60}
        self.store.publish(self.job, 'final', partial, 'partial', self.now)
        original = self.store.read_result(self.job+'.final', self.now)
        self.store.create_job(self.tile, 'b'*32, self.now+timedelta(seconds=61), carry=original)
        carried = self.store.read_state(self.tile['id'])['body']['carry']
        self.assertEqual(carried['fieldStatus']['ndvi']['expiresAt'], self.now.timestamp()+86400)

    def test_reported_budget_ceiling_prevents_admission(self):
        self.cost = Decimal('9.01')
        with self.assertRaises(module.BudgetExceeded):
            self.store.acquire(self.job, self.now)

    def test_reservations_survive_release(self):
        for index in range(8):
            lease = self.store.acquire(str(index), self.now)
            self.assertIsNotNone(lease)
            self.store.release(lease)
        with self.assertRaises(module.BudgetExceeded):
            self.store.acquire('ninth', self.now)

    def test_unverified_billing_fails_closed(self):
        def unavailable(now):
            raise RuntimeError('Billing unavailable')
        self.store.billing = unavailable
        with self.assertRaises(RuntimeError):
            self.store.acquire(self.job, self.now)
        self.assertNotIn('admission/global.json', self.s3.objects)

    def test_budget_stop_does_not_keep_making_billable_billing_queries(self):
        checks=[]
        self.store.billing=lambda now: checks.append(now) or Decimal('9.01')
        for _ in range(3):
            with self.assertRaises(module.BudgetExceeded):
                self.store.acquire(self.job,self.now)
        self.assertEqual(len(checks),1)

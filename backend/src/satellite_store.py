"""Private cached results, conditional admission, and conservative spending guard."""
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import lru_cache
from botocore.exceptions import ClientError
from satellite_geometry import parse_dataset_id, parse_job_id, tile_from_id


class Conflict(RuntimeError):
    pass


class MissingResult(RuntimeError):
    pass


class ExpiredResult(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    pass


@lru_cache(maxsize=1)
def billing_client():
    import boto3
    from botocore.config import Config
    return boto3.client('ce', region_name='us-east-1', config=Config(
        connect_timeout=3, read_timeout=5,
        retries={'total_max_attempts': 2, 'mode': 'standard'}))


def reported_cost(now):
    # AWS bills in UTC. Require verifiable costs; never assume unavailable is zero.
    now = now.astimezone(timezone.utc)
    data = billing_client().get_cost_and_usage(
        TimePeriod={'Start': now.strftime('%Y-%m-01'),
                    'End': (now+timedelta(days=1)).strftime('%Y-%m-%d')},
        Granularity='MONTHLY', Metrics=['UnblendedCost'],
        Filter={'Not': {'Dimensions': {'Key': 'RECORD_TYPE', 'Values': ['Credit', 'Refund']}}})
    periods = data.get('ResultsByTime', [])
    if not periods or data.get('NextPageToken'):
        raise RuntimeError('Billing data is unavailable')
    amounts = [p['Total']['UnblendedCost'] for p in periods]
    if any(a['Unit'] != 'USD' for a in amounts):
        raise RuntimeError('Unsupported billing currency')
    amount = sum((Decimal(a['Amount']) for a in amounts), Decimal(0))
    if not amount.is_finite() or amount < 0:
        raise RuntimeError('Invalid billing amount')
    return amount


class SatelliteStore:
    def __init__(self, client, bucket: str, billing=reported_cost):
        self.client, self.bucket, self.billing = client, bucket, billing

    def _read(self, key):
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as error:
            if error.response['Error']['Code'] in ('NoSuchKey', '404'):
                return None
            raise
        with response['Body'] as stream:
            raw = stream.read(1000001)
        if len(raw) > 1000000:
            raise ValueError('Cached satellite object is too large')
        return {'body': json.loads(raw), 'etag': response['ETag']}

    def _put(self, key, body, previous=None):
        raw = json.dumps(body, allow_nan=False, separators=(',', ':')).encode()
        if len(raw) > 1000000:
            raise ValueError('Satellite result is too large')
        condition = {'IfMatch': previous['etag']} if previous else {'IfNoneMatch': '*'}
        try:
            response = self.client.put_object(Bucket=self.bucket, Key=key, Body=raw,
                ContentType='application/json', ServerSideEncryption='AES256', **condition)
        except ClientError as error:
            if error.response['Error']['Code'] in ('PreconditionFailed', 'ConditionalRequestConflict', '409', '412'):
                raise Conflict('Satellite state changed') from error
            raise
        return {'body': body, 'etag': response['ETag']}

    def read_state(self, tile_id):
        tile_from_id(tile_id)
        return self._read(f'states/{tile_id}.json')

    def acquire(self, owner: str, now: datetime):
        current = self._read('admission/global.json')
        if current and current['body']['expiresAt'] > now.timestamp():
            return None
        month = now.astimezone(timezone.utc).strftime('%Y-%m')
        count = current['body'].get('reservedJobs', 0) if current and current['body'].get('month') == month else 0
        if current and current['body'].get('month') == month and current['body'].get('budgetStopped'):
            raise BudgetExceeded('Processing stopped to protect the $10 AWS limit')
        if count+2 >= 10:
            raise BudgetExceeded('Processing stopped to protect the $10 AWS limit')
        cost = self.billing(now)
        # Count every admitted generation, even failed work, to cover billing lag.
        if cost + Decimal(count+1) + Decimal(1) >= Decimal(10):
            try:
                self._put('admission/global.json', {'owner':'','expiresAt':0,'month':month,
                    'reservedJobs':count,'reportedUsd':str(cost),'budgetStopped':True},current)
            except Conflict:
                pass
            raise BudgetExceeded('Processing stopped to protect the $10 AWS limit')
        body = {'owner': owner, 'expiresAt': now.timestamp()+420, 'month': month,
                'reservedJobs': count+1, 'reportedUsd': str(cost)}
        try:
            return self._put('admission/global.json', body, current)
        except Conflict:
            return None

    def release(self, lease: dict) -> bool:
        body = dict(lease['body'], owner='', expiresAt=0)
        try:
            self._put('admission/global.json', body, lease)
            return True
        except Conflict:
            return False

    def create_job(self, tile, generation, now, carry=None):
        job_id = tile['id']+'.'+generation
        parse_job_id(job_id)
        previous = self.read_state(tile['id'])
        if previous and previous['body']['status'] in ('queued', 'processing') and previous['body']['leaseExpiresAt'] > now.timestamp():
            raise Conflict('This satellite job is already pending')
        body = {'jobId': job_id, 'tile': tile, 'generation': generation,
                'status': 'queued', 'createdAt': now.timestamp(),
                'leaseExpiresAt': now.timestamp()+420, 'resultId': None,
                'fieldStatus': {f: {'status': 'pending'} for f in ('ndvi', 'tempC')}}
        if carry:
            body['carry'] = carry
            for field, status in carry['fieldStatus'].items():
                if status['status'] in ('ready', 'no_data') and status.get('expiresAt', 0) > now.timestamp():
                    body['fieldStatus'][field] = status
        return self._put(f'states/{tile["id"]}.json', body, previous)

    def claim_worker(self, job_id, now):
        tile_id, _ = parse_job_id(job_id)
        current, admission = self.read_state(tile_id), self._read('admission/global.json')
        if not current or not admission:
            return None
        body = current['body']
        if (body['jobId'] != job_id or body['status'] != 'queued' or
            body['leaseExpiresAt'] <= now.timestamp() or
            admission['body']['owner'] != job_id or admission['body']['expiresAt'] <= now.timestamp()):
            return None
        try:
            claimed = self._put(f'states/{tile_id}.json', dict(body, status='processing'), current)
            return dict(claimed, lease=admission)
        except Conflict:
            return None

    def publish(self, job_id, revision, result, terminal_status, now):
        tile_id, _ = parse_job_id(job_id)
        dataset_id = job_id+'.'+revision
        parse_dataset_id(dataset_id)
        current = self.read_state(tile_id)
        if not current or current['body']['jobId'] != job_id or current['body']['status'] != 'processing' or current['body']['leaseExpiresAt'] <= now.timestamp():
            return False
        result = dict(result, datasetId=dataset_id)
        key = 'results/'+dataset_id.replace('.', '/')+'.json'
        try:
            self._put(key, result)
            body = dict(current['body'], status=terminal_status, resultId=dataset_id,
                        fieldStatus=result['fieldStatus'], completedAt=now.timestamp())
            body.pop('carry', None)
            self._put(f'states/{tile_id}.json', body, current)
            return True
        except Conflict:
            return False

    def read_result(self, dataset_id, now):
        parse_dataset_id(dataset_id)
        stored = self._read('results/'+dataset_id.replace('.', '/')+'.json')
        if not stored:
            raise MissingResult('Satellite result is unavailable')
        result = stored['body']
        if result['metadata']['expiresAt'] <= now.timestamp():
            raise ExpiredResult('Satellite result has expired. Retry processing.')
        return result

    def fail_job(self, job_id, now, reason='Unable to start satellite processing'):
        tile_id, _ = parse_job_id(job_id)
        current = self.read_state(tile_id)
        if current and current['body']['jobId'] == job_id:
            fields = {f: {'status': 'error', 'reason': reason, 'retryAfterAt': now.timestamp()+60} for f in ('ndvi', 'tempC')}
            try:
                self._put(f'states/{tile_id}.json', dict(current['body'], status='error', fieldStatus=fields), current)
            except Conflict:
                pass

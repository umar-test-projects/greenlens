"""Start, poll, and explicitly retry server-owned satellite neighborhoods."""
import json
import math
import os
import uuid
from satellite_geometry import tile_for_location, parse_job_id
from satellite_store import BudgetExceeded, Conflict, ExpiredResult, MissingResult


def error(status, code, message, retry=0):
    body = {'error': {'code': code, 'message': message}, 'retryAfterSeconds': retry}
    return status, body, {'Retry-After': str(retry)} if retry else {}


def validate_request(body):
    if not isinstance(body, dict) or set(body)-{'lat', 'lng', 'jobId', 'retryFailed'}:
        raise ValueError('Provide coordinates and an optional job ID or retry flag')
    tile = tile_for_location(body.get('lat'), body.get('lng'))
    if 'retryFailed' in body and type(body['retryFailed']) is not bool:
        raise ValueError('Invalid retry flag')
    if 'jobId' in body:
        if 'retryFailed' in body or parse_job_id(body['jobId'])[0] != tile['id']:
            raise ValueError('Job does not match the requested neighborhood')
    return tile


def public_state(state, store, now):
    body = {'jobId': state['jobId'], 'datasetId': None, 'status': state['status'],
            'retryAfterSeconds': 3 if state['status'] in ('queued', 'processing') else 0,
            'fieldStatus': state['fieldStatus']}
    if state.get('resultId'):
        try:
            result = store.read_result(state['resultId'], now)
            body.update(datasetId=result['datasetId'], grid=result['grid'], metadata=result['metadata'])
        except (ExpiredResult, MissingResult):
            pass
    return body


def handle(body: dict, store, lambda_client, now):
    try:
        tile = validate_request(body)
    except (ValueError, TypeError):
        return error(400, 'INVALID_REQUEST', 'Provide valid GPS coordinates and a matching job ID or boolean retry flag.')
    stored = store.read_state(tile['id'])
    carry = None
    if stored:
        state = stored['body']
        if 'jobId' in body and body['jobId'] != state['jobId']:
            return error(503, 'JOB_CHANGED', 'A newer neighborhood result is available. Retry loading.')
        pending = state['status'] in ('queued', 'processing')
        if pending and state['leaseExpiresAt'] > now.timestamp():
            return 202, public_state(state, store, now), {'Retry-After': '3'}
        if pending:
            if 'jobId' in body or not body.get('retryFailed'):
                return error(503, 'JOB_EXPIRED', 'Satellite processing timed out. Retry processing.')
        if state.get('resultId'):
            try:
                carry = store.read_result(state['resultId'], now)
            except (ExpiredResult, MissingResult):
                pass
        if not pending:
            failed = any(f['status'] == 'error' for f in state['fieldStatus'].values())
            if failed:
                cooldown = max((f.get('retryAfterAt', 0) for f in state['fieldStatus'].values()), default=0)
                retry = max(0, math.ceil(cooldown-now.timestamp()))
                if not body.get('retryFailed') or retry:
                    if carry and state['status'] == 'partial' and not body.get('retryFailed'):
                        return 200, public_state(state, store, now), {}
                    return error(503, 'PROCESSING_FAILED', 'Satellite processing could not complete. Retry processing.', retry)
            elif carry:
                return 200, public_state(state, store, now), {}
            if 'jobId' in body:
                return error(503, 'RESULT_EXPIRED', 'The dated satellite result has expired. Reload the neighborhood.')
    elif 'jobId' in body:
        return error(503, 'JOB_UNAVAILABLE', 'This satellite job is unavailable. Retry loading.')
    generation = uuid.uuid4().hex
    job_id = tile['id']+'.'+generation
    try:
        lease = store.acquire(job_id, now)
    except BudgetExceeded:
        return error(503, 'BUDGET_LIMIT', 'New satellite processing is stopped to protect the $10 AWS limit.')
    if not lease:
        return error(429, 'PROCESSING_BUSY', 'Satellite processing is busy. Waiting for capacity.', 15)
    try:
        created = store.create_job(tile, generation, now, carry=carry)
    except Conflict:
        store.release(lease)
        winner = store.read_state(tile['id'])
        return 202, public_state(winner['body'], store, now), {'Retry-After': '3'}
    try:
        invocation = lambda_client.invoke(FunctionName=os.environ.get('PROCESSOR_FUNCTION', 'satellite-worker'),
            InvocationType='Event', Payload=json.dumps({'jobId': job_id}).encode())
        if invocation.get('StatusCode') != 202:
            raise RuntimeError('Worker invocation was not accepted')
    except Exception:
        store.fail_job(job_id, now)
        store.release(lease)
        return error(503, 'PROCESSING_FAILED', 'Unable to start satellite processing. Retry shortly.', 60)
    return 202, public_state(created['body'], store, now), {'Retry-After': '3'}

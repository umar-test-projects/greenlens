"""Idempotent background worker; publish each completed field independently."""
import logging
import os
import time
from datetime import datetime, timezone
from satellite_geometry import build_cells, transformers
from satellite_store import SatelliteStore
from satellite_rasters import process_field


def make_result(tile, fields, now):
    cells = build_cells(tile)
    provenance, statuses = [], {}
    for field in ('ndvi', 'tempC'):
        output = fields.get(field, {'values': [None]*400, 'fieldStatus': {'status': 'processing'}})
        if len(output['values']) != 400:
            raise ValueError('Incorrect satellite cell count')
        for cell, value in zip(cells, output['values']):
            cell[field] = value
        statuses[field] = output['fieldStatus']
        if output.get('provenance'):
            provenance.append(output['provenance'])
    expiries = [s['expiresAt'] for s in statuses.values() if s.get('expiresAt')]
    lng, lat = transformers(tile['epsg'])[1].transform(tile['center']['x'], tile['center']['y'])
    metadata = {'source': 'satellite', 'area': {'name': 'GPS neighborhood', 'center': {'lat': lat, 'lng': lng}},
                'generatedAt': now.isoformat(), 'expiresAt': min(expiries) if expiries else now.timestamp()+60,
                'provenance': provenance, 'fieldStatus': statuses,
                'validCells': {field: sum(c[field] is not None for c in cells) for field in statuses},
                'caveats': ['Dated satellite observations, not live weather.',
                            'Surface temperature is not air temperature; NDVI is not canopy percentage.',
                            'Different layers and RGB imagery may have different acquisition dates.']}
    return {'grid': {**tile, 'cells': cells}, 'metadata': metadata, 'fieldStatus': statuses}


def run_job(event, store, process, now, deadline):
    job_id = event['jobId']
    claimed = store.claim_worker(job_id, now())
    if not claimed:
        return {'status': 'ignored'}
    state, fields = claimed['body'], {}
    carry = state.get('carry')
    try:
        for field in ('ndvi', 'tempC'):
            saved = carry['fieldStatus'].get(field) if carry else None
            if saved and saved['status'] in ('ready', 'no_data') and saved['expiresAt'] > now().timestamp():
                fields[field] = {'values': [c[field] for c in carry['grid']['cells']], 'fieldStatus': saved}
                source = next((p for p in carry['metadata']['provenance'] if p['field'] == field), None)
                if source:
                    fields[field]['provenance'] = source
            else:
                fields[field] = process(field, state['tile'], deadline)
            if field == 'ndvi':
                if not store.publish(job_id, 'ndvi', make_result(state['tile'], fields, now()), 'processing', now()):
                    return {'status': 'ignored'}
        statuses = [fields[f]['fieldStatus']['status'] for f in ('ndvi', 'tempC')]
        status = ('partial' if 'ready' in statuses else 'error') if 'error' in statuses else 'no_data' if all(s == 'no_data' for s in statuses) else 'ready'
        if not store.publish(job_id, 'final', make_result(state['tile'], fields, now()), status, now()):
            return {'status': 'ignored'}
        return {'status': status}
    except Exception as error:
        logging.getLogger(__name__).warning('Satellite worker failed: %s', type(error).__name__)
        store.fail_job(job_id, now(), 'Processing was interrupted. Retry shortly.')
        return {'status': 'error'}
    finally:
        store.release(claimed['lease'])


def handler(event, context):
    import boto3
    from botocore.config import Config
    client = boto3.client('s3', config=Config(connect_timeout=3, read_timeout=5,
        retries={'total_max_attempts': 2, 'mode': 'standard'}))
    store = SatelliteStore(client, os.environ['PROCESSING_BUCKET'])
    remaining = min(300, context.get_remaining_time_in_millis()/1000)
    return run_job(event, store, process_field, lambda: datetime.now(timezone.utc),
                   time.monotonic()+max(0, remaining-20))

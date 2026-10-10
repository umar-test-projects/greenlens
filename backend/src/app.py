"""API Gateway HTTP API / SAM Lambda entrypoint."""
import base64
import json
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from data_store import load_data, get_client
from service import DataTools, validate_query, summarize_query
from satellite_store import SatelliteStore, ExpiredResult, MissingResult
import satellite_api


def utcnow():
    return datetime.now(timezone.utc)


@lru_cache(maxsize=1)
def get_processing_store():
    return SatelliteStore(get_client(), os.environ['PROCESSING_BUCKET'])


@lru_cache(maxsize=1)
def get_lambda_client():
    import boto3
    from botocore.config import Config
    return boto3.client('lambda', config=Config(connect_timeout=3, read_timeout=5,
        retries={'total_max_attempts': 2, 'mode': 'standard'}))


def response(status, body, headers=None):
    return {'statusCode':status, 'headers':{'Content-Type':'application/json',
            'Cache-Control':'no-store', **(headers or {})}, 'body':json.dumps(body,allow_nan=False)}


def handler(event, context):
    satellite_request = event.get('routeKey') == 'POST /satellite' or event.get('rawPath') == '/satellite' or event.get('path') == '/satellite'
    try:
        raw=event.get('body') or ''
        if not isinstance(raw,str) or len(raw)>8192:
            raise ValueError('Request too large')
        if event.get('isBase64Encoded'):
            raw=base64.b64decode(raw,validate=True).decode('utf-8')
        if len(raw)>8192:
            raise ValueError('Request too large')
        body=json.loads(raw)
        if satellite_request:
            satellite_api.validate_request(body)
        else:
            query=validate_query(body)
    except (ValueError,TypeError,UnicodeError):
        message=('Provide valid GPS coordinates and a matching job ID or boolean retry flag.' if satellite_request else 'Provide valid lat, lng, heading and a question of 1–1000 characters.')
        return response(400,{'error':{'code':'INVALID_REQUEST','message':message}})
    try:
        if satellite_request:
            status,result,headers=satellite_api.handle(body,get_processing_store(),get_lambda_client(),utcnow())
            return response(status,result,headers)
        if query.get('datasetId'):
            result=get_processing_store().read_result(query['datasetId'],utcnow())
            grid,metadata=result['grid'],result['metadata']
        else:
            grid,metadata=load_data()
        tools=DataTools(grid,metadata,query['lat'],query['lng'])
        covered=tools.nearest() is not None
        layers={'source':'satellite','status':'ok' if covered else 'no_data',
                'grid':dict(grid,cells=grid['cells'] if covered else []),
                'provenance':metadata['provenance']}
        if not covered:
            text=('No measured coverage at this point in the selected GPS neighborhood.' if query.get('datasetId') else 'No satellite data at this location. Select the Aliganj snapshot to explore the demo area.')
            return response(200,{'layers':layers,'answer':{'text':text,'mode':'data_summary','citations':[],'toolsUsed':[]},'scenario':None})
        answer,scenario=summarize_query(query,tools)
        return response(200,{'layers':layers,'answer':answer,'scenario':scenario})
    except (ExpiredResult,MissingResult):
        return response(503,{'error':{'code':'DATASET_UNAVAILABLE','message':'This satellite result is unavailable or expired. Reload measurements.'}})
    except Exception as error:
        # No question, precise coordinates, credentials, or provider response in logs.
        logging.getLogger(__name__).warning('Query failed: %s',type(error).__name__)
        return response(503,{'error':{'code':'SERVICE_UNAVAILABLE','message':'The data service is unavailable. Your satellite overlay is still available; try again shortly.'}})

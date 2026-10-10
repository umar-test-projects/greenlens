import json
import os
from functools import lru_cache


@lru_cache(maxsize=1)
def get_client():
    """Reuse the S3 client within this Lambda environment."""
    import boto3
    from botocore.config import Config
    return boto3.client('s3',region_name=os.getenv('AWS_REGION','ap-south-1'),
                        config=Config(connect_timeout=3,read_timeout=5,
                                      retries={'total_max_attempts':2,'mode':'adaptive'}))


@lru_cache(maxsize=1)
def load_data():
    """Read only the two configured S3 keys, cached for this Lambda environment."""
    client=get_client()
    bucket=os.environ['DATA_BUCKET']
    values=[]
    for key in ('data/grid.json','data/provenance.json'):
        with client.get_object(Bucket=bucket,Key=key)['Body'] as body:
            data=body.read(1_000_001)
            if len(data)>1_000_000:
                raise ValueError('Dataset too large')
            values.append(json.loads(data))
    grid,metadata=values
    if metadata.get('source')!='satellite' or not isinstance(grid.get('cells'),list):
        raise ValueError('Invalid satellite data')
    return grid,metadata

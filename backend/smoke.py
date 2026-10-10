"""Read the private S3 grid and print one deterministic summary; S3 reads can cost money."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from app import handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--question',default='Why is this block hotter?')
    args=parser.parse_args()
    os.environ.setdefault('AWS_REGION','ap-south-1')
    os.environ.setdefault('DATA_BUCKET','greenlens-data-636993911888-ap-south-1')
    event=json.loads((Path(__file__).parent/'events/query.json').read_text())
    body=json.loads(event['body']);body['question']=args.question
    event['body']=json.dumps(body)
    start=time.monotonic()
    result=handler(event,None)
    payload=json.loads(result['body'])
    print(json.dumps({'statusCode':result['statusCode'],'seconds':round(time.monotonic()-start,2),
                      'answer':payload.get('answer'),'scenario':payload.get('scenario'),
                      'error':payload.get('error')},indent=2,ensure_ascii=True))
    return 0 if result['statusCode']==200 else 1


if __name__=='__main__':
    sys.exit(main())

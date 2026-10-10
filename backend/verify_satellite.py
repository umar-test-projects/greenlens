"""Check a public landmark's live job, immutable measurements and cached replay."""
import argparse
import json
import time
from pathlib import Path
from verify_deployed import request


def check_citations(result, answer):
    for citation in answer['citations']:
        cell = next((c for c in result['grid']['cells'] if c['lat'] == citation['lat'] and c['lng'] == citation['lng']), None)
        assert cell is not None and cell[citation['field']] is not None
        assert cell[citation['field']] == citation['value'], 'Citation value changed'
        source = next(p for p in result['metadata']['provenance'] if p['field'] == citation['field'])
        assert citation['sceneId'] == source['sceneId'], 'Citation scene changed'
        assert citation['acquiredAt'] == source['acquiredAt'], 'Citation acquisition date changed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('satellite_url')
    parser.add_argument('query_url')
    parser.add_argument('--origin', required=True)
    parser.add_argument('--lat', type=float, default=12.9767)
    parser.add_argument('--lng', type=float, default=77.5929)
    parser.add_argument('--output', default='.aws-sam/satellite-result.json')
    args = parser.parse_args()
    anchor = {'lat': args.lat, 'lng': args.lng}
    payload, started, revisions = anchor, time.monotonic(), []
    while time.monotonic()-started < 480:
        status, headers, body, _ = request(args.satellite_url, 'POST', payload, {'Origin': args.origin})
        assert headers.get('Access-Control-Allow-Origin') == args.origin, 'Processing CORS mismatch'
        if status == 429:
            time.sleep(max(15, int(headers.get('Retry-After', '15'))))
            continue
        assert status in (200, 202), f'Processing HTTP {status}: {body.get("error", {}).get("code")}'
        if body.get('datasetId') and body['datasetId'] not in revisions:
            revisions.append(body['datasetId'])
            Path(args.output).write_text(json.dumps(body), encoding='utf-8')
            print('Published revision:', body['datasetId'], flush=True)
        if status == 200:
            break
        payload = {**anchor, 'jobId': body['jobId']}
        time.sleep(max(3, body.get('retryAfterSeconds', 3)))
    else:
        raise AssertionError('Satellite processing timed out')
    assert body['grid']['cells'] and len(body['grid']['cells']) == 400
    result = body
    time.sleep(1.2)
    status, _, cached, _ = request(args.satellite_url, 'POST', anchor, {'Origin': args.origin})
    assert status == 200 and cached['jobId'] == result['jobId'] and cached['datasetId'] == result['datasetId'], 'Cached replay started another generation'
    available = [c for c in result['grid']['cells'] if c['ndvi'] is not None or c['tempC'] is not None]
    paired = [c for c in available if c['ndvi'] is not None and c['tempC'] is not None]
    selected = min(paired or available, key=lambda c: (c['lat']-anchor['lat'])**2+(c['lng']-anchor['lng'])**2) if available else None
    summary_anchor = {'lat': selected['lat'], 'lng': selected['lng']} if selected else anchor
    checks = []
    for question in ('What are the temperature and NDVI here?', 'How does this cell compare with nearby cells?', 'Where should we plant trees here?'):
        time.sleep(1.2)
        status, _, answer, _ = request(args.query_url, 'POST', {**summary_anchor, 'heading': 0, 'question': question, 'datasetId': result['datasetId']}, {'Origin': args.origin})
        assert status == 200, 'Measured summary unavailable'
        check_citations(result, answer['answer'])
        if selected and question.startswith('What are'):
            assert {c['field'] for c in answer['answer']['citations']} == {f for f in ('ndvi', 'tempC') if selected[f] is not None}, 'Local summary omitted an available measurement'
        checks.append({'question': question, 'citations': len(answer['answer']['citations'])})
    print(json.dumps({'result': 'PASS', 'seconds': round(time.monotonic()-started, 2),
        'datasetId': result['datasetId'], 'revisionsObserved': revisions,
        'fieldStatus': result['fieldStatus'], 'validCells': result['metadata']['validCells'],
        'sources': [{k: p[k] for k in ('field', 'sceneId', 'acquiredAt')} for p in result['metadata']['provenance']],
        'cacheReplay': True, 'summaries': checks}, indent=2))


if __name__ == '__main__':
    main()

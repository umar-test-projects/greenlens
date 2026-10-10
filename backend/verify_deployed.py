"""Verify the deployed HTTP API with measured fixtures; makes billable API requests."""
import argparse
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request(url, method, body=None, headers=None):
    encoded = json.dumps(body).encode() if body is not None else None
    options = dict(headers or {})
    if encoded is not None:
        options['Content-Type'] = 'application/json'
    started = time.monotonic()
    req = Request(url, data=encoded, headers=options, method=method)
    try:
        response = urlopen(req, timeout=35)
    except HTTPError as error:
        response = error
    with response:
        data = response.read()
        return response.status, response.headers, json.loads(data) if data else None, round(time.monotonic() - started, 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('--origin', default='http://localhost:5173')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    grid = json.loads((root / 'public/data/grid.json').read_text())
    provenance = json.loads((root / 'public/data/provenance.json').read_text())
    report = []

    for origin, allowed in ((args.origin, True), ('https://unrelated.example', False)):
        status, headers, _, elapsed = request(args.url, 'OPTIONS', headers={
            'Origin': origin, 'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'content-type'})
        assert status == 204, f'Preflight HTTP {status}'
        if allowed:
            assert headers.get('Access-Control-Allow-Origin') == origin
            assert 'POST' in headers.get('Access-Control-Allow-Methods', '')
            assert 'content-type' in headers.get('Access-Control-Allow-Headers', '').lower()
        else:
            assert not headers.get('Access-Control-Allow-Origin')
        report.append({'check': 'allowed CORS' if allowed else 'unrelated origin excluded', 'status': status, 'seconds': elapsed})
        time.sleep(1.2)

    base = {'lat': 26.8879107, 'lng': 80.9494493, 'heading': 0}
    summaries = (
        ('local conditions', 'What are the temperature and NDVI here?'),
        ('nearby comparison', 'How does this cell compare with nearby cells?'),
        ('planting survey', 'Where should we plant trees here?'),
    )
    for label, question in summaries:
        status, headers, body, elapsed = request(args.url, 'POST', {**base, 'question': question}, {'Origin': args.origin})
        assert status == 200, f'{label}: HTTP {status}: {body}'
        assert headers.get('Access-Control-Allow-Origin') == args.origin
        assert body['layers']['source'] == 'satellite'
        assert body['layers']['status'] == 'ok'
        assert body['layers']['grid'] == grid, 'Frontend/API grid mismatch'
        assert body['layers']['provenance'] == provenance['provenance']
        answer = body['answer']
        assert answer['mode'] == 'data_summary'
        assert answer['text'] and answer['citations']
        for citation in answer['citations']:
            cell = next(c for c in grid['cells'] if c['lat'] == citation['lat'] and c['lng'] == citation['lng'])
            assert cell[citation['field']] == citation['value'], 'Citation does not match measured cell'
        report.append({'check': label, 'status': status, 'citations': len(answer['citations']), 'seconds': elapsed})
        time.sleep(1.2)

    status, _, body, elapsed = request(args.url, 'POST', {**base, 'lat': 0, 'lng': 0, 'question': summaries[0][1]})
    assert status == 200 and body['layers']['status'] == 'no_data'
    assert body['layers']['grid']['cells'] == [] and body['answer']['citations'] == []
    report.append({'check': 'outside coverage', 'status': status, 'seconds': elapsed})
    time.sleep(1.2)
    status, _, body, elapsed = request(args.url, 'POST', {'lat': True})
    assert status == 400 and body['error']['code'] == 'INVALID_REQUEST'
    report.append({'check': 'invalid input', 'status': status, 'seconds': elapsed})
    print(json.dumps({'result': 'PASS', 'checks': report}, indent=2))


if __name__ == '__main__':
    main()

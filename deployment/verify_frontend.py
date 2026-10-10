"""Check published frontend bytes and security headers against the local Vite build."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site_url')
    args = parser.parse_args()
    site = args.site_url.rstrip('/')
    assert site.startswith('https://'), 'Public frontend must use HTTPS'
    root = Path(__file__).resolve().parent.parent / 'dist'
    checked = []
    for local in sorted(root.rglob('*')):
        if not local.is_file():
            continue
        path = local.relative_to(root).as_posix()
        with urlopen(site + '/' + path, timeout=30) as response:
            remote = response.read()
            assert response.status == 200, f'{path}: HTTP {response.status}'
            assert hashlib.sha256(remote).digest() == hashlib.sha256(local.read_bytes()).digest(), f'{path}: deployed bytes differ'
            assert response.headers.get('X-Content-Type-Options') == 'nosniff'
            assert response.headers.get('X-Frame-Options') == 'DENY'
            assert 'microphone=()' in response.headers.get('Permissions-Policy', '')
            csp=response.headers.get('Content-Security-Policy','')
            assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp
            assert "object-src 'none'" in csp and "base-uri 'none'" in csp
            assert "script-src 'self' 'wasm-unsafe-eval'" in csp and "'unsafe-eval'" not in csp
            assert 'https://api.open-meteo.com' in csp and "worker-src 'self' blob:" in csp
            checked.append(path)
    with urlopen(site + '/', timeout=30) as response:
        assert response.status == 200
        assert response.read() == (root / 'index.html').read_bytes()
        assert "frame-ancestors 'none'" in response.headers.get('Content-Security-Policy','')
        assert 'max-age=0' in response.headers.get('Cache-Control','')
    for path in ('/assets/does-not-exist.js', '/.env.production.local'):
        try:
            with urlopen(site + path, timeout=30) as response:
                raise AssertionError(f'{path}: unexpected HTTP {response.status}')
        except HTTPError as error:
            assert error.code == 404, f'{path}: expected 404, got {error.code}'
    req = Request(site.replace('https://', 'http://', 1) + '/', method='HEAD')
    with urlopen(req, timeout=30) as response:
        assert response.geturl().startswith(site + '/'), 'HTTP did not redirect to HTTPS'
    print(json.dumps({'result': 'PASS', 'site': site, 'matchingFiles': len(checked),
                      'paths': checked, 'root': '200', 'missingAssets': '404',
                      'http': 'redirects to HTTPS', 'securityHeaders': 'present'}, indent=2))


if __name__ == '__main__':
    main()

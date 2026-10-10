"""Independently check official source windows; no worker calculation imports."""
import argparse
import json
import os
from urllib.request import Request, urlopen
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT


def calculate(field, arrays, assets):
    if field == 'ndvi':
        red, nir, scl = arrays['red'], arrays['nir'], arrays['scl']
        rmeta, nmeta = assets['red']['raster:bands'][0], assets['nir']['raster:bands'][0]
        r = red.astype('float64')*rmeta['scale']+rmeta.get('offset', 0)
        n = nir.astype('float64')*nmeta['scale']+nmeta.get('offset', 0)
        valid = np.isin(scl, [4, 5, 6]) & (red > 0) & (nir > 0) & (r >= 0) & (n >= 0) & (n+r > 0)
        values = np.divide(n-r, n+r, out=np.full(r.shape, np.nan), where=valid)
        valid &= np.isfinite(values) & (values >= -1) & (values <= 1)
    else:
        dn, qa, saturated = arrays['lwir11'], arrays['qa_pixel'], arrays['qa_radsat']
        valid = (dn > 0) & ((qa.astype('uint32') & 0b111111) == 0) & (saturated == 0)
        values = dn.astype('float64')*0.00341802+149-273.15
    return round(float(np.mean(values[valid])), 4) if np.count_nonzero(valid) >= 50 else None


def read_cell(href, grid, cell, paid):
    west, _, _, north = grid['bounds']
    transform = from_origin(west+cell['column']*100, north-cell['row']*100, 10, 10)
    settings = {'GDAL_DISABLE_READDIR_ON_OPEN': 'EMPTY_DIR', 'CPL_VSIL_CURL_ALLOWED_EXTENSIONS': '.tif,.TIF',
        'GDAL_HTTP_TIMEOUT': '20', 'GDAL_HTTP_CONNECTTIMEOUT': '5', 'GDAL_HTTP_MAX_RETRY': '0', 'GDAL_CACHEMAX': 64*1024*1024}
    if paid:
        settings.update(AWS_REQUEST_PAYER='requester', AWS_REGION='us-west-2')
    with rasterio.Env(**settings), rasterio.open(href) as source:
        with WarpedVRT(source, crs=f'EPSG:{grid["epsg"]}', transform=transform,
                width=10, height=10, resampling=Resampling.nearest,
                nodata=source.nodata if source.nodata is not None else 65535) as vrt:
            return vrt.read(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result_json')
    parser.add_argument('--scenes-json', help='Previously fetched official STAC records keyed by field')
    args = parser.parse_args()
    result = json.load(open(args.result_json, encoding='utf-8'))
    # The CLI credential process supports the user's existing aws login session.
    if not os.environ.get('AWS_ACCESS_KEY_ID') and any(p['field'] == 'tempC' for p in result['metadata']['provenance']):
        import subprocess
        credential = subprocess.run(['C:/Program Files/Amazon/AWSCLIV2/aws.exe', 'configure', 'export-credentials', '--format', 'process'], capture_output=True, check=True, text=True)
        values = json.loads(credential.stdout)
        for target, key in [('AWS_ACCESS_KEY_ID', 'AccessKeyId'), ('AWS_SECRET_ACCESS_KEY', 'SecretAccessKey'), ('AWS_SESSION_TOKEN', 'SessionToken')]:
            os.environ[target] = values[key]
    checks = []
    for source in result['metadata']['provenance']:
        field = source['field']
        print('Checking official source window:', field, flush=True)
        cell = next(c for c in result['grid']['cells'] if c[field] is not None)
        if args.scenes_json:
            scene = json.load(open(args.scenes_json, encoding='utf-8'))[field]
        else:
            search = Request('https://earth-search.aws.element84.com/v1/search',
                data=json.dumps({'collections': [source['dataset']], 'ids': [source['sceneId']], 'limit': 1}).encode(),
                headers={'Content-Type': 'application/json'}, method='POST')
            with urlopen(search, timeout=20) as response:
                scene = json.loads(response.read(2000000))['features'][0]
        assert scene['id'] == source['sceneId'], 'Source scene mismatch'
        assert scene['properties']['datetime'] == source['acquiredAt'], 'Source date mismatch'
        assert all(scene['assets'][key]['href'] == href for key, href in source['assets'].items()), 'Source asset mismatch'
        arrays = {key: read_cell(href, result['grid'], cell, field == 'tempC') for key, href in source['assets'].items()}
        value = calculate(field, arrays, scene['assets'])
        assert value is not None and abs(value-cell[field]) <= .0001, f'{field}: independent value {value} differs from {cell[field]}'
        checks.append({'field': field, 'cell': [cell['row'], cell['column']], 'value': value, 'sceneId': source['sceneId'], 'acquiredAt': source['acquiredAt']})
        print('Independent value matched:', field, value, flush=True)
    assert checks, 'No measured fields available for independent verification'
    print(json.dumps({'result': 'PASS', 'independentSourceWindows': checks}, indent=2))


if __name__ == '__main__':
    main()

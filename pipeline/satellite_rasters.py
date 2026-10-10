"""Bounded official-source COG reads and masked 100 m satellite measurements."""
import json
import math
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds

SENTINEL_HOSTS = {'sentinel-cogs.s3.us-west-2.amazonaws.com',
                  'e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com'}
FIELDS = {'ndvi': ('sentinel-2-l2a', ('red', 'nir', 'scl')),
          'tempC': ('landsat-c2-l2', ('lwir11', 'qa_pixel', 'qa_radsat'))}


class UnusableScene(ValueError):
    pass


def validate_assets(feature, field):
    keys = FIELDS[field][1]
    assets = feature.get('assets', {})
    if not all(key in assets for key in keys):
        raise UnusableScene('Required source bands are unavailable')
    if field == 'tempC' and not str(feature.get('id', '')).startswith(('LC08_L2SP_', 'LC09_L2SP_')):
        raise UnusableScene('A Landsat 8 or 9 surface-temperature product is required')
    for key in keys:
        uri = urlparse(assets[key]['href'])
        if field == 'ndvi':
            if uri.scheme != 'https' or uri.netloc not in SENTINEL_HOSTS:
                raise UnusableScene('Unsupported Sentinel source')
        elif uri.scheme != 's3' or uri.netloc != 'usgs-landsat' or not uri.path.startswith('/collection02/level-2/standard/oli-tirs/'):
            raise UnusableScene('Unsupported Landsat source')
    return assets


def read_asset(asset: dict, tile: dict, *, paid=False, local=None) -> np.ndarray:
    href = str(local) if local else asset['href']
    if not local:
        uri = urlparse(href)
        allowed = uri.scheme == 'https' and uri.netloc in SENTINEL_HOSTS
        allowed_paid = paid and uri.scheme == 's3' and uri.netloc == 'usgs-landsat' and uri.path.startswith('/collection02/level-2/standard/oli-tirs/')
        if not (allowed or allowed_paid):
            raise UnusableScene('Unsupported raster asset')
    options = {'GDAL_DISABLE_READDIR_ON_OPEN': 'EMPTY_DIR', 'GDAL_HTTP_TIMEOUT': 20,
               'GDAL_HTTP_CONNECTTIMEOUT': 5, 'GDAL_HTTP_MAX_RETRY': 1,
               'GDAL_HTTP_RETRY_DELAY': 1, 'CPL_VSIL_CURL_ALLOWED_EXTENSIONS': '.tif,.TIF',
               'GDAL_CACHEMAX': 64*1024*1024, 'VSI_CACHE': False}
    if paid:
        options.update(AWS_REQUEST_PAYER='requester', AWS_REGION='us-west-2')
    west, south, east, north = tile['bounds']
    target_crs = f'EPSG:{tile["epsg"]}'
    with rasterio.Env(**options), rasterio.open(href) as source:
        if not source.crs:
            raise UnusableScene('Raster georeferencing is missing')
        w, s, e, n = transform_bounds(target_crs, source.crs, west, south, east, north, densify_pts=21)
        bounds = source.bounds
        if w < bounds.left-.001 or s < bounds.bottom-.001 or e > bounds.right+.001 or n > bounds.top+.001:
            raise UnusableScene('Source scene does not cover the complete neighborhood')
        nodata = source.nodata if source.nodata is not None else 65535
        with WarpedVRT(source, crs=target_crs, transform=from_origin(west, north, 10, 10),
                       width=200, height=200, resampling=Resampling.nearest, nodata=nodata) as vrt:
            return vrt.read(1)


def aggregate_cells(values):
    if values.shape != (200, 200):
        raise ValueError('Expected a 200 by 200 working raster')
    blocks = values.reshape(20, 10, 20, 10).transpose(0, 2, 1, 3).reshape(400, 100)
    valid = np.isfinite(blocks)
    counts = valid.sum(axis=1)
    totals = np.where(valid, blocks, 0).sum(axis=1)
    means = np.divide(totals, counts, out=np.zeros(400), where=counts > 0)
    return [round(float(value), 4) if count >= 50 else None for value, count in zip(means, counts)]


def reflectance(dn, metadata):
    scale, offset = metadata.get('scale'), metadata.get('offset', 0)
    if type(scale) not in (int, float) or type(offset) not in (int, float) or not math.isfinite(scale) or not math.isfinite(offset) or scale <= 0:
        raise ValueError('Invalid reflectance scaling metadata')
    return dn.astype('float64')*scale+offset


def ndvi_cells(red, nir, scl, red_meta, nir_meta):
    r, n = reflectance(red, red_meta), reflectance(nir, nir_meta)
    valid = np.isin(scl, [4, 5, 6]) & (red > 0) & (nir > 0) & (r >= 0) & (n >= 0) & ((n+r) > 0)
    values = np.full(red.shape, np.nan)
    np.divide(n-r, n+r, out=values, where=valid)
    values[~valid | (values < -1) | (values > 1)] = np.nan
    return aggregate_cells(values)


def temperature_cells(dn, qa, saturation):
    values = dn.astype('float64')*.00341802+149-273.15
    values[(dn <= 0) | ((qa.astype('uint32') & 63) != 0) | (saturation != 0)] = np.nan
    return aggregate_cells(values)


def search_catalog(field, tile):
    end = datetime.now(timezone.utc)
    try:
        start = end.replace(year=end.year-2)
    except ValueError:
        start = end.replace(year=end.year-2, day=28)
    payload = {'collections': [FIELDS[field][0]], 'bbox': tile['bbox'],
               'datetime': f'{start.isoformat()}/{end.isoformat()}', 'limit': 12,
               'sortby': [{'field': 'properties.datetime', 'direction': 'desc'}],
               'query': {'eo:cloud_cover': {'lt': 20}}}
    request = Request('https://earth-search.aws.element84.com/v1/search',
        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(request, timeout=15) as response:
        raw = response.read(2000001)
    if len(raw) > 2000000:
        raise ValueError('Satellite catalog response is too large')
    features = json.loads(raw)['features']
    return sorted(features[:12], key=lambda scene: scene['properties']['datetime'], reverse=True)


def process_field(field: str, tile: dict, deadline: float, *, catalog_search=search_catalog, reader=read_asset):
    keys = FIELDS[field][1]
    errors, attempts = False, 0
    try:
        if time.monotonic() >= deadline:
            raise TimeoutError('Processing deadline')
        features = catalog_search(field, tile)
        for feature in features:
            if attempts >= 4 or time.monotonic() >= deadline:
                if time.monotonic() >= deadline:
                    errors = True
                break
            try:
                assets = validate_assets(feature, field)
            except (UnusableScene, KeyError, TypeError):
                continue
            attempts += 1
            try:
                arrays = {}
                for key in keys:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Processing deadline')
                    arrays[key] = reader(assets[key], tile, paid=field == 'tempC')
                if field == 'ndvi':
                    values = ndvi_cells(arrays['red'], arrays['nir'], arrays['scl'],
                        assets['red']['raster:bands'][0], assets['nir']['raster:bands'][0])
                    processing = 'Per-band STAC scale/offset; NDVI=(NIR-red)/(NIR+red); SCL 4,5,6; 100 m means with >=50% valid 10 m samples.'
                else:
                    values = temperature_cells(arrays['lwir11'], arrays['qa_pixel'], arrays['qa_radsat'])
                    processing = 'ST_B10*0.00341802+149-273.15; QA_PIXEL bits 0-5 clear; QA_RADSAT=0; nearest resampling; >=50% valid samples. Native thermal resolution about 100 m.'
                if not any(value is not None for value in values):
                    continue
                now = datetime.now(timezone.utc)
                return {'values': values, 'fieldStatus': {'status': 'ready',
                        'completedAt': now.timestamp(), 'expiresAt': now.timestamp()+86400},
                        'provenance': {'field': field, 'dataset': FIELDS[field][0],
                        'sceneId': feature['id'], 'acquiredAt': feature['properties']['datetime'],
                        'processing': processing, 'assets': {key: assets[key]['href'] for key in keys}}}
            except UnusableScene:
                continue
            except (OSError, ValueError, KeyError, TimeoutError, RuntimeError):
                errors = True
    except (OSError, ValueError, KeyError, TimeoutError, RuntimeError):
        errors = True
    now = datetime.now(timezone.utc).timestamp()
    status = {'status': 'error' if errors else 'no_data',
              'reason': 'Satellite processing could not complete. Retry shortly.' if errors else 'No clear valid observation was found in the available scenes.',
              'completedAt': now}
    status['retryAfterAt' if errors else 'expiresAt'] = now+(60 if errors else 86400)
    return {'values': [None]*400, 'fieldStatus': status}

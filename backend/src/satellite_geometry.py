"""Canonical metric satellite neighborhoods; no storage or raster dependencies."""
import math
import re
from functools import lru_cache
from pyproj import Transformer

Tile = dict
TILE_PATTERN = r'p1-(326[0-5][0-9]|32660|327[0-5][0-9]|32760)-([0-9]{1,7})-([0-9]{1,8})'
JOB_PATTERN = re.compile(rf'({TILE_PATTERN})\.([a-f0-9]{{32}})')


def valid_number(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


@lru_cache(maxsize=120)
def transformers(epsg):
    return (Transformer.from_crs(4326, epsg, always_xy=True),
            Transformer.from_crs(epsg, 4326, always_xy=True))


def snap_center(value):
    return math.floor(value / 1000 + .5) * 1000


def footprint(epsg, west, south, east, north):
    inverse = transformers(epsg)[1]
    return [list(inverse.transform(x, y)) for x, y in
            [(west, north), (east, north), (east, south), (west, south)]]


def make_tile(epsg, x, y):
    if not (32601 <= epsg <= 32660 or 32701 <= epsg <= 32760):
        raise ValueError('Invalid tile projection')
    if not (0 <= x <= 1000000 and 0 <= y <= 10000000) or x % 1000 or y % 1000:
        raise ValueError('Invalid tile center')
    bounds = [x-1000, y-1000, x+1000, y+1000]
    polygon = footprint(epsg, *bounds)
    longitudes, latitudes = zip(*polygon)
    bbox = [min(longitudes), min(latitudes), max(longitudes), max(latitudes)]
    if bbox[2]-bbox[0] > 180:
        raise ValueError('Satellite processing does not support tiles crossing the date line')
    return {'id': f'p1-{epsg}-{x}-{y}', 'epsg': epsg, 'center': {'x': x, 'y': y},
            'bounds': bounds, 'bbox': bbox, 'footprint': polygon,
            'cellSizeM': 100, 'rows': 20, 'columns': 20}


def tile_for_location(lat: float, lng: float) -> Tile:
    if not valid_number(lat, -80, 84) or not valid_number(lng, -180, 180):
        raise ValueError('Satellite processing requires coordinates between 80 S and 84 N')
    zone = min(60, math.floor((lng+180)/6)+1)
    epsg = (32600 if lat >= 0 else 32700) + zone
    x, y = transformers(epsg)[0].transform(lng, lat)
    return make_tile(epsg, snap_center(x), snap_center(y))


def tile_from_id(tile_id: str) -> Tile:
    match = re.fullmatch(TILE_PATTERN, tile_id) if isinstance(tile_id, str) else None
    if not match:
        raise ValueError('Invalid satellite tile ID')
    tile = make_tile(*(int(part) for part in match.groups()))
    if tile['id'] != tile_id:
        raise ValueError('Noncanonical satellite tile ID')
    return tile


def parse_job_id(value: str):
    match = JOB_PATTERN.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise ValueError('Invalid satellite job ID')
    tile_id, generation = match.group(1), match.group(5)
    tile_from_id(tile_id)
    return tile_id, generation


def parse_dataset_id(value: str) -> tuple[str, str, str]:
    if not isinstance(value, str) or len(value) > 100:
        raise ValueError('Invalid satellite dataset ID')
    job_id, separator, revision = value.rpartition('.')
    if not separator or revision not in ('ndvi', 'final'):
        raise ValueError('Invalid satellite dataset revision')
    return (*parse_job_id(job_id), revision)


def build_cells(tile: Tile) -> list[dict]:
    west, south, east, north = tile['bounds']
    inverse = transformers(tile['epsg'])[1]
    cells = []
    for row in range(20):
        for column in range(20):
            x, y = west+(column+.5)*100, north-(row+.5)*100
            lng, lat = inverse.transform(x, y)
            cells.append({'lat': lat, 'lng': lng, 'row': row, 'column': column,
                          'footprint': footprint(tile['epsg'], x-50, y-50, x+50, y+50),
                          'ndvi': None, 'tempC': None})
    return cells


def cell_index(grid: dict, lat: float, lng: float) -> int | None:
    if not valid_number(lat, -90, 90) or not valid_number(lng, -180, 180):
        return None
    x, y = transformers(grid['epsg'])[0].transform(lng, lat)
    west, south, east, north = grid['bounds']
    tolerance = 1e-6  # projection round-trip error, in metres
    if x < west-tolerance or x > east+tolerance or y < south-tolerance or y > north+tolerance:
        return None
    column = min(19, max(0, math.floor((x-west+tolerance)/100)))
    row = min(19, max(0, math.floor((north-y+tolerance)/100)))
    return row*20+column

"""Offline 100 m grid from windowed AWS Open Data COG reads; no AWS provisioning."""
import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.transform import from_origin
from rasterio.enums import Resampling
from pyproj import Transformer
from processing import ndvi, temperature_c, clear_landsat, aggregate

ROOT = Path(__file__).resolve().parents[1]

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def read_asset(asset, transform, crs, pixels, *, paid=False, local=None):
    href = str(local) if local else asset['href']
    if not local and (href.startswith('s3://') or asset.get('storage:requester_pays')) and not paid:
        raise RuntimeError('Requester Pays blocked. Explicit --requester-pays is required.')
    options = dict(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', GDAL_HTTP_TIMEOUT=30,
                   GDAL_HTTP_MAX_RETRY=2, CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif,.TIF')
    if href.startswith('s3://'):
        options['AWS_REQUEST_PAYER'] = 'requester'
    with rasterio.Env(**options):
        with rasterio.open(href) as dataset:
            # Zero is valid for QA_RADSAT. Reserving it as destination nodata
            # makes GDAL change valid zeros to ones, falsely marking saturation.
            destination_nodata = dataset.nodata if dataset.nodata is not None else 65535
            with WarpedVRT(dataset, crs=crs, transform=transform, width=pixels,
                           height=pixels, resampling=Resampling.nearest, nodata=destination_nodata) as vrt:
                return vrt.read(1)

def build(args):
    area = load(ROOT/'data/area.json')
    item = load(args.sentinel)
    size, cell_size = area['widthM'], area['cellSizeM']
    crs = area['crs']
    forward = Transformer.from_crs('EPSG:4326', crs, always_xy=True)
    inverse = Transformer.from_crs(crs, 'EPSG:4326', always_xy=True)
    x, y = forward.transform(area['center']['lng'], area['center']['lat'])
    west, north = x-size/2, y+size/2
    resolution = 10
    pixels = size//resolution
    transform = from_origin(west, north, resolution, resolution)
    assets = item['assets']
    red = read_asset(assets['red'], transform, crs, pixels)
    nir = read_asset(assets['nir'], transform, crs, pixels)
    scl = read_asset(assets['scl'], transform, crs, pixels)
    rmeta, nmeta = assets['red']['raster:bands'][0], assets['nir']['raster:bands'][0]
    # Handle each band's metadata separately (scale and additive offset matter).
    r = red.astype(float)*rmeta['scale']+rmeta.get('offset',0)
    n = nir.astype(float)*nmeta['scale']+nmeta.get('offset',0)
    valid = np.isin(scl,[4,5,6]) & (red>0) & (nir>0) & (r>=0) & (n>=0) & ((r+n)>0)
    values = np.full(red.shape,np.nan)
    np.divide(n-r,n+r,out=values,where=valid)
    values[~valid | (values < -1) | (values > 1)] = np.nan
    temp = None
    provenance = [{
        'field':'ndvi','dataset':item['collection'],'sceneId':item['id'],
        'acquiredAt':item['properties']['datetime'],
        'processing':'Per-band STAC scale/offset; NDVI=(NIR-red)/(NIR+red); nearest SCL classes 4,5,6; 100 m means with >=50% valid 10 m samples.',
        'assets':{key:assets[key]['href'] for key in ['red','nir','scl']},
        'registry':'https://registry.opendata.aws/sentinel-2-l2a-cogs/'
    }]
    temperature_status = 'Not downloaded: Landsat AWS bucket requires Requester Pays access.'
    if args.requester_pays or args.landsat_dir:
        landsat = load(args.landsat)
        source = landsat['assets']
        arrays = {}
        for key in ['lwir11','qa_pixel','qa_radsat']:
            local = Path(args.landsat_dir)/Path(source[key]['href']).name if args.landsat_dir else None
            arrays[key]=read_asset(source[key],transform,crs,pixels,paid=args.requester_pays,local=local)
        dn,qa,sat = arrays['lwir11'],arrays['qa_pixel'],arrays['qa_radsat']
        print(json.dumps({'landsatQuality': {
            'pixels': int(dn.size), 'temperatureNonzero': int(np.count_nonzero(dn)),
            'qaClear': int(np.count_nonzero((qa.astype('uint32') & 63) == 0)),
            'unsaturated': int(np.count_nonzero(sat == 0)),
            'saturationValues': [int(value) for value in np.unique(sat)]}}))
        temp=dn.astype(float)*.00341802+149-273.15
        temp[(dn==0)|((qa.astype('uint32')&63)!=0)|(sat!=0)]=np.nan
        provenance.append({'field':'tempC','dataset':landsat['collection'],'sceneId':landsat['id'],
                           'acquiredAt':landsat['properties']['datetime'],
                           'processing':'ST_B10*0.00341802+149-273.15; QA_PIXEL bits 0-5 clear and QA_RADSAT=0; nearest resampling; >=50% valid samples per 100 m cell. Native thermal resolution about 100 m.',
                           'assets':{key:source[key]['href'] for key in arrays},
                           'registry':'https://registry.opendata.aws/usgs-landsat/'})
        temperature_status=('Processed Landsat surface temperature, not air temperature.' if np.any(np.isfinite(temp))
                            else 'Landsat scene has no valid temperature pixels in the demo area after masking.')
    cells=[]
    step=cell_size//resolution
    for row in range(size//cell_size):
        for col in range(size//cell_size):
            latlng=inverse.transform(west+(col+.5)*cell_size,north-(row+.5)*cell_size)
            region=np.s_[row*step:(row+1)*step,col*step:(col+1)*step]
            cells.append({'lat':round(latlng[1],7),'lng':round(latlng[0],7),
                          'ndvi':aggregate(values[region].ravel().tolist()),
                          'tempC':aggregate(temp[region].ravel().tolist()) if temp is not None else None})
    corners=[inverse.transform(xx,yy) for xx in [west,west+size] for yy in [north-size,north]]
    bbox=[min(p[0] for p in corners),min(p[1] for p in corners),max(p[0] for p in corners),max(p[1] for p in corners)]
    grid={'bbox':bbox,'cellSizeM':cell_size,'cells':cells}
    metadata={'source':'satellite','area':area,'generatedAt':datetime.now(timezone.utc).isoformat(),
              'provenance':provenance,'temperatureStatus':temperature_status,
              'validCells':{field:sum(c[field] is not None for c in cells) for field in ['ndvi','tempC']},
              'caveats':['Historical satellite snapshot, not live weather.','NDVI is not tree-canopy percentage.','Different fields may come from different acquisition dates.','Bearing overlay is approximate; 100 m cells cannot resolve individual trees.']}
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    for name,body in [('grid.json',grid),('provenance.json',metadata)]:
        temporary=output/(name+'.tmp');temporary.write_text(json.dumps(body,indent=2,allow_nan=False),encoding='utf-8');temporary.replace(output/name)
    print(json.dumps({'output':str(output),'validCells':metadata['validCells'],'temperatureStatus':temperature_status}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sentinel',default=str(ROOT/'data/sentinel-item.json'))
    parser.add_argument('--landsat',default=str(ROOT/'data/landsat-item.json'))
    parser.add_argument('--landsat-dir',help='Local official ST_B10, QA_PIXEL, QA_RADSAT files; no paid read')
    parser.add_argument('--requester-pays',action='store_true',help='COST: explicitly permit paid AWS Landsat reads; requires existing AWS credentials')
    parser.add_argument('--output',default=str(ROOT/'public/data'))
    build(parser.parse_args())

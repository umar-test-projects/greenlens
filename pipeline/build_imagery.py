from super_resolution import options, build as build_super_resolution
args = options()
import json
import os
os.environ['AWS_NO_SIGN_REQUEST']='YES'
from pathlib import Path
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.transform import from_origin
from rasterio.enums import Resampling
from rasterio.session import DummySession
from pyproj import Transformer
root=Path(__file__).resolve().parents[1]
area=json.loads((root/'data/area.json').read_text())
item=json.loads((root/'data/sentinel-item.json').read_text())
x,y=Transformer.from_crs('EPSG:4326',area['crs'],always_xy=True).transform(area['center']['lng'],area['center']['lat'])
size=area['widthM']
transform=from_origin(x-size/2,y+size/2,10,10)
with rasterio.Env(session=DummySession(),GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',GDAL_HTTP_TIMEOUT=30,GDAL_HTTP_MAX_RETRY=1,CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif'):
 with rasterio.open(item['assets']['visual']['href'], AWS_NO_SIGN_REQUEST='YES') as src:
  with WarpedVRT(src,crs=area['crs'],transform=transform,width=100,height=100,resampling=Resampling.nearest) as vrt:
   rgb=vrt.read([1,2,3])
with rasterio.open(root/'public/data/satellite-rgb.png','w',driver='PNG',width=100,height=100,count=3,dtype='uint8') as dst:
 dst.write(rgb)
metadata={'image':'/data/satellite-rgb.png','sceneId':item['id'],'acquiredAt':item['properties']['datetime'],'source':item['assets']['visual']['href'],'attribution':'Contains modified Copernicus Sentinel data (2025)','cellRows':10,'cellColumns':10,'resolutionM':10,'processing':'True-color TCI crop aligned to existing 100 m UTM grid; row-major north to south.'}
grid=json.loads((root/'public/data/grid.json').read_text())
metadata['cells']=[{'lat':c['lat'],'lng':c['lng'],'row':i//10,'column':i%10} for i,c in enumerate(grid['cells'])]
(root/'public/data/imagery.json').write_text(json.dumps(metadata,indent=2))
print('Saved aligned RGB crop',rgb.shape, 'range', int(rgb.min()),int(rgb.max()))
from enhance_imagery import build as enhance_display
enhance_display(root)

if args.super_resolution:
    build_super_resolution(root, args.weights, args.device, args.tile)

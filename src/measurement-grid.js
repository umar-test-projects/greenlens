import proj4 from 'proj4';

export function measurementCell(location,grid){
 if(!grid||!Number.isFinite(location?.lat)||!Number.isFinite(location?.lng))return null;
 const south=grid.epsg>=32701,zone=grid.epsg-(south?32700:32600);
 if(!Number.isInteger(zone)||zone<1||zone>60||!Array.isArray(grid.bounds))return null;
 const projection=`+proj=utm +zone=${zone} ${south?'+south ':''}+datum=WGS84 +units=m +no_defs`;
 const [x,y]=proj4('EPSG:4326',projection,[location.lng,location.lat]);
 const [west,southBound,east,north]=grid.bounds,tolerance=1e-6;
 if(!Number.isFinite(x)||!Number.isFinite(y)||x<west-tolerance||x>east+tolerance||y<southBound-tolerance||y>north+tolerance)return null;
 const column=Math.min(19,Math.max(0,Math.floor((x-west+tolerance)/100))),row=Math.min(19,Math.max(0,Math.floor((north-y+tolerance)/100)));
 return grid.cells[row*20+column]??null;
}
export function mapMeasurements(displayGrid,measuredGrid){
 return {...displayGrid,cells:displayGrid.cells.map(cell=>{const match=measurementCell(cell,measuredGrid);return {...cell,ndvi:match?.ndvi??null,tempC:match?.tempC??null,measurementLat:match?.lat,measurementLng:match?.lng}})};
}
export function measurementSource(metadata,layer){return metadata?.provenance?.find(source=>source.field===(layer==='heat'?'tempC':'ndvi'))??null}

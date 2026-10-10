export const MOCK_ORIGIN={lat:26.8467,lng:80.9462};
// Synthetic fixture only. These are NOT observations of Lucknow.
export const mockGrid={
 bbox:[80.9447,26.84535,80.9477,26.84805],cellSizeM:100,
 cells:[
  {lat:26.8476,lng:80.9452,ndvi:.14,tempC:39},
  {lat:26.8476,lng:80.9462,ndvi:.22,tempC:37},
  {lat:26.8476,lng:80.9472,ndvi:.66,tempC:32},
  {lat:26.8467,lng:80.9452,ndvi:.08,tempC:41},
  {lat:26.8467,lng:80.9462,ndvi:null,tempC:null},
  {lat:26.8467,lng:80.9472,ndvi:.48,tempC:34},
  {lat:26.8458,lng:80.9452,ndvi:.19,tempC:38},
  {lat:26.8458,lng:80.9462,ndvi:.35,tempC:35},
  {lat:26.8458,lng:80.9472,ndvi:.71,tempC:31},
 ]
};
const rad=degrees=>degrees*Math.PI/180;
export function temperatureRange(cells){
 const values=cells.map(cell=>cell.tempC).filter(Number.isFinite);
 if(!values.length)return null;
 const low=Math.floor(Math.min(...values)),high=Math.ceil(Math.max(...values));
 return [low,high>low?high:low+1];
}
export function layerFraction(cell,layer,range){
 const value=layer==='heat'?cell.tempC:cell.ndvi;
 if(!Number.isFinite(value))return null;
 if(layer==='heat'&&(!range||range[1]<=range[0]))return null;
 const fraction=layer==='heat'?(value-range[0])/(range[1]-range[0]):value;
 return Math.min(1,Math.max(0,fraction));
}
export function queryGrid(grid,origin){
 const empty={bbox:grid?.bbox??[],cellSizeM:grid?.cellSizeM??100,cells:[]};
 if(!grid||!origin||!Number.isFinite(origin.lat)||!Number.isFinite(origin.lng)||!Array.isArray(grid.bbox)||grid.bbox.length!==4||!grid.bbox.every(Number.isFinite)||!Array.isArray(grid.cells))return empty;
 const [w,s,e,n]=grid.bbox;
 if(origin.lng<w||origin.lng>e||origin.lat<s||origin.lat>n)return empty;
 return {...grid,cells:grid.cells.filter(c=>Number.isFinite(c.lat)&&Number.isFinite(c.lng)&&(c.ndvi===null||(Number.isFinite(c.ndvi)&&c.ndvi>=-1&&c.ndvi<=1))&&(c.tempC===null||Number.isFinite(c.tempC)))};
}
export function bearing(from,to){
 const delta=rad(to.lng-from.lng),a=rad(from.lat),b=rad(to.lat);
 return (Math.atan2(Math.sin(delta)*Math.cos(b),Math.cos(a)*Math.sin(b)-Math.sin(a)*Math.cos(b)*Math.cos(delta))*180/Math.PI+360)%360;
}
export const relativeBearing=(target,heading)=>((target-heading+540)%360)-180;
export function queryMock({lat,lng}){
 const [west,south,east,north]=mockGrid.bbox;
 const covered=Number.isFinite(lat)&&Number.isFinite(lng)&&lat>=south&&lat<=north&&lng>=west&&lng<=east;
 return {layers:{source:'mock',status:covered?'ok':'no_data',grid:{...mockGrid,cells:covered?mockGrid.cells:[]}},answer:null,scenario:null};
}
export function projectCells(grid,origin,heading){
 if(!origin)return [];
 return grid.cells.filter(cell=>Math.abs(cell.lat-origin.lat)+Math.abs(cell.lng-origin.lng)>.00001)
  .map((cell,index)=>{
   const angle=relativeBearing(bearing(origin,cell),heading);
   return {...cell,id:`${cell.lat},${cell.lng}`,angle,x:Math.tan(rad(angle))/Math.tan(rad(35)),row:index%3,distance:Math.hypot((cell.lat-origin.lat)*111320,(cell.lng-origin.lng)*111320*Math.cos(rad(origin.lat)))};
  }).filter(cell=>Math.abs(cell.angle)<35).sort((a,b)=>a.distance-b.distance)
  .filter((cell,index,all)=>all.findIndex(other=>Math.floor((other.angle+35)/23.34)===Math.floor((cell.angle+35)/23.34))===index).slice(0,3);
}

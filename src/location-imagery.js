const metersPerDegree=111320;
export function buildLocationGrid(center){
 if(!Number.isFinite(center?.lat)||!Number.isFinite(center?.lng)||center.lat<-80||center.lat>84||Math.abs(center.lng)>180)
  throw new Error('Satellite coverage requires a valid location between 80°S and 84°N.');
 const columns=9,rows=9,size=100,longitudeScale=metersPerDegree*Math.cos(center.lat*Math.PI/180);
 const cells=[];
 for(let row=0;row<rows;row++)for(let column=0;column<columns;column++){
  const lat=center.lat+(4-row)*size/metersPerDegree,lng=center.lng+(column-4)*size/longitudeScale;
  cells.push({lat,lng,row,column,isLocation:row===4&&column===4,tempC:null,ndvi:null,
   bbox:[lng-50/longitudeScale,lat-50/metersPerDegree,lng+50/longitudeScale,lat+50/metersPerDegree]});
 }
 return {center:{...center},cellSizeM:size,rows,columns,cells,
  bbox:[center.lng-450/longitudeScale,center.lat-450/metersPerDegree,center.lng+450/longitudeScale,center.lat+450/metersPerDegree]};
}

// The image can be rotated in geographic coordinates; test its actual crop corners.
export function locationWithinGrid(location,grid){
 if(!Number.isFinite(location?.lat)||!Number.isFinite(location?.lng)||!grid)return false;
 const polygon=grid.footprint;
 if(!polygon){const b=grid.bbox;return Boolean(b&&location.lng>=b[0]&&location.lng<=b[2]&&location.lat>=b[1]&&location.lat<=b[3]);}
 let inside=false;
 const x=location.lng,y=location.lat;
 for(let i=0,j=polygon.length-1;i<polygon.length;j=i++){
  const [ax,ay]=polygon[j],[bx,by]=polygon[i];
  const cross=(x-ax)*(by-ay)-(y-ay)*(bx-ax);
  if(Math.abs(cross)<=1e-12&&x>=Math.min(ax,bx)-1e-10&&x<=Math.max(ax,bx)+1e-10&&y>=Math.min(ay,by)-1e-10&&y<=Math.max(ay,by)+1e-10)return true;
  if((ay>y)!==(by>y)&&x<(bx-ax)*(y-ay)/(by-ay)+ax)inside=!inside;
 }
 return inside;
}

export function locationCell(location,grid){
 if(!locationWithinGrid(location,grid))return null;
 return grid.cells.find(cell=>locationWithinGrid(location,cell))??null;
}

export function imageNeeded(location,loadedGrid,pendingGrid){
 return !locationWithinGrid(location,loadedGrid)&&!locationWithinGrid(location,pendingGrid);
}

export function locationDistance(a,b){
 return Math.hypot((a.lat-b.lat)*metersPerDegree,(a.lng-b.lng)*metersPerDegree*Math.cos(a.lat*Math.PI/180));
}

export function attachMeasurements(grid,measurements){
 const bbox=measurements?.bbox,half=(measurements?.cellSizeM??100)/2;
 return {...grid,cells:grid.cells.map(cell=>{
  const covered=bbox&&cell.lng>=bbox[0]&&cell.lng<=bbox[2]&&cell.lat>=bbox[1]&&cell.lat<=bbox[3];
  const match=covered?measurements.cells.find(m=>
   Math.abs((m.lat-cell.lat)*metersPerDegree)<=half&&
   Math.abs((m.lng-cell.lng)*metersPerDegree*Math.cos(cell.lat*Math.PI/180))<=half):null;
  return {...cell,tempC:match?.tempC??null,ndvi:match?.ndvi??null,
   measurementLat:match?.lat,measurementLng:match?.lng};
 })};
}

// Display-only percentile lightness stretch, local contrast and mild sharpening.
export function enhancePixels(pixels,width,height){
 const luminance=new Float32Array(width*height),sorted=[];
 for(let i=0;i<luminance.length;i++){
  luminance[i]=.2126*pixels[i*4]+.7152*pixels[i*4+1]+.0722*pixels[i*4+2];
  if(pixels[i*4+3]&&luminance[i]>0)sorted.push(luminance[i]);
 }
 sorted.sort((a,b)=>a-b);
 const low=sorted[Math.floor(sorted.length*.02)]??0,high=sorted[Math.floor(sorted.length*.98)]??0;
 if(high-low<2)return pixels.slice();
 const stretched=Float32Array.from(luminance,l=>.65*Math.min(245,Math.max(10,(l-low)*235/(high-low)+10))+.35*l);
 const output=pixels.slice();
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){
  const i=y*width+x;
  if(!luminance[i])continue;
  let mean=0,count=0;
  for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){
   const yy=Math.min(height-1,Math.max(0,y+dy)),xx=Math.min(width-1,Math.max(0,x+dx));
   mean+=stretched[yy*width+xx];count++;
  }
  const target=Math.max(0,Math.min(255,stretched[i]+.3*(stretched[i]-mean/count)));
  const gain=target/luminance[i];
  for(let channel=0;channel<3;channel++)output[i*4+channel]=Math.min(255,Math.max(0,pixels[i*4+channel]*gain));
 }
 return output;
}

export async function loadLocationImagery(center,{signal,onProgress=()=>{}}={}){
 const grid=buildLocationGrid(center);
 onProgress('Finding a satellite scene near your GPS…');
 const end=new Date(),start=new Date(end);start.setUTCFullYear(start.getUTCFullYear()-2);
 const response=await fetch('https://earth-search.aws.element84.com/v1/search',{
  method:'POST',headers:{'Content-Type':'application/json'},signal,
  body:JSON.stringify({collections:['sentinel-2-l2a'],bbox:grid.bbox,
   datetime:`${start.toISOString()}/${end.toISOString()}`,limit:12,
   sortby:[{field:'properties.datetime',direction:'desc'}],query:{'eo:cloud_cover':{lt:20}}})});
 if(!response.ok)throw new Error('Satellite catalog unavailable. Try again.');
 const catalog=await response.json();
 const [{fromUrl},{default:proj4}]=await Promise.all([import('geotiff'),import('proj4')]);
 let lastError;
 for(const feature of (catalog.features??[]).slice(0,4)){
  const href=feature.assets?.visual?.href,epsg=feature.properties?.['proj:epsg'];
  if(!href||!Number.isInteger(epsg)||epsg<32601||epsg>32760)continue;
  const host=new URL(href).hostname;
  if(!['sentinel-cogs.s3.us-west-2.amazonaws.com','e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com'].includes(host))continue;
  const southern=epsg>=32701,zone=epsg-(southern?32700:32600);
  if(zone<1||zone>60)continue;
  const projection=`+proj=utm +zone=${zone} ${southern?'+south ':''}+datum=WGS84 +units=m +no_defs`;
  const [cx,cy]=proj4('EPSG:4326',projection,[center.lng,center.lat]);
  const bbox=[cx-450,cy-450,cx+450,cy+450];
  try{
   signal?.throwIfAborted();onProgress('Loading a 900 m satellite crop…');
   const tiff=await fromUrl(href,{allowFullFile:false,blockSize:65536,cacheSize:32},signal);
   const source=await tiff.getImage();const bounds=source.getBoundingBox();
   if(bbox[0]<bounds[0]||bbox[1]<bounds[1]||bbox[2]>bounds[2]||bbox[3]>bounds[3])continue;
   const [ox,oy]=source.getOrigin(),[rx,ry]=source.getResolution();
   const window=[Math.floor((bbox[0]-ox)/rx),Math.floor((bbox[3]-oy)/ry),Math.ceil((bbox[2]-ox)/rx),Math.ceil((bbox[1]-oy)/ry)];
   const pixels=await source.readRasters({window,samples:[0,1,2],interleave:true,signal});
   signal?.throwIfAborted();
   const rgba=new Uint8ClampedArray(90*90*4);let valid=0;
   // Sample exact projected pixel centers, avoiding a rounded-window GPS shift.
   const width=window[2]-window[0],height=window[3]-window[1];
   for(let y=0;y<90;y++)for(let x=0;x<90;x++){
    const fx=Math.max(0,Math.min(width-1,(bbox[0]+(x+.5)*10-ox)/rx-window[0]-.5));
    const fy=Math.max(0,Math.min(height-1,(bbox[3]-(y+.5)*10-oy)/ry-window[1]-.5));
    const x0=Math.floor(fx),y0=Math.floor(fy),x1=Math.min(width-1,x0+1),y1=Math.min(height-1,y0+1),dx=fx-x0,dy=fy-y0;
    const i=(y*90+x)*4;
    for(let channel=0;channel<3;channel++)rgba[i+channel]=
     pixels[(y0*width+x0)*3+channel]*(1-dx)*(1-dy)+pixels[(y0*width+x1)*3+channel]*dx*(1-dy)+
     pixels[(y1*width+x0)*3+channel]*(1-dx)*dy+pixels[(y1*width+x1)*3+channel]*dx*dy;
    rgba[i+3]=255;if(rgba[i]||rgba[i+1]||rgba[i+2])valid++;
   }
   if(valid<90*90*.9)continue;
   onProgress('Enhancing satellite contrast…');
   const canvas=document.createElement('canvas');canvas.width=90;canvas.height=90;
   const context=canvas.getContext('2d');
   context.putImageData(new ImageData(enhancePixels(rgba,90,90),90,90),0,0);
   const display=document.createElement('canvas');display.width=360;display.height=360;
   const displayContext=display.getContext('2d');displayContext.imageSmoothingQuality='high';displayContext.drawImage(canvas,0,0,360,360);
   const blob=await new Promise(resolve=>display.toBlob(resolve,'image/png'));
   if(!blob)throw new Error('Unable to enhance the satellite image.');
   signal?.throwIfAborted();
   // Position every cell in the same projection used to crop the image.
   const footprint=(x,y,half)=>[[x-half,y-half],[x+half,y-half],[x+half,y+half],[x-half,y+half]].map(point=>proj4(projection,'EPSG:4326',point));
   grid.footprint=footprint(cx,cy,450);
   grid.bbox=[Math.min(...grid.footprint.map(p=>p[0])),Math.min(...grid.footprint.map(p=>p[1])),Math.max(...grid.footprint.map(p=>p[0])),Math.max(...grid.footprint.map(p=>p[1]))];
   grid.cells=grid.cells.map(cell=>{
    const x=cx+(cell.column-4)*100,y=cy+(4-cell.row)*100;
    const [lng,lat]=cell.isLocation?[center.lng,center.lat]:proj4(projection,'EPSG:4326',[x,y]);
    return {...cell,lat,lng,footprint:footprint(x,y,50)};
   });
   const image=URL.createObjectURL(blob);
   return {grid,imagery:{image,enhancedImage:image,cellRows:9,cellColumns:9,cells:grid.cells,
    sceneId:feature.id,acquiredAt:feature.properties.datetime,resolutionM:10,
    attribution:'Contains modified Copernicus Sentinel data',source:href,
    enhancement:{displayOnly:true,techniques:['Percentile lightness stretch','Local contrast sharpening','4× display interpolation']}}};
  }catch(error){if(signal?.aborted)throw error;lastError=error;}
 }
 throw new Error(lastError?'Satellite crop could not load. Check your connection and retry.':'No suitable satellite scene covers your location. Try again later.');
}

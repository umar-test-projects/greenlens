import React from 'react';
import {createRoot} from 'react-dom/client';
import proj4 from 'proj4';
import {App} from '../src/main.jsx';
import {buildLocationGrid} from '../src/location-imagery.js';
const center={lat:12.9767,lng:77.5929},projection='+proj=utm +zone=43 +datum=WGS84 +units=m +no_defs';
const [x,y]=proj4('EPSG:4326',projection,[center.lng,center.lat]),cx=Math.floor(x/1000+.5)*1000,cy=Math.floor(y/1000+.5)*1000;
const geo=(a,b)=>proj4(projection,'EPSG:4326',[a,b]);
const jobId=`p1-32643-${cx}-${cy}.${'a'.repeat(32)}`;
const cells=Array.from({length:400},(_,i)=>{const row=Math.floor(i/20),column=i%20,a=cx-1000+(column+.5)*100,b=cy+1000-(row+.5)*100,[lng,lat]=geo(a,b);return {row,column,lat,lng,ndvi:.45,tempC:null,footprint:[[a-50,b-50],[a+50,b-50],[a+50,b+50],[a-50,b+50]].map(p=>geo(...p))}});
const grid={epsg:32643,bounds:[cx-1000,cy-1000,cx+1000,cy+1000],rows:20,columns:20,cellSizeM:100,cells};
const ndviSource={field:'ndvi',dataset:'Synthetic fixture Sentinel-2',sceneId:'FIXTURE_S2',acquiredAt:'2026-09-01T00:00:00Z'},tempSource={field:'tempC',dataset:'Synthetic fixture Landsat',sceneId:'FIXTURE_L8',acquiredAt:'2026-08-23T00:00:00Z'};
let scenario='ndvi',calls=0,release=null;
async function request(){
 calls++;if(scenario==='busy')throw Object.assign(new Error('Processing busy · synthetic fixture'),{status:429,retryAfterSeconds:15});
 if(scenario==='error')throw Object.assign(new Error('Provider failure · synthetic fixture'),{status:503,code:'PROCESSING_FAILED',retryAfterSeconds:60});
 if(scenario==='delayed'&&calls>1)await new Promise(resolve=>release=resolve);
 const final=scenario==='final'||scenario==='delayed'&&calls>1,empty=scenario==='no_data';
 const fieldStatus={ndvi:{status:empty?'no_data':'ready'},tempC:{status:empty?'no_data':final?'ready':'processing'}};
 return {jobId,datasetId:`${jobId}.${final||empty?'final':'ndvi'}`,status:final?'ready':empty?'no_data':'processing',retryAfterSeconds:3,fieldStatus,grid:{...grid,cells:cells.map(c=>({...c,ndvi:empty?null:c.ndvi,tempC:final?29.6609:null}))},metadata:{source:'satellite',expiresAt:Date.now()/1000+86400,provenance:empty?[]:final?[ndviSource,tempSource]:[ndviSource]}};
}
async function image(anchor){const image='data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="90" height="90"%3E%3Crect width="90" height="90" fill="%23254939"/%3E%3C/svg%3E';return {grid:buildLocationGrid(anchor),imagery:{image,enhancedImage:image,acquiredAt:'2026-09-05T00:00:00Z',resolutionM:10,attribution:'Synthetic UI fixture',cellRows:9,cellColumns:9}}}
async function query(payload){return {text:`Synthetic fixture summary for ${payload.datasetId}`,citations:[]}}
const app=createRoot(document.getElementById('root')),controls=createRoot(document.getElementById('fixture-controls'));
function render(name='ndvi',position={latitude:center.lat,longitude:center.lng,accuracy:5}){scenario=name;calls=0;release=null;app.render(<App key={`${name}-${Boolean(position)}`} initialMode="none" initialPosition={position} loadImage={image} satelliteRequest={request} queryRequest={query}/>)}
controls.render(<div style={{position:'fixed',zIndex:30,bottom:4,left:4,right:4,padding:4,background:'#fff',color:'#111',fontSize:10}}><b>SYNTHETIC UI FIXTURE · NOT OBSERVATIONS</b>{['ndvi','final','no_data','busy','error','delayed'].map(name=><button key={name} onClick={()=>render(name)}>{name}</button>)}<button onClick={()=>release?.()}>Release temperature</button><button onClick={()=>render('denied',null)}>Denied GPS</button></div>);
render();

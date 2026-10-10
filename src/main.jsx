import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {headingFromEvent, normalize} from './heading.js';
import {MOCK_ORIGIN, queryMock, queryGrid, projectCells, temperatureRange} from './layers.js';
import Overlay from './Overlay.jsx';
import SurveyScene from './SurveyScene.jsx';
import QueryPanel from './QueryPanel.jsx';
import {locationCell,locationWithinGrid,loadLocationImagery} from './location-imagery.js';
import useLocationImagery from './useLocationImagery.js';
import useSatelliteMeasurements from './useSatelliteMeasurements.js';
import {mapMeasurements,measurementCell,measurementSource} from './measurement-grid.js';
import {sendSatellite} from './satellite.js';
import useAirTemperature from './useAirTemperature.js';
import AirTemperatureCard from './AirTemperatureCard.jsx';
import {sendCurrentWeather} from './weather.js';
import {openToolsKeyboard} from './tools-focus.js';
import './style.css';

export function App({initialMode='satellite',initialPosition=null,loadImage=loadLocationImagery,satelliteRequest=sendSatellite,queryRequest,weatherRequest=sendCurrentWeather}){
 const [imagery,setImagery]=useState(null),[tint,setTint]=useState(.25);
 useEffect(()=>{const controller=new AbortController();fetch('/data/imagery.json',{signal:controller.signal}).then(r=>{if(!r.ok)throw new Error('Image metadata unavailable');return r.json()}).then(setImagery).catch(()=>{});return ()=>controller.abort()},[]);
 const [toolsOpen,setToolsOpen]=useState(false),[sceneView,setSceneView]=useState(true),[selected,setSelected]=useState(null),[zoom,setZoom]=useState(1);
 const toolsPanel=useRef(null),toolsTrigger=useRef(null);
 useEffect(()=>{if(toolsOpen)return openToolsKeyboard(toolsPanel.current,toolsTrigger.current,()=>setToolsOpen(false))},[toolsOpen]);
 const video=useRef(null), stream=useRef(null), watch=useRef(null), cleanup=useRef(()=>{}), generation=useRef(0), drag=useRef(null);
 const [active,setActive]=useState(false),[camera,setCamera]=useState('Not started'),[gps,setGps]=useState('Not started'),[compass,setCompass]=useState('Not started'),[position,setPosition]=useState(initialPosition),[heading,setHeading]=useState(0),[manual,setManual]=useState(true);
 const manualRef=useRef(true);
 const [mode,setMode]=useState(initialMode),[layer,setLayer]=useState(initialMode==='none'?'green':'heat');
 const [satellite,setSatellite]=useState(null),[dataStatus,setDataStatus]=useState('Loading satellite snapshot…');
 const {scene:locationScene,status:locationStatus,loading:locationLoading,retry:retryLocationImagery,measurementAnchor}=useLocationImagery(mode==='none',position,loadImage);
 const measurements=useSatelliteMeasurements(mode==='none'&&Boolean(position),measurementAnchor,import.meta.env.VITE_SATELLITE_URL||'/satellite',satelliteRequest);
 useEffect(()=>setSelected(null),[locationScene,measurementAnchor?.lat,measurementAnchor?.lng,mode]);
 useEffect(()=>{
  const controller=new AbortController();
  Promise.all(['/data/grid.json','/data/provenance.json'].map(url=>fetch(url,{signal:controller.signal}).then(r=>{if(!r.ok)throw new Error('Dataset unavailable');return r.json()})))
   .then(([grid,metadata])=>{
    if(metadata.source!=='satellite'||!metadata.area?.center||!Array.isArray(metadata.provenance)||!metadata.provenance.some(p=>p.field==='ndvi')||!Array.isArray(grid.cells))throw new Error('Invalid dataset');
    setSatellite({grid,metadata});setDataStatus('Historical satellite snapshot loaded');
   }).catch(e=>{if(e.name!=='AbortError')setDataStatus('Satellite data unavailable · no data')});
  return ()=>controller.abort();
 },[]);
 function chooseManual(value){manualRef.current=value;setManual(value)}
 function stop(){generation.current++;stream.current?.getTracks().forEach(t=>t.stop());stream.current=null;if(video.current)video.current.srcObject=null;if(watch.current!==null)navigator.geolocation?.clearWatch(watch.current);watch.current=null;cleanup.current();setActive(false);setCamera('Stopped');setGps('Stopped');setCompass('Stopped');setPosition(null);chooseManual(true)}
 useEffect(()=>()=>{generation.current++;stream.current?.getTracks().forEach(t=>t.stop());if(watch.current!==null)navigator.geolocation?.clearWatch(watch.current);cleanup.current()},[]);
 function requestLocation(id=generation.current){
  setGps('Waiting for GPS…');
  if(!window.isSecureContext){setGps('HTTPS required');return}
  if(watch.current!==null){navigator.geolocation?.clearWatch(watch.current);watch.current=null}
  if(navigator.geolocation)watch.current=navigator.geolocation.watchPosition(p=>{if(id!==generation.current)return;setPosition(p.coords);setGps(`Accuracy ±${Math.round(p.coords.accuracy)} m${p.coords.accuracy>50?' · low accuracy':''}`)},e=>{if(id!==generation.current)return;setPosition(null);setGps(e.code===1?'Location denied':e.code===3?'GPS timed out · waiting':'Location unavailable')},{enableHighAccuracy:true,timeout:15000,maximumAge:5000});
  else setGps('GPS unavailable');
 }
 async function start(){
  stop();const id=generation.current;setActive(true);setCamera('Requesting camera…');setCompass('Waiting for compass…');
  if(!window.isSecureContext){setCamera('HTTPS required on phones');setGps('HTTPS required');setCompass('Use manual heading');return}
  // Call synchronously within the tap, before awaiting camera or GPS.
  let permission;
  try{permission=typeof window.DeviceOrientationEvent?.requestPermission==='function'?window.DeviceOrientationEvent.requestPermission(true):Promise.resolve('granted')}catch{permission=Promise.resolve('denied')}
  Promise.resolve(permission).then(result=>{
   if(id!==generation.current)return;
   if(result!=='granted'){setCompass('Permission denied · use manual');return}
   let timer;
   const stale=()=>{setCompass('No recent compass · use manual');chooseManual(true)};
   const onOrientation=e=>{const value=headingFromEvent(e);if(value===null)return;clearTimeout(timer);timer=setTimeout(stale,5000);setCompass('Compass available · approximate');if(!manualRef.current)setHeading(value)};
   chooseManual(false);timer=setTimeout(stale,5000);
   window.addEventListener('deviceorientationabsolute',onOrientation);window.addEventListener('deviceorientation',onOrientation);
   cleanup.current=()=>{clearTimeout(timer);window.removeEventListener('deviceorientationabsolute',onOrientation);window.removeEventListener('deviceorientation',onOrientation)};
  }).catch(()=>{if(id===generation.current)setCompass('Compass unavailable · use manual')});
  if(mode==='none')requestLocation(id);
  try{
   if(!navigator.mediaDevices?.getUserMedia)throw new Error('Camera API unavailable');
   const media=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'}},audio:false});
   if(id!==generation.current){media.getTracks().forEach(t=>t.stop());return}
   stream.current=media;video.current.srcObject=media;await video.current.play();if(id===generation.current)setCamera('Camera live');
  }catch(e){if(id!==generation.current)return;stream.current?.getTracks().forEach(t=>t.stop());stream.current=null;setCamera(e.name==='NotAllowedError'?'Camera denied · allow in site settings':e.name==='NotFoundError'?'No camera · desktop mode':`Camera unavailable · ${e.message}`)}
 }
 const direction=['N','NE','E','SE','S','SW','W','NW'][Math.round(heading/45)%8];
 const origin=mode==='mock'?MOCK_ORIGIN:mode==='satellite'?satellite?.metadata.area.center:position?{lat:position.latitude,lng:position.longitude}:null;
 const weather=useAirTemperature(mode!=='mock',origin,weatherRequest);
 const response=mode==='mock'?queryMock({...MOCK_ORIGIN,heading,question:''}):null;
 const gpsGrid=useMemo(()=>locationScene?mapMeasurements(locationScene.grid,measurements.result?.grid):null,[locationScene,measurements.result]);
 const emptyGrid={cells:[],cellSizeM:100};
 const grid=mode==='none'?(origin?(sceneView?(gpsGrid??measurements.result?.grid??emptyGrid):(measurementCell(origin,measurements.result?.grid)?measurements.result.grid:emptyGrid)):emptyGrid):response?.layers.grid??queryGrid(satellite?.grid,origin);
 const sceneImagery=mode==='none'?locationScene?.imagery:mode==='mock'?null:imagery;
 const visible=projectCells(grid,origin,heading);
 const selectedMetadata=mode==='none'?measurements.result?.metadata:satellite?.metadata;
 const selectedProvenance=mode==='mock'?null:measurementSource(selectedMetadata,layer);
 const date=selectedProvenance?.acquiredAt?.slice(0,10);
 const heatRange=temperatureRange(mode==='mock'?response.layers.grid.cells:mode==='none'?measurements.result?.grid.cells??[]:satellite?.grid.cells??[]);
 const aheadReading=visible.reduce((best,cell)=>!best||Math.abs(cell.angle)<Math.abs(best.angle)?cell:best,null);
 const currentLocationCell=mode==='none'?(grid.epsg?measurementCell(origin,grid):locationCell(origin,grid)):null;
 const reading=sceneView?(grid.cells.find(c=>selected&&c.lat===selected.lat&&c.lng===selected.lng)??(mode==='none'?currentLocationCell:aheadReading)??(mode==='none'?null:grid.cells[0])):aheadReading;
 const fieldState=measurements.fieldStatus[layer==='heat'?'tempC':'ndvi']?.status;
 const fieldMessage=['pending','processing'].includes(fieldState)?(layer==='heat'?'Processing Landsat surface temperature…':'Processing Sentinel-2 vegetation…'):fieldState==='error'?'This layer could not be processed. Retry shortly.':fieldState==='no_data'?'No clear satellite observations for this layer.':'No valid environmental measurement in this cell.';
 const overlayCells=aheadReading?[aheadReading]:[];
 const emptyMessage=mode==='none'&&sceneView?(position?locationStatus:gps==='Not started'?'Use my location to load satellite imagery.':gps):!satellite&&mode!=='mock'?dataStatus:!origin?'Enable GPS or use the Aliganj preview.':!grid.cells.length?'No satellite data at this location.':'No grid cell ahead. Rotate or drag to look around.';
 const modeLabel=mode==='mock'?'Synthetic mock':mode==='satellite'?'Aliganj preview':'My GPS';
 const imageryWithinGrid=locationWithinGrid(origin,locationScene?.grid);
 const gpsReady=Boolean(position&&!measurements.loading&&!measurements.retryNeeded&&measurements.result?.status==='ready'&&!locationLoading&&imageryWithinGrid);
 return <main className={`survey-app ${toolsOpen?'tools-open':''}`}>
  <section className={`view ${sceneView?'scene-view':''} ${camera==='Camera live'?'camera-live':''}`} aria-label="Heading control" onPointerDown={e=>{if(!manualRef.current||toolsOpen||e.target.closest('button, input, select'))return;drag.current={x:e.clientX,heading};if(!sceneView)e.currentTarget.setPointerCapture(e.pointerId)}} onPointerMove={e=>{if(drag.current&&!toolsOpen)setHeading(normalize(drag.current.heading+(e.clientX-drag.current.x)*.4))}} onPointerUp={()=>drag.current=null} onPointerCancel={()=>drag.current=null} onPointerLeave={()=>drag.current=null}>
   <video ref={video} muted playsInline autoPlay aria-label="Live camera view"/>
   <div className="shade"/>
   {sceneView?<SurveyScene grid={grid} origin={origin} heading={heading} layer={layer} heatRange={heatRange} selected={reading} onSelect={cell=>{if(!toolsOpen)setSelected(cell)}} zoom={zoom} imagery={sceneImagery?{...sceneImagery,image:sceneImagery.enhancedImage}:null} appearance="enhanced" tint={tint} showLocation={mode==='none'&&Boolean(position)}/>:<Overlay cells={overlayCells} layer={layer} heatRange={heatRange}/>}
  <header className="app-header" onPointerDown={e=>e.stopPropagation()}>
   <div className="brand-row"><a className="brand" href="./"><span aria-hidden="true">◉</span> GreenLens</a><span className="area-badge">{modeLabel}</span></div>
   <nav className="survey-navigation" aria-label="Survey tools">
    <div className="layer-switch" data-layer={layer} role="group" aria-label="Environmental layer">
     <button aria-pressed={layer==='heat'} onClick={()=>setLayer('heat')}>{mode==='mock'?'Surface heat (mock)':'Air temperature'}</button>
     <button aria-pressed={layer==='green'} onClick={()=>setLayer('green')}>Vegetation</button>
    </div>
   {sceneView&&mode!=='mock'&&sceneImagery&&grid.cells.length>0&&<div className="imagery-controls" onPointerDown={e=>e.stopPropagation()}>
    <label>{layer==='heat'?'Surface heat tint':'Vegetation tint'}<input aria-label="Layer tint strength" type="range" min="0" max="80" value={Math.round(tint*100)} onChange={e=>setTint(Number(e.target.value)/100)}/><output>{Math.round(tint*100)}%</output></label>
   </div>}
    <button ref={toolsTrigger} className="tools-toggle" aria-expanded={toolsOpen} aria-controls="field-tools" onClick={()=>setToolsOpen(v=>!v)}>{toolsOpen?'Close ×':'Tools ↗'}</button>
   </nav>
   {sceneView&&mode!=='mock'&&sceneImagery&&grid.cells.length>0&&<small className="imagery-credit">Historical imagery · {sceneImagery.acquiredAt.slice(0,10)} · Copernicus Sentinel-2</small>}
  </header>
   {mode==='none'&&<div className={`gps-scene-status ${gpsReady?'gps-ready':''}`} role="status" onPointerDown={e=>e.stopPropagation()}><div className="gps-status-line"><span className="gps-dot"/><span>{gpsReady?'Satellite data loaded':position?measurements.status:gps==='Not started'?'Use my location to load imagery and measurements.':gps}</span></div>{position&&<small>{gpsReady?`GPS accuracy ±${Math.round(position.accuracy)} m`:`You · accuracy ±${Math.round(position.accuracy)} m · ${locationStatus}`}</small>}{position&&!measurements.loading&&measurements.retryNeeded&&<button onClick={measurements.retry}>Retry measurements</button>}{position&&!locationLoading&&!imageryWithinGrid&&<button onClick={retryLocationImagery}>Retry imagery</button>}</div>}
   <div className="scene-actions" onPointerDown={e=>e.stopPropagation()}><button aria-label="Zoom in" disabled={toolsOpen||zoom<=.7} onClick={()=>setZoom(z=>Math.max(.7,z-.15))}>＋</button><button aria-label="Zoom out" disabled={toolsOpen||zoom>=1.6} onClick={()=>setZoom(z=>Math.min(1.6,z+.15))}>−</button><button aria-label="Reset view" disabled={toolsOpen} onClick={()=>{chooseManual(true);setHeading(0);setZoom(1);setSelected(null)}}>↺</button><button aria-label="Inspect next cell" disabled={toolsOpen||!grid.cells.length} onClick={()=>{const i=grid.cells.findIndex(c=>c.lat===reading?.lat&&c.lng===reading?.lng);setSelected(grid.cells[(i+1)%grid.cells.length])}}>→</button></div>
   <p className="scene-hint">{sceneView?'DRAG TO ROTATE · TAP A CELL TO INSPECT':'DRAG TO CHANGE HEADING'}</p>
   <div className="view-toolbar">
    <span className="compass">{direction} {Math.round(heading)%360}°<small>{manual?'Manual':'Compass'}</small></span>
   </div>
   <div className="reticle" aria-hidden="true"><i/><i/></div>
   <p className="alignment-note">Approximate direction · {grid.cellSizeM} m cells</p>
   <div inert={toolsOpen} className={`reading-slot ${layer==='heat'?'weather-reading':''}`} aria-label={layer==='heat'&&mode!=='mock'?'Current air temperature':sceneView?"Selected satellite cell":"Grid cell ahead"}>
    {layer==='heat'&&mode!=='mock'?<AirTemperatureCard weather={weather} reference={mode==='satellite'} waitingForReference={mode==='satellite'&&!satellite&&dataStatus.startsWith('Loading')}/>:reading?<article className="measurement-card" data-node-id="12:328" key={`${mode}-${layer}`}>
     <div className="measurement-heading"><span>{layer==='heat'?'Satellite surface temperature':'Vegetation index · NDVI'}</span><small>{sceneView?`${reading===currentLocationCell?'Your cell · ':''}${grid.cellSizeM} m${mode==='none'&&(layer==='heat'?reading.tempC!==null:reading.ndvi!==null)?` · measured ${date??'date unavailable'}`:' grid cell'}`:`${Math.round((reading.angle+heading+360)%360)}° · ~${Math.round(reading.distance)} m`}</small></div>
     <strong>{layer==='heat'?(reading.tempC===null?'No data':<>{reading.tempC.toFixed(1)}<small> °C</small></>):(reading.ndvi===null?'No data':reading.ndvi.toFixed(2))}</strong>
     <p>{mode==='none'&&(layer==='heat'?reading.tempC===null:reading.ndvi===null)?fieldMessage:layer==='heat'?'Ground surface, not air temperature':'Vegetation index, not tree-cover percentage'}</p>
    </article>:<div className="empty-reading" role="status"><strong>{mode==='none'&&sceneView?(locationLoading?'Loading imagery':position?'No imagery':'Waiting for GPS'):'No data'}</strong><p>{emptyMessage}</p>{mode==='none'&&<button onPointerDown={e=>e.stopPropagation()} onClick={()=>setMode('satellite')}>Use Aliganj preview</button>}</div>}
   </div>
   {(mode==='mock'||(date&&grid.cells.some(c=>layer==='heat'?c.tempC!==null:c.ndvi!==null)))&&<div className={`legend ${layer==='heat'?'surface-legend':''}`} aria-label="Layer display scale">
    {layer==='heat'&&<small>{mode==='mock'?'Synthetic surface heat':`Satellite surface heat map · ${date}`}</small>}
    {layer==='heat'&&heatRange?<><span>{heatRange[0]} °C</span><i className="heat-scale"/><span>{heatRange[1]} °C</span></>:layer==='green'?<><span>NDVI 0</span><i className="green-scale"/><span>1</span></>:null}
   </div>}
  </section>
  <footer ref={toolsPanel} id="field-tools" aria-label="Field tools" hidden={!toolsOpen}><div className="drawer-heading"><span>YOUR FIELD STATION</span><h2>Field tools</h2><p className="note">{modeLabel} · {mode==='mock'?'Synthetic · not observations':'Camera is optional. Choose a view or explore the measured data.'}</p></div><div className="view-mode" role="group" aria-label="View mode"><button aria-pressed={sceneView} onClick={()=>setSceneView(true)}>3D survey</button><button aria-pressed={!sceneView} onClick={()=>setSceneView(false)}>Camera / AR</button></div>
   <div className="camera-actions">
    <button className="primary" onClick={start}>{active?'Retry camera':'Start camera'} <span aria-hidden="true">↗</span></button>
    <button className="secondary" onClick={()=>{setMode('none');setLayer('green');setSelected(null);setSceneView(true);setToolsOpen(false);requestLocation()}}>Use my location</button>
    {active&&<button className="stop-button" onClick={stop}>Stop</button>}
   </div>
   {active&&camera!=='Camera live'&&<p className="sensor-notice" role="status">{camera}. The data preview still works.</p>}
   {mode==='none'&&<p className="sensor-notice" role="status">{gps}</p>}
   <QueryPanel origin={origin} heading={heading} mode={mode} datasetId={mode==='none'?measurements.result?.datasetId:null} measurementStatus={measurements.status} request={queryRequest}/>
   <details className="data-explainer"><summary>How the data works</summary>
   {sceneImagery&&mode!=='mock'&&<p className="note">Satellite imagery: {sceneImagery.acquiredAt.slice(0,10)} · {sceneImagery.resolutionM} m pixels. Enhanced view uses contrast adjustment and light sharpening for display only; source measurements are unchanged. Optional AI 4× imagery contains generated detail for visual use only and does not improve real spatial resolution. {sceneImagery.attribution}. Temperature measurements use a separate Landsat acquisition.</p>}
   {mode==='none'&&<p className="note">Your marker follows GPS across the loaded 900 m image. A new image downloads when you leave its boundary. NDVI and surface temperature are processed separately for a 2 km neighborhood, using clear satellite observations. Imagery enhancement runs on this device. GPS coordinates go to AWS; neighborhood bounds go to Earth Search.</p>}
   {mode!=='mock'&&<p className="note">Air temperature is a current weather estimate for {mode==='satellite'?'the Aliganj reference area':'your area'}. Rounded area coordinates go to Open-Meteo and refresh every 15 minutes. Map heat and satellite summaries use historical land surface temperature.</p>}
   </details>
   <details className="controls-panel">
    <summary>Controls &amp; sources <span>{manual?'Manual heading':'Compass heading'}</span></summary>
    <div className="controls-content">
     <label className="field-label">Data source<select aria-label="Data source" value={mode} onChange={e=>{setMode(e.target.value);setSelected(null);if(e.target.value==='none')setLayer('green')}}><option value="satellite">Aliganj snapshot · fixed reference</option><option value="none">My GPS · satellite measurements</option><option value="mock">Mock preview · synthetic data</option></select></label>
     <p className="note">{mode==='mock'?`Synthetic fixture at ${MOCK_ORIGIN.lat}, ${MOCK_ORIGIN.lng}. Not real observations.`:mode==='satellite'?`Preview from the Aliganj reference pin, ${origin?.lat??'unavailable'}, ${origin?.lng??'unavailable'}. Independent of your GPS.`:position?`Your GPS: ${position.latitude.toFixed(5)}, ${position.longitude.toFixed(5)}. Your marker moves within the loaded image; measurements use dated observations for this neighborhood.`:'No GPS position. Use my location or return to Aliganj preview.'}</p>
     <div className="statuses"><p><b>Camera</b>{camera}</p><p><b>Location</b>{gps}</p><p><b>Heading</b>{compass}</p></div>
     <label className="manual"><input type="checkbox" checked={manual} onChange={e=>chooseManual(e.target.checked)}/> Manual heading</label>
     {manual&&<><input className="slider" aria-label="Manual heading in degrees" type="range" min="0" max="359" value={Math.round(heading)%360} onChange={e=>setHeading(Number(e.target.value))}/><p className="note">Drag the view or use the slider to look around.</p></>}
     <p className="note">Keep the phone upright. Compass readings can drift near metal. Camera frames stay on your device. Patches show grid directions, not individual trees or buildings.</p>
     {mode!=='mock'&&<div className="source-records"><p>{mode==='none'?measurements.status:dataStatus}.</p>{selectedMetadata?.provenance.map(source=><p key={source.field}><b>{source.field==='tempC'?'Surface temperature':'NDVI'}</b> · {source.acquiredAt.slice(0,10)}<br/>{source.dataset}<br/><small>{source.sceneId}</small></p>)}</div>}
    </div>
   </details>
  </footer>
 </main>
}
if(!import.meta.env.DEV||!location.pathname.startsWith('/tests/'))createRoot(document.getElementById('root')).render(<App/>);



import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import SurveyScene from '../src/SurveyScene.jsx';
import {loadLocationImagery,locationCell} from '../src/location-imagery.js';
import useLocationImagery from '../src/useLocationImagery.js';
import useSatelliteMeasurements from '../src/useSatelliteMeasurements.js';
import {mapMeasurements,measurementSource} from '../src/measurement-grid.js';
import {temperatureRange} from '../src/layers.js';
import '../src/style.css';
const center={lat:12.9767,lng:77.5929};
let downloads=0;
const loadPreviewImagery=(...args)=>{downloads++;return loadLocationImagery(...args);};
function Preview(){
 const [position,setPosition]=useState({latitude:center.lat,longitude:center.lng});
 const {scene:result,status,loading,retry,measurementAnchor}=useLocationImagery(true,position,loadPreviewImagery);
 const measurements=useSatelliteMeasurements(true,measurementAnchor,import.meta.env.VITE_SATELLITE_URL||'https://y6yl9bz1u1.execute-api.ap-south-1.amazonaws.com/satellite');
 const [layer,setLayer]=useState('green');
 const grid=result?mapMeasurements(result.grid,measurements.result?.grid):null;
 const origin={lat:position.latitude,lng:position.longitude};
 const cell=locationCell(origin,grid);
 function moveTo(point){setPosition({latitude:point.lat,longitude:point.lng});}
 return <main className="survey-app"><div style={{position:'absolute',zIndex:10,top:20,left:20,right:20,fontSize:12}}><b>PUBLIC LANDMARK TEST · NOT YOUR GPS</b><p role="status">{status} · Downloads: {downloads} · Cell: {cell?`${cell.row+1}, ${cell.column+1}`:'outside image'} · Image center: {result?`${result.grid.center.lat.toFixed(5)}, ${result.grid.center.lng.toFixed(5)}`:'pending'}</p>
 <button disabled={!result||loading} onClick={()=>moveTo(result.grid.cells[42])}>Move two cells east</button>{' '}
 <button disabled={!result||loading} onClick={()=>moveTo({lat:result.grid.center.lat,lng:result.grid.bbox[2]+100/(111320*Math.cos(result.grid.center.lat*Math.PI/180))})}>Leave image</button>{' '}
 <button disabled={!result} onClick={()=>moveTo(result.grid.center)}>Return to loaded image</button>{' '}
 <button disabled={loading} onClick={retry}>Retry imagery</button>{' '}<button onClick={()=>setLayer('green')}>Vegetation</button>{' '}<button onClick={()=>setLayer('heat')}>Surface heat</button>
 <p>{measurements.status} · {cell?(layer==='heat'?cell.tempC:cell.ndvi)??'No data':'No cell'} · {measurementSource(measurements.result?.metadata,layer)?.acquiredAt?.slice(0,10)??'No acquisition'} · {measurements.result?.datasetId??'No dataset'}</p></div>{result&&<SurveyScene grid={grid} origin={origin} layer={layer} heatRange={temperatureRange(grid.cells)} imagery={result.imagery} appearance="enhanced" showLocation selected={cell} onSelect={moveTo} zoom={1} tint={.25}/>}</main>
}
createRoot(document.getElementById('root')).render(<Preview/>);

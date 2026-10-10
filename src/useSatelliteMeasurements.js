import {useEffect,useRef,useState} from 'react';
import {createSatelliteController,sendSatellite} from './satellite.js';
const empty={result:null,status:'Waiting for GPS measurements.',fieldStatus:{},loading:false,retryAt:0,retryNeeded:false};
export default function useSatelliteMeasurements(enabled,anchor,url='/satellite',request=sendSatellite){
 const [state,setState]=useState(empty),controller=useRef(null);
 useEffect(()=>{
  if(!enabled||!anchor){setState(empty);return}
  const client=createSatelliteController({request:(payload,signal)=>request(payload,signal,fetch,url),onUpdate:setState});controller.current=client;client.start(anchor);
  return ()=>{client.stop();if(controller.current===client)controller.current=null};
 },[enabled,anchor?.lat,anchor?.lng,url,request]);
 useEffect(()=>{if(state.result?.metadata.expiresAt){const timer=setTimeout(()=>controller.current?.expire(),Math.max(0,state.result.metadata.expiresAt*1000-Date.now()));return()=>clearTimeout(timer)}},[state.result?.datasetId]);
 return {...state,retry:()=>controller.current?.retry()};
}

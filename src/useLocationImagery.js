import {useEffect,useRef,useState} from 'react';
import {buildLocationGrid,imageNeeded,loadLocationImagery,locationWithinGrid} from './location-imagery.js';

// Keep one enhanced crop while GPS moves through its cells. A pending crop also
// supplies coverage so repeated GPS fixes do not restart the same download.
export default function useLocationImagery(enabled,position,loadImage=loadLocationImagery){
 const [anchor,setAnchor]=useState(null),[scene,setScene]=useState(null);
 const [status,setStatus]=useState('Use my location to load satellite imagery.');
 const [loading,setLoading]=useState(false);
 const pending=useRef(null),imageUrl=useRef(null);
 useEffect(()=>()=>{if(imageUrl.current)URL.revokeObjectURL(imageUrl.current)},[]);
 useEffect(()=>{
  if(!enabled){
   pending.current=null;setAnchor(null);setScene(null);
   if(imageUrl.current){URL.revokeObjectURL(imageUrl.current);imageUrl.current=null;}
   return;
  }
  if(!position)return;
  const center={lat:position.latitude,lng:position.longitude};
  if(locationWithinGrid(center,scene?.grid)){
   // Returning to the available image cancels an unnecessary replacement.
   if(pending.current){pending.current=null;setAnchor(null);setStatus('Location tracked · enhanced satellite imagery');}
   return;
  }
  if(!imageNeeded(center,scene?.grid,pending.current))return;
  try{pending.current=buildLocationGrid(center);setAnchor(center);}
  catch(error){setStatus(error.message);}
 },[enabled,position,scene]);
 useEffect(()=>{
  if(!enabled||!anchor){setLoading(false);return;}
  const controller=new AbortController();let disposed=false,timedOut=false;
  const timer=setTimeout(()=>{timedOut=true;controller.abort()},60000);
  setLoading(true);
  loadImage(anchor,{signal:controller.signal,onProgress:message=>{if(!disposed)setStatus(message)}})
   .then(result=>{
    if(disposed){URL.revokeObjectURL(result.imagery.image);return;}
    if(imageUrl.current)URL.revokeObjectURL(imageUrl.current);
    imageUrl.current=result.imagery.image;pending.current=null;
    setScene(result);setStatus('Location tracked · enhanced satellite imagery');
   }).catch(error=>{if(!disposed)setStatus(timedOut?'Satellite imagery timed out. Retry when connected.':error.message);})
   .finally(()=>{clearTimeout(timer);if(!disposed)setLoading(false);});
  return ()=>{disposed=true;clearTimeout(timer);controller.abort();};
 },[enabled,anchor,loadImage]);
 function retry(){
  if(!enabled||!position||loading)return;
  const center={lat:position.latitude,lng:position.longitude};
  if(locationWithinGrid(center,scene?.grid))return;
  try{pending.current=buildLocationGrid(center);setAnchor(center);}
  catch(error){setStatus(error.message);}
 }
 return {scene,status,loading,retry,measurementAnchor:enabled&&position?(anchor??scene?.grid.center??null):null};
}

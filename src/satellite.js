const jobPattern=/^p1-32[67]\d{2}-\d+-\d+\.[a-f0-9]{32}$/;
const states=new Set(['queued','processing','ready','partial','no_data','error']);
const fieldStates=new Set(['pending','processing','ready','no_data','error']);
function validResponse(data){
 if(!data||!jobPattern.test(data.jobId)||!states.has(data.status)||!['ndvi','tempC'].every(f=>fieldStates.has(data.fieldStatus?.[f]?.status)))return false;
 if(data.datasetId===null)return !data.grid;
 if(!['ndvi','final'].some(r=>data.datasetId===`${data.jobId}.${r}`))return false;
 const grid=data.grid;
 if(!grid||!Number.isInteger(grid.epsg)||!Array.isArray(grid.bounds)||grid.bounds.length!==4||!grid.bounds.every(Number.isFinite)||grid.rows!==20||grid.columns!==20||grid.cellSizeM!==100||grid.cells?.length!==400||!Array.isArray(data.metadata?.provenance)||!Number.isFinite(data.metadata?.expiresAt))return false;
 return grid.cells.every((c,i)=>Number.isFinite(c.lat)&&Number.isFinite(c.lng)&&c.row===Math.floor(i/20)&&c.column===i%20&&Array.isArray(c.footprint)&&c.footprint.length===4&&[c.ndvi,c.tempC].every(v=>v===null||Number.isFinite(v))&&(c.ndvi===null||c.ndvi>=-1&&c.ndvi<=1)&&['ndvi','tempC'].every(f=>c[f]===null||data.metadata.provenance.some(p=>p.field===f&&typeof p.sceneId==='string'&&Number.isFinite(Date.parse(p.acquiredAt)))));
}
export async function sendSatellite(payload,signal,fetcher=fetch,url='/satellite'){
 const response=await fetcher(url,{method:'POST',headers:{'Content-Type':'application/json'},signal,body:JSON.stringify(payload)});
 let data;try{data=await response.json()}catch{throw new Error('Satellite service unavailable. Retry shortly.')}
 if(!response.ok){
  const delay=Number(response.headers?.get('Retry-After')??data.retryAfterSeconds);
  throw Object.assign(new Error(data.error?.message||data.message||'Satellite processing unavailable. Retry shortly.'),{status:response.status,code:data.error?.code,retryAfterSeconds:Number.isFinite(delay)&&delay>0?delay:response.status===429?15:60});
 }
 if(!validResponse(data))throw new Error('Invalid satellite measurements received.');
 return data;
}

export function createSatelliteController({request,onUpdate,now=Date.now,setTimer=setTimeout,clearTimer=clearTimeout}){
 let version=0,anchor=null,jobId=null,result=null,fieldStatus={},timer=null,deadlineTimer=null,requestTimer=null,abort=null,began=0,failed=false,retryAt=0,loading=false;
 const emit=(status,retryNeeded=false)=>onUpdate({result,fieldStatus,status,loading,retryAt,retryNeeded});
 function clear(){for(const id of [timer,deadlineTimer,requestTimer])if(id!==null)clearTimer(id);timer=deadlineTimer=requestTimer=null;abort?.abort();abort=null}
 function stop(){version++;clear();loading=false;anchor=null;jobId=null}
 function timeout(id){if(id!==version)return;version++;clear();loading=false;failed=Boolean(jobId);emit('Processing timed out. Retry to check this location.',true)}
 async function run(payload,id){
  if(id!==version)return;
  if(now()-began>=480000){timeout(id);return}
  abort=new AbortController();requestTimer=setTimer(()=>abort?.abort(),30000);
  try{
   const data=await request(payload,abort.signal);
   if(id!==version)return;
   clearTimer(requestTimer);requestTimer=null;jobId=data.jobId;fieldStatus=data.fieldStatus;
   if(data.datasetId&&data.grid)result=data;
   failed=Object.values(fieldStatus).some(f=>f.status==='error');
   retryAt=Math.max(0,...Object.values(fieldStatus).map(f=>(f.retryAfterAt??0)*1000));
   loading=['queued','processing'].includes(data.status);
   const message=loading?(fieldStatus.ndvi.status==='ready'?'NDVI available · processing surface temperature…':'Processing satellite vegetation and temperature…'):data.status==='no_data'?'No clear satellite observations found.':data.status==='partial'?'Available observations loaded · one layer needs retry.':data.status==='error'?'Satellite processing failed. Retry shortly.':'Satellite observations loaded.';
   emit(message,!loading&&data.status!=='ready');
   if(loading)timer=setTimer(()=>run({...anchor,jobId},id),Math.max(3,data.retryAfterSeconds||3)*1000);
   else{clearTimer(deadlineTimer);deadlineTimer=null}
  }catch(error){
   if(id!==version)return;
   clearTimer(requestTimer);requestTimer=null;
   if(error.status===429){emit('Processing busy · waiting for an available slot…');timer=setTimer(()=>run(payload,id),Math.max(15,error.retryAfterSeconds||15)*1000)}
   else{loading=false;failed=['PROCESSING_FAILED','JOB_EXPIRED'].includes(error.code);retryAt=now()+(error.retryAfterSeconds||0)*1000;clearTimer(deadlineTimer);deadlineTimer=null;emit(error.name==='AbortError'?'Satellite request timed out. Retry shortly.':error.message,true)}
  }
 }
 function begin(payload){version++;clear();began=now();loading=true;const id=version;deadlineTimer=setTimer(()=>timeout(id),480000);emit('Finding satellite observations…');run(payload,id)}
 return {start(next){if(anchor&&next?.lat===anchor.lat&&next?.lng===anchor.lng)return;stop();anchor={lat:next.lat,lng:next.lng};result=null;fieldStatus={};failed=false;retryAt=0;begin({...anchor})},retry(){if(!anchor||loading||now()<retryAt)return;jobId=null;begin({...anchor,...(failed?{retryFailed:true}:{})})},expire(){version++;clear();loading=false;result=null;fieldStatus={};failed=false;retryAt=0;emit('Satellite observations expired. Retry this location.',true)},stop};
}

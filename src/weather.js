export const WEATHER_SOURCE_URL='https://open-meteo.com/';
const REFRESH_MS=15*60*1000;

// Weather models describe an area. Do not send precise phone coordinates.
export function weatherLocation(location){
 if(!location||!Number.isFinite(location.lat)||!Number.isFinite(location.lng)||Math.abs(location.lat)>90||Math.abs(location.lng)>180)return null;
 return {lat:Math.round(location.lat*100)/100,lng:Math.round(location.lng*100)/100};
}

export async function sendCurrentWeather(location,signal,fetcher=fetch,now=Date.now){
 const area=weatherLocation(location);
 if(!area)throw new Error('Weather location unavailable');
 const url=new URL('https://api.open-meteo.com/v1/forecast');
 url.search=new URLSearchParams({latitude:area.lat,longitude:area.lng,current:'temperature_2m',temperature_unit:'celsius',timeformat:'unixtime',timezone:'auto',forecast_days:'1'}).toString();
 const response=await fetcher(url.toString(),{signal,cache:'no-store'});
 if(!response.ok)throw new Error('Weather unavailable. Please retry shortly.');
 const data=await response.json(),value=data.current?.temperature_2m,time=data.current?.time,seconds=now()/1000;
 if(!Number.isFinite(value)||value < -100||value > 70||data.current_units?.temperature_2m!=='°C'||!Number.isFinite(time)||time<seconds-3600||time>seconds+900)throw new Error('Current weather unavailable or outdated.');
 return {airTempC:value,validAt:time,expiresAt:time+3600,timezone:data.timezone||'UTC',area,source:'Open-Meteo',sourceUrl:WEATHER_SOURCE_URL};
}

export function createWeatherController({request,onUpdate,now=Date.now,setTimer=setTimeout,clearTimer=clearTimeout}){
 let anchor=null,version=0,pending=null,refresh=null,timeout=null,expiry=null;
 const emit=(result,loading,status)=>onUpdate({result,loading,status});
 function clear(){for(const id of [refresh,timeout,expiry])if(id!==null)clearTimer(id);refresh=timeout=expiry=null}
 function stop(){version++;clear();pending?.abort();pending=null;anchor=null}
 function schedule(){refresh=setTimer(run,REFRESH_MS)}
 async function run(){
  clear();pending?.abort();const id=++version,controller=new AbortController();pending=controller;
  emit(null,true,'Loading current air temperature…');
  timeout=setTimer(()=>{if(id!==version)return;version++;controller.abort();pending=null;emit(null,false,'Weather request timed out. Retry shortly.');schedule()},15000);
  try{
   const result=await request(anchor,controller.signal);
   if(id!==version)return;
   if(!Number.isFinite(result?.airTempC)||!Number.isFinite(result?.expiresAt)||result.expiresAt<=now()/1000)throw new Error('Weather reading expired. Retry shortly.');
   emit(result,false,'Current air temperature loaded');
   expiry=setTimer(()=>{if(id===version)emit(null,false,'Weather reading expired. Retry shortly.')},result.expiresAt*1000-now());
  }catch(error){if(id===version)emit(null,false,error.name==='AbortError'?'Weather request timed out. Retry shortly.':error.message||'Weather unavailable. Retry shortly.')}
  finally{if(id===version){clearTimer(timeout);timeout=null;pending=null;schedule()}}
 }
 return {start(location){const next=weatherLocation(location);if(next&&anchor&&next.lat===anchor.lat&&next.lng===anchor.lng)return;stop();anchor=next;if(anchor)run();else emit(null,false,'Enable GPS to load air temperature.')},retry(){if(anchor)run()},stop};
}

export function weatherTime(result){
 if(!result)return '';
 const options={dateStyle:'medium',timeStyle:'short',timeZone:result.timezone};
 try{return new Intl.DateTimeFormat(undefined,options).format(new Date(result.validAt*1000))}
 catch{return new Intl.DateTimeFormat(undefined,{...options,timeZone:'UTC'}).format(new Date(result.validAt*1000))}
}

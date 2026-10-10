import test from 'node:test';
import assert from 'node:assert/strict';
import {weatherLocation,sendCurrentWeather,createWeatherController} from './weather.js';

const now=Date.parse('2026-10-10T21:00:00Z'),area={lat:26.8472,lng:80.9468};
const response=(temp=26,time=now/1000)=>({current:{temperature_2m:temp,time},current_units:{temperature_2m:'°C',time:'unixtime'},timezone:'Asia/Kolkata'});
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function harness(request){
 let time=now,sequence=0;const timers=new Map(),updates=[],calls=[];
 const client=createWeatherController({request:(...args)=>{calls.push(args);return request(...args)},onUpdate:s=>updates.push(s),now:()=>time,setTimer:(fn,ms)=>{const id=++sequence;timers.set(id,{fn,at:time+ms});return id},clearTimer:id=>timers.delete(id)});
 return {client,updates,calls,timers,advance:async ms=>{time+=ms;for(const [id,t] of [...timers])if(t.at<=time){timers.delete(id);t.fn()}await flush()}};
}
test('weather uses rounded area coordinates and current Celsius air temperature',async()=>{
 let url;const value=await sendCurrentWeather(area,null,async u=>{url=new URL(u);return {ok:true,json:async()=>response()}},()=>now);
 assert.equal(url.origin,'https://api.open-meteo.com');assert.equal(url.searchParams.get('latitude'),'26.85');assert.equal(url.searchParams.get('longitude'),'80.95');
 assert.equal(url.searchParams.get('current'),'temperature_2m');assert.equal(url.searchParams.get('temperature_unit'),'celsius');assert.equal(url.searchParams.get('timeformat'),'unixtime');
 assert.equal(value.airTempC,26);assert.equal(value.validAt,now/1000);assert.equal(value.source,'Open-Meteo');assert.deepEqual(value.area,{lat:26.85,lng:80.95});
});
test('missing, invalid, wrong-unit and stale weather never become a temperature',async()=>{
 for(const data of [response(null),response('26'),response(999),response(26,now/1000-3601),response(26,now/1000+901),{...response(),current_units:{temperature_2m:'°F'}}]){
  await assert.rejects(sendCurrentWeather(area,null,async()=>({ok:true,json:async()=>data}),()=>now),/weather/i);
 }
 await assert.rejects(sendCurrentWeather(area,null,async()=>({ok:false,status:429}),()=>now),/weather/i);
});
test('invalid coordinates are rejected without contacting the provider',async()=>{
 assert.equal(weatherLocation(null),null);assert.equal(weatherLocation({lat:91,lng:0}),null);
 let calls=0;await assert.rejects(sendCurrentWeather({lat:NaN,lng:0},null,async()=>{calls++}),/location/i);assert.equal(calls,0);
});
test('GPS jitter reuses weather, refreshes every fifteen minutes, and replaces the reading',async()=>{
 let temp=26;const h=harness(async anchor=>sendCurrentWeather(anchor,null,async()=>({ok:true,json:async()=>response(temp)}),()=>now));
 h.client.start(area);await flush();assert.equal(h.updates.at(-1).result.airTempC,26);
 h.client.start({lat:26.8473,lng:80.9469});await flush();assert.equal(h.calls.length,1);
 temp=27;await h.advance(15*60000);assert.equal(h.calls.length,2);assert.equal(h.updates.at(-1).result.airTempC,27);h.client.stop();
});
test('late responses cannot restore another location or a stopped GPS reading',async()=>{
 const pending=[];const h=harness(()=>new Promise(resolve=>pending.push(resolve)));
 h.client.start(area);h.client.start({lat:12.97,lng:77.59});
 pending[0]({airTempC:39,validAt:now/1000,expiresAt:now/1000+3600});await flush();assert.equal(h.updates.at(-1).result,null);
 pending[1]({airTempC:26,validAt:now/1000,expiresAt:now/1000+3600});await flush();assert.equal(h.updates.at(-1).result.airTempC,26);
 h.client.stop();assert.equal(h.timers.size,0);assert.equal(h.calls[0][1].aborted,true);
});
test('provider failure and timeout show no weather and allow manual retry',async()=>{
 let reject=true;const h=harness(async()=>{if(reject)throw new Error('Weather unavailable');return {airTempC:26,expiresAt:now/1000+3600}});
 h.client.start(area);await flush();assert.equal(h.updates.at(-1).result,null);assert.equal(h.updates.at(-1).loading,false);
 reject=false;h.client.retry();await flush();assert.equal(h.updates.at(-1).result.airTempC,26);h.client.stop();
 const stalled=harness(()=>new Promise(()=>{}));stalled.client.start(area);await stalled.advance(15000);assert.equal(stalled.updates.at(-1).loading,false);assert.match(stalled.updates.at(-1).status,/timed out/i);stalled.client.stop();
});
test('an expired response is never displayed as current air temperature',async()=>{
 const h=harness(async()=>({airTempC:26,expiresAt:now/1000-1}));h.client.start(area);await flush();assert.equal(h.updates.at(-1).result,null);assert.match(h.updates.at(-1).status,/expired/i);h.client.stop();
});
test('the displayed weather is cleared at expiry and stopped requests cannot restore it',async()=>{
 const h=harness(async()=>({airTempC:0,expiresAt:now/1000+60}));h.client.start(area);await flush();assert.equal(h.updates.at(-1).result.airTempC,0);await h.advance(60000);assert.equal(h.updates.at(-1).result,null);h.client.stop();
 let resolve;const stopped=harness(()=>new Promise(done=>resolve=done));stopped.client.start(area);stopped.client.stop();resolve({airTempC:26,expiresAt:now/1000+3600});await flush();assert.equal(stopped.updates.at(-1).result,null);assert.equal(stopped.timers.size,0);
});

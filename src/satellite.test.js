import test from 'node:test';
import assert from 'node:assert/strict';
import {sendSatellite,createSatelliteController} from './satellite.js';
const anchor={lat:12.9767,lng:77.5929};
const pending={jobId:'p1-32643-500000-1400000.'+'a'.repeat(32),datasetId:null,status:'processing',retryAfterSeconds:3,fieldStatus:{ndvi:{status:'processing'},tempC:{status:'pending'}}};
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function harness(request){
 let time=0;const timers=new Map(),updates=[],calls=[];let sequence=0;
 const controller=createSatelliteController({request:(...args)=>{calls.push(args[0]);return request(...args)},onUpdate:value=>updates.push(value),now:()=>time,setTimer:(fn,ms)=>{const id=++sequence;timers.set(id,{fn,at:time+ms});return id},clearTimer:id=>timers.delete(id)});
 return {controller,timers,updates,calls,advance:async ms=>{time+=ms;for(const [id,t] of [...timers])if(t.at<=time){timers.delete(id);t.fn()}await flush()}};
}
test('same anchor reuses a job; polling keeps the original coordinates',async()=>{
 const h=harness(async()=>pending);h.controller.start(anchor);await flush();h.controller.start({...anchor});await flush();assert.equal(h.calls.length,1);
 assert.ok([...h.timers.values()].some(t=>t.at===3000));await h.advance(3000);assert.deepEqual(h.calls[1],{...anchor,jobId:pending.jobId});h.controller.stop();
});
test('busy retries at fifteen seconds and expires after eight minutes',async()=>{
 const h=harness(async()=>{throw Object.assign(new Error('Busy'),{status:429,retryAfterSeconds:15})});h.controller.start(anchor);await flush();assert.ok([...h.timers.values()].some(t=>t.at===15000));await h.advance(15000);assert.equal(h.calls.length,2);await h.advance(465000);assert.equal(h.timers.size,0);assert.equal(h.updates.at(-1).loading,false);assert.match(h.updates.at(-1).status,/timed out/i);
});
test('partial data is retained on a provider failure and retry is explicit',async()=>{
 let count=0;const result={...pending,datasetId:pending.jobId+'.ndvi',grid:{cells:[]},metadata:{provenance:[]}};
 const h=harness(async()=>++count===1?result:Promise.reject(Object.assign(new Error('Provider failed'),{status:503,code:'PROCESSING_FAILED',retryAfterSeconds:60})));
 h.controller.start(anchor);await flush();assert.equal(h.updates.at(-1).result.datasetId,result.datasetId);await h.advance(3000);assert.equal(h.updates.at(-1).result.datasetId,result.datasetId);assert.equal(h.timers.size,0);
 await h.advance(60000);h.controller.retry();await flush();assert.equal(h.calls.at(-1).retryFailed,true);h.controller.stop();
});
test('late responses cannot update a stopped or replaced neighborhood',async()=>{
 const resolvers=[];const h=harness(()=>new Promise(resolve=>resolvers.push(resolve)));h.controller.start(anchor);h.controller.start({lat:13,lng:77});const before=h.updates.length;resolvers[0](pending);await flush();assert.equal(h.updates.length,before);h.controller.stop();const stopped=h.updates.length;resolvers[1](pending);await flush();assert.equal(h.updates.length,stopped);
});
test('manual retry replaces an expired worker job rather than polling it forever',async()=>{
 const h=harness(async()=>{throw Object.assign(new Error('Worker expired'),{status:503,code:'JOB_EXPIRED',retryAfterSeconds:0})});h.controller.start(anchor);await flush();h.controller.retry();await flush();assert.equal(h.calls.at(-1).retryFailed,true);h.controller.stop();
});
test('busy admission preserves an explicit failed-field retry',async()=>{
 let count=0;
 const h=harness(async()=>{count++;if(count===1)throw Object.assign(new Error('Failed field'),{status:503,code:'PROCESSING_FAILED',retryAfterSeconds:0});if(count===2)throw Object.assign(new Error('Busy'),{status:429,retryAfterSeconds:15});return pending});
 h.controller.start(anchor);await flush();h.controller.retry();await flush();assert.equal(h.calls[1].retryFailed,true);await h.advance(15000);assert.equal(h.calls[2].retryFailed,true);h.controller.stop();
});
test('HTTP validation distinguishes throttles, invalid JSON and invalid measurements',async()=>{
 await assert.rejects(sendSatellite(anchor,null,async()=>({ok:false,status:429,headers:new Headers(),json:async()=>({message:'Too many requests'})})),e=>e.status===429&&e.retryAfterSeconds===15);
 await assert.rejects(sendSatellite(anchor,null,async()=>({ok:true,json:async()=>{throw Error()}})),/unavailable/i);
 await assert.rejects(sendSatellite(anchor,null,async()=>({ok:true,json:async()=>({...pending,datasetId:'wrong',grid:{cells:[{ndvi:2,tempC:NaN}]},metadata:{}})})),/invalid/i);
});

test('complete observations hide retry until their data expires',async()=>{
 const h=harness(async()=>({...pending,status:'ready',fieldStatus:{ndvi:{status:'ready'},tempC:{status:'ready'}}}));
 h.controller.start(anchor);assert.equal(h.updates.at(-1).retryNeeded,false);
 await flush();assert.equal(h.updates.at(-1).retryNeeded,false);
 h.controller.expire();assert.equal(h.updates.at(-1).retryNeeded,true);h.controller.stop();
});
test('incomplete observations keep a manual recovery action',async()=>{
 for(const status of ['partial','no_data','error']){
  const h=harness(async()=>({...pending,status,fieldStatus:{ndvi:{status:'ready'},tempC:{status:'error'}}}));
  h.controller.start(anchor);await flush();assert.equal(h.updates.at(-1).retryNeeded,true,status);h.controller.stop();
 }
});
test('a refresh failure offers retry even when previous complete data is retained',async()=>{
 let count=0;const ready={...pending,status:'ready',datasetId:pending.jobId+'.final',grid:{cells:[]},metadata:{provenance:[]},fieldStatus:{ndvi:{status:'ready'},tempC:{status:'ready'}}};
 const h=harness(async()=>++count===1?ready:Promise.reject(new Error('Connection lost')));
 h.controller.start(anchor);await flush();h.controller.retry();await flush();
 assert.equal(h.updates.at(-1).result.status,'ready');assert.equal(h.updates.at(-1).retryNeeded,true);h.controller.stop();
});
test('automatic busy polling hides manual retry until its deadline',async()=>{
 const h=harness(async()=>{throw Object.assign(new Error('Busy'),{status:429,retryAfterSeconds:15})});
 h.controller.start(anchor);await flush();assert.equal(h.updates.at(-1).retryNeeded,false);
 await h.advance(480000);assert.equal(h.updates.at(-1).retryNeeded,true);h.controller.stop();
});

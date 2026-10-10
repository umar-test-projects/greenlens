import test from 'node:test';
import assert from 'node:assert/strict';
import {sendQuery,queryPayload} from './query.js';

test('proxy and provider errors produce a useful message, never a fake answer',async()=>{
 await assert.rejects(sendQuery({},undefined,async()=>({ok:false,json:async()=>{throw new SyntaxError()}})),/Data service unavailable/);
 await assert.rejects(sendQuery({},undefined,async()=>({ok:false,json:async()=>({error:{message:'Try again shortly'}})})),/Try again shortly/);
});
test('GPS summaries require and preserve the exact measured revision',async()=>{
 const id='p1-32643-500000-1400000.'+'a'.repeat(32)+'.ndvi';
 assert.throws(()=>queryPayload({lat:12,lng:77},0,'What is NDVI?','none'),/measurements/i);
 const payload=queryPayload({lat:12,lng:77},0,'What is NDVI?','none',id);let sent;
 await sendQuery(payload,null,async(_url,options)=>{sent=JSON.parse(options.body);return {ok:true,json:async()=>({answer:{text:'Measured NDVI',citations:[]}})}});
 assert.equal(sent.datasetId,id);assert.equal(queryPayload({lat:26,lng:80},0,'NDVI','satellite').datasetId,undefined);
});
test('only a valid cited answer response is accepted',async()=>{
 await assert.rejects(sendQuery({},undefined,async()=>({ok:true,json:async()=>({answer:{text:'no sources'}})})),/Invalid answer/);
 const answer={text:'No data',citations:[]};
 assert.deepEqual(await sendQuery({},undefined,async()=>({ok:true,json:async()=>({answer})})),answer);
});

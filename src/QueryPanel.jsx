import React, {useEffect, useRef, useState} from 'react';
import {sendQuery,queryPayload} from './query.js';

const summaries=[
 {label:'Local conditions',title:'Local conditions',question:'What are the temperature and NDVI here?'},
 {label:'Compare nearby',title:'Nearby comparison',question:'How does this cell compare with nearby cells?'},
 {label:'Planting areas',title:'Area to inspect for planting',question:'Where should we plant trees here?'},
];

export default function QueryPanel({origin,heading,mode,datasetId=null,measurementStatus=null,request=sendQuery}){
 const [selected,setSelected]=useState(null),[answer,setAnswer]=useState(null);
 const [error,setError]=useState(''),[busy,setBusy]=useState(false);
 const pending=useRef(null),version=useRef(0);
 useEffect(()=>{version.current++;pending.current?.abort();setBusy(false);setAnswer(null);setError('');setSelected(null)},[mode,origin?.lat,origin?.lng,datasetId]);
 useEffect(()=>()=>pending.current?.abort(),[]);
 async function submit(summary){
  if(!origin||mode==='mock'||busy||mode==='none'&&!datasetId)return;
  const id=++version.current,controller=new AbortController();pending.current=controller;
  setSelected(summary);setBusy(true);setError('');setAnswer(null);
  const timer=setTimeout(()=>controller.abort(),30000);
  try{
   const data=await request(queryPayload(origin,heading,summary.question,mode,datasetId),controller.signal,fetch,import.meta.env.VITE_QUERY_URL||'/query');
   if(id===version.current)setAnswer(data);
  }catch(error){if(id===version.current)setError(error.name==='AbortError'?'Request timed out. Please try again.':error.message)}
  finally{clearTimeout(timer);if(id===version.current)setBusy(false)}
 }
 return <section className="query-panel" aria-label="Satellite data summaries">
  <div className="section-heading"><h2>Explore this area</h2><span>Data summaries</span></div>
  <p className="summary-context">{mode==='satellite'?'Summaries use the Aliganj reference pin.':mode==='mock'?'Synthetic preview · real-data summaries disabled.':'Summaries use your GPS position.'}</p>
  {mode!=='mock'&&<p className="note">Satellite summaries use historical surface temperature and NDVI. Current air temperature is shown in the Air temperature tab.</p>}
  <div className="summary-actions">
   {summaries.map(summary=><button key={summary.label} className={selected===summary?'is-selected':''} disabled={busy||!origin||mode==='mock'||mode==='none'&&!datasetId} onClick={()=>submit(summary)}>{summary.label}</button>)}
  </div>
  <p className="privacy-note">Selections and coordinates go to AWS. Camera stays on your phone.</p>
  {!origin&&<p className="note">Enable GPS or use the Aliganj preview to explore measured data.</p>}
  {mode==='none'&&!datasetId&&origin&&<p className="note">{measurementStatus||'Waiting for satellite measurements.'}</p>}
  <div aria-live="polite" aria-busy={busy}>
   {busy&&<p className="request-status">Reading satellite data…</p>}
   {error&&<p className="request-error" role="alert">{error} The satellite view is still available.</p>}
   {answer&&<article className="answer-card">
    <h3>{selected.title}</h3><p className="note">Historical satellite analysis</p><p className="answer-text">{answer.text}</p>
    {selected!==summaries[0]&&<p className="note">Nearby results use available sampled cells within 500 m of {mode==='satellite'?'the reference pin':'your GPS position'}.</p>}
    {answer.citations.length>0&&<details><summary>Measured sources ({answer.citations.length})</summary><ul>{answer.citations.map(c=><li key={c.id}><b>[{c.id}] {c.field==='tempC'?'Surface temperature':'NDVI'}: {c.value} {c.unit}</b><br/>{c.acquiredAt?.slice(0,10)} · {c.lat}, {c.lng}<br/><small>{c.sceneId}</small></li>)}</ul></details>}
    {answer.toolsUsed?.length>0&&<p className="note">Satellite data from AWS S3 · fixed calculations</p>}
   </article>}
  </div>
 </section>
}

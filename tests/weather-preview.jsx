import React from 'react';
import {createRoot} from 'react-dom/client';
import {App} from '../src/main.jsx';
let scenario='ready',release;
const app=createRoot(document.getElementById('root'));
async function request(area){
 if(scenario==='unavailable')throw new Error('Weather unavailable · synthetic fixture');
 if(scenario==='delayed')await new Promise(resolve=>release=resolve);
 return {airTempC:26,validAt:Date.now()/1000,expiresAt:Date.now()/1000+3600,timezone:'Asia/Kolkata',area,source:'Open-Meteo'};
}
function render(name){scenario=name;app.render(<App key={name} weatherRequest={request} initialMode={name==='denied'?'none':'satellite'}/>)}
const controlStyle={padding:3,fontSize:10,minHeight:0,margin:2};
createRoot(document.getElementById('fixture-controls')).render(<div style={{position:'fixed',zIndex:30,top:170,left:4,right:4,padding:4,background:'#fff',color:'#111',fontSize:10}}><b>SYNTHETIC WEATHER FIXTURE · NOT OBSERVATIONS</b>{['ready','unavailable','delayed','denied'].map(name=><button style={controlStyle} key={name} onClick={()=>render(name)}>{name}</button>)}<button style={controlStyle} onClick={()=>release?.()}>Release weather</button></div>);
render('ready');

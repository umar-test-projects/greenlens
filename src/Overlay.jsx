import React,{useEffect,useRef,useState} from 'react';
import {Scene,OrthographicCamera,WebGLRenderer,Mesh,CircleGeometry,MeshBasicMaterial,Color} from 'three';
import {layerFraction} from './layers.js';

export function layerColor(cell,layer,heatRange){
 const fraction=layerFraction(cell,layer,heatRange);
 if(fraction===null)return null;
 return new Color().setHSL(layer==='heat'?(1-fraction)*.14:.29,.75,layer==='heat'?.52:.25+fraction*.3);
}

export default function Overlay({cells,layer,heatRange}){
 const host=useRef(null),engine=useRef(null);
 const [fallback,setFallback]=useState(false);
 useEffect(()=>{
  const container=host.current;
  let renderer;
  try{renderer=new WebGLRenderer({alpha:true,antialias:false});}catch{setFallback(true);return}
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.5));
  const scene=new Scene(),camera=new OrthographicCamera(-1,1,1,-1,.1,10);camera.position.z=2;
  const geometry=new CircleGeometry(.5,32),material=new MeshBasicMaterial({transparent:true,opacity:.18,depthWrite:false});
  const mesh=new Mesh(geometry,material);mesh.scale.set(.8,.55,1);mesh.visible=false;scene.add(mesh);
  const state={scene,camera,renderer,mesh,contextLost:false};engine.current=state;
  container.appendChild(renderer.domElement);
  const resize=()=>{renderer.setSize(container.clientWidth,container.clientHeight);if(!state.contextLost)renderer.render(scene,camera)};
  const observer=new ResizeObserver(resize);observer.observe(container);resize();
  const lost=e=>{e.preventDefault();state.contextLost=true;setFallback(true)};renderer.domElement.addEventListener('webglcontextlost',lost);
  return ()=>{
   observer.disconnect();renderer.domElement.removeEventListener('webglcontextlost',lost);
   scene.remove(mesh);geometry.dispose();material.dispose();renderer.dispose();renderer.domElement.remove();
   if(engine.current===state)engine.current=null;
  };
 },[]);
 useEffect(()=>{
  if(!engine.current||engine.current.contextLost)return;
  const {scene,camera,renderer,mesh}=engine.current;
  const cell=cells[0],color=cell?layerColor(cell,layer,heatRange):null;
  mesh.visible=Boolean(color);
  if(color){mesh.material.color.copy(color);mesh.position.set(cell.x,.05,0)}
  renderer.render(scene,camera);
 },[cells,layer,heatRange]);
 return <><div className="overlay-canvas" ref={host} aria-hidden="true"/>{fallback&&<p className="overlay-warning">3D overlay unavailable · data cards still work</p>}</>;
}

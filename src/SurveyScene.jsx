import React, {useEffect, useRef, useState} from 'react';
import * as THREE from 'three';
import {layerColor} from './Overlay.jsx';
import {cellImageUV,textureSources} from './imagery.js';

// Cell height is a display constant, never a measurement of terrain elevation.
export default function SurveyScene({grid, origin, heading=0, layer='heat', heatRange, selected, onSelect, zoom=1, imagery, appearance='original', tint=.25, showLocation=false}) {
 const host=useRef(null), engine=useRef(null), callbacks=useRef({onSelect});
 const [fallback,setFallback]=useState(false);
 const [texture,setTexture]=useState(null),[imageryError,setImageryError]=useState(false);
 useEffect(()=>{
  setTexture(null);setImageryError(false);
  if(!imagery?.image)return;
  let disposed=false;
  const textures=[];
  const sources=textureSources(imagery,appearance);
  const load=index=>{
   const loaded=new THREE.TextureLoader().load(sources[index],value=>{
    if(disposed){value.dispose();return;}
    value.colorSpace=THREE.SRGBColorSpace;
    value.magFilter=THREE.LinearFilter;value.minFilter=THREE.LinearFilter;
    value.generateMipmaps=false;setTexture(value);
   },undefined,()=>{
    if(disposed)return;
    setImageryError(true);
    if(index+1<sources.length)load(index+1);
   });
   textures.push(loaded);
  };
  load(0);
  return ()=>{disposed=true;textures.forEach(value=>value.dispose())};
 },[imagery?.image,imagery?.enhancedImage,imagery?.superResolvedImage,imagery?.superResolution?.status,appearance]);
 callbacks.current={onSelect};
 useEffect(()=>{
  const container=host.current;
  let renderer;
  try {renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});} catch {setFallback(true);return;}
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.5));
  renderer.setClearColor(0x07131d,0);
  const scene=new THREE.Scene();
  const camera=new THREE.PerspectiveCamera(42,1,10,10000);
  scene.add(new THREE.HemisphereLight(0xd3f4ff,0x162938,2));
  const sun=new THREE.DirectionalLight(0xffffff,2.4);sun.position.set(-300,600,200);scene.add(sun);
  const group=new THREE.Group();scene.add(group);
  const state={scene,camera,renderer,group,meshes:[],radius:300,heading:0,zoom:1,lost:false};
  state.render=()=>{
   if(state.lost)return;
   const aspect=camera.aspect;
   const distance=state.radius*2.7/Math.min(1,aspect)*state.zoom;
   const angle=state.heading*Math.PI/180;
   camera.position.set(-Math.sin(angle)*distance*.78,distance*.82,Math.cos(angle)*distance*.78);
   camera.far=Math.max(10000,distance*5);camera.updateProjectionMatrix();camera.lookAt(0,0,0);
   renderer.render(scene,camera);
  };
  engine.current=state;container.appendChild(renderer.domElement);
  const resize=()=>{const w=container.clientWidth,h=container.clientHeight;if(!w||!h)return;renderer.setSize(w,h);camera.aspect=w/h;state.render();};
  const observer=new ResizeObserver(resize);observer.observe(container);resize();
  let down=null;
  const pointerDown=e=>{down={x:e.clientX,y:e.clientY,id:e.pointerId};};
  const pointerUp=e=>{
   if(!down||down.id!==e.pointerId||Math.hypot(e.clientX-down.x,e.clientY-down.y)>7){down=null;return;}
   down=null;
   const rect=renderer.domElement.getBoundingClientRect();
   const pointer=new THREE.Vector2((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);
   const ray=new THREE.Raycaster();ray.setFromCamera(pointer,camera);
   const hit=ray.intersectObjects(state.meshes,false)[0];
   if(hit)callbacks.current.onSelect?.(hit.object.userData.cell);
  };
  const cancel=()=>{down=null;};
  const lost=e=>{e.preventDefault();state.lost=true;setFallback(true);};
  container.addEventListener('pointerdown',pointerDown);container.addEventListener('pointerup',pointerUp);container.addEventListener('pointercancel',cancel);
  renderer.domElement.addEventListener('webglcontextlost',lost);
  return ()=>{
   observer.disconnect();container.removeEventListener('pointerdown',pointerDown);container.removeEventListener('pointerup',pointerUp);container.removeEventListener('pointercancel',cancel);
   renderer.domElement.removeEventListener('webglcontextlost',lost);
   group.traverse(object=>{object.geometry?.dispose();if(Array.isArray(object.material))object.material.forEach(m=>m.dispose());else object.material?.dispose();});
   renderer.dispose();renderer.domElement.remove();if(engine.current===state)engine.current=null;
  };
 },[]);
 useEffect(()=>{
  const state=engine.current;if(!state||state.lost)return;
  const {group}=state;
  group.traverse(object=>{object.geometry?.dispose();object.material?.dispose();});
  group.clear();state.meshes=[];
  const cells=(grid?.cells??[]).filter(c=>Number.isFinite(c.lat)&&Number.isFinite(c.lng));
  const reference=origin??cells[0];
  if(!reference||!cells.length){state.render();return;}
  const latitude=reference.lat??reference.latitude,longitude=reference.lng??reference.longitude;
  const points=cells.map(cell=>({cell,x:(cell.lng-longitude)*111320*Math.cos(latitude*Math.PI/180),z:-(cell.lat-latitude)*111320}));
  const minX=Math.min(...points.map(p=>p.x)),maxX=Math.max(...points.map(p=>p.x)),minZ=Math.min(...points.map(p=>p.z)),maxZ=Math.max(...points.map(p=>p.z));
  const cx=(minX+maxX)/2,cz=(minZ+maxZ)/2,size=grid.cellSizeM||100;
  state.radius=Math.max(maxX-minX+size,maxZ-minZ+size)*.65;
  const platform=new THREE.Mesh(new THREE.BoxGeometry(maxX-minX+size*1.5,size*.1,maxZ-minZ+size*1.5),new THREE.MeshStandardMaterial({color:0x102736,roughness:.8,metalness:.2}));
  platform.position.y=-size*.11;group.add(platform);
  const helper=new THREE.GridHelper(state.radius*2,Math.max(4,Math.round(state.radius*2/size)),0x32758a,0x183947);helper.position.y=-size*.045;group.add(helper);
  points.forEach(({cell,x,z})=>{
   const color=layerColor(cell,layer,heatRange);
   const crop=texture?cellImageUV(cell,imagery):null;
   const mesh=new THREE.Mesh(new THREE.BoxGeometry(size*.94,size*.065,size*.94),new THREE.MeshStandardMaterial({color:crop?0x1d3339:(color??0x233b47),roughness:.48,metalness:.15,emissive:crop?0x000000:(color??0x000000),emissiveIntensity:crop?0:(color ? .14 : 0)}));
   mesh.position.set(x-cx,0,z-cz);mesh.userData.cell=cell;group.add(mesh);state.meshes.push(mesh);
   if(crop){
    const geometry=new THREE.PlaneGeometry(size*.94,size*.94),uv=geometry.attributes.uv;
    for(let i=0;i<uv.count;i++)uv.setXY(i,crop.u0+uv.getX(i)*(crop.u1-crop.u0),crop.v0+uv.getY(i)*(crop.v1-crop.v0));
    const photo=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({map:texture,toneMapped:false}));
    photo.rotation.x=-Math.PI/2;photo.position.set(x-cx,size*.05,z-cz);group.add(photo);
    photo.userData.cell=cell;state.meshes.push(photo);
    if(color){
     const wash=new THREE.Mesh(new THREE.PlaneGeometry(size*.94,size*.94),new THREE.MeshBasicMaterial({color,transparent:true,opacity:tint,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-1,toneMapped:false}));
     wash.rotation.x=-Math.PI/2;wash.position.set(x-cx,size*.06,z-cz);group.add(wash);
    }
   }
   const isSelected=selected&&(selected.id===`${cell.lat},${cell.lng}`||(selected.lat===cell.lat&&selected.lng===cell.lng));
   const edges=new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry),new THREE.LineBasicMaterial({color:isSelected?0xe5fbff:0x70c4cd,transparent:true,opacity:isSelected?1:.38,depthTest:!isSelected}));
   edges.position.copy(mesh.position);if(isSelected)edges.scale.set(1.025,1.12,1.025);group.add(edges);
  });
  if(showLocation){
   const marker=new THREE.Group();marker.position.set(-cx,size*.07,-cz);
   const halo=new THREE.Mesh(new THREE.RingGeometry(size*.12,size*.18,48),new THREE.MeshBasicMaterial({color:0x92ffde,side:THREE.DoubleSide,transparent:true,opacity:.85,depthTest:false}));
   halo.rotation.x=-Math.PI/2;marker.add(halo);
   const stem=new THREE.Mesh(new THREE.CylinderGeometry(size*.025,size*.025,size*.2,12),new THREE.MeshBasicMaterial({color:0xb7ffeb}));stem.position.y=size*.1;marker.add(stem);
   const pin=new THREE.Mesh(new THREE.SphereGeometry(size*.085,16,12),new THREE.MeshBasicMaterial({color:0x80ffd4}));pin.position.y=size*.26;marker.add(pin);group.add(marker);
  }
  state.render();
 },[grid,origin,layer,heatRange,selected,texture,imagery,tint,showLocation]);
 useEffect(()=>{const state=engine.current;if(state){state.heading=heading;state.zoom=Math.min(1.6,Math.max(.7,zoom));state.render();}},[heading,zoom]);
 return <div className="survey-scene" ref={host} style={{position:'absolute',inset:0}} aria-label="Interactive three dimensional satellite grid">
  {imageryError&&<p className="overlay-warning">Enhanced image unavailable · showing data colors</p>}
  {fallback&&<div className="scene-fallback" style={{position:'absolute',inset:'25% 10%',overflow:'auto'}}><p>3D unavailable. Select a satellite cell to inspect its data.</p><div>{(grid?.cells??[]).map((cell,index)=><button key={`${cell.lat},${cell.lng}`} onPointerDown={e=>e.stopPropagation()} onClick={()=>onSelect?.(cell)}>Cell {index+1}</button>)}</div></div>}
 </div>;
}

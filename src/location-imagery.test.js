import test from 'node:test';
import assert from 'node:assert/strict';
import {buildLocationGrid,attachMeasurements,enhancePixels,locationWithinGrid,locationCell,imageNeeded} from './location-imagery.js';

test('GPS is exactly in the middle cell of a symmetric 9 by 9 grid',()=>{
 const grid=buildLocationGrid({lat:26.88,lng:80.94});
 assert.equal(grid.cells.length,81);
 assert.equal(grid.cells[40].lat,26.88);assert.equal(grid.cells[40].lng,80.94);
 assert.equal(grid.cells[40].isLocation,true);
 assert.equal(grid.cells[0].row,0);assert.equal(grid.cells[0].column,0);
 assert.ok(grid.cells[0].lat>grid.center.lat);assert.ok(grid.cells[0].lng<grid.center.lng);
 assert.equal(grid.cells[0].tempC,null);
});
test('GPS measurement mapping never fills missing coverage or combines unrelated cells',()=>{
 const grid=buildLocationGrid({lat:10,lng:20});
 const measurements={bbox:[19.9995,9.9995,20.0005,10.0005],cellSizeM:100,cells:[{lat:10,lng:20,tempC:37,ndvi:.5}]};
 const mapped=attachMeasurements(grid,measurements);
 assert.equal(mapped.cells[40].tempC,37);
 assert.equal(mapped.cells[0].tempC,null);
 assert.equal(attachMeasurements(grid,{...measurements,bbox:[70,20,71,21]}).cells[40].tempC,null);
});
test('enhancement preserves constant scenes and raises low contrast without mutating input',()=>{
 const flat=new Uint8ClampedArray([120,120,120,255,120,120,120,255]);
 assert.deepEqual(enhancePixels(flat,2,1),flat);
 const pixels=new Uint8ClampedArray(10*10*4);
 for(let i=0;i<100;i++){pixels.set([100+i*.5,100+i*.5,100+i*.5,255],i*4)}
 const copy=pixels.slice();const output=enhancePixels(pixels,10,10);
 assert.deepEqual(pixels,copy);
 assert.ok(output[396]-output[0]>pixels[396]-pixels[0]);
 assert.equal(output[3],255);
});
test('invalid or unsupported latitude never produces imagery requests',()=>{
 assert.throws(()=>buildLocationGrid({lat:100,lng:0}));
 assert.throws(()=>buildLocationGrid({lat:0,lng:NaN}));
});

test('moving across loaded cells preserves imagery until leaving the 900 m crop',()=>{
 const center={lat:26.88,lng:80.94},grid=buildLocationGrid(center);
 const move=(east,north=0)=>({lat:center.lat+north/111320,lng:center.lng+east/(111320*Math.cos(center.lat*Math.PI/180))});
 assert.equal(locationCell(center,grid).column,4);
 for(const east of [40,100,200,400,449]){
  assert.equal(imageNeeded(move(east),grid),false);
  assert.equal(locationCell(move(east),grid).column,4+Math.round(east/100));
 }
 assert.equal(locationCell(move(0,200),grid).row,2);
 assert.equal(locationWithinGrid(move(450),grid),true);
 assert.equal(imageNeeded(move(451),grid),true);
 assert.equal(imageNeeded(move(-451),grid),true);
 assert.equal(imageNeeded(move(0,451),grid),true);
 assert.equal(locationCell(move(451),grid),null);
});

test('pending crop prevents duplicate downloads while moving inside its footprint',()=>{
 const loaded=buildLocationGrid({lat:26.88,lng:80.94});
 const next=buildLocationGrid({lat:26.88,lng:80.95});
 assert.equal(imageNeeded(next.center,loaded),true);
 assert.equal(imageNeeded(next.center,loaded,next),false);
 assert.equal(imageNeeded(next.cells[44],loaded,next),false);
 assert.equal(imageNeeded({lat:26.9,lng:80.97},loaded,next),true);
 assert.equal(imageNeeded(loaded.center,loaded,next),false);
 assert.equal(imageNeeded(loaded.center,null),true);
});

test('projected image footprints determine coverage instead of their geographic bounding box',()=>{
 const diamond={bbox:[-1,-1,1,1],footprint:[[0,-1],[1,0],[0,1],[-1,0]]};
 assert.equal(locationWithinGrid({lat:.9,lng:.9},diamond),false);
 assert.equal(locationWithinGrid({lat:.4,lng:.4},diamond),true);
 assert.equal(locationWithinGrid({lat:.5,lng:.5},diamond),true);
 assert.equal(locationWithinGrid({lat:NaN,lng:0},diamond),false);
 assert.equal(locationWithinGrid(null,diamond),false);
});

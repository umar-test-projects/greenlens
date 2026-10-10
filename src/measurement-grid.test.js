import test from 'node:test';
import assert from 'node:assert/strict';
import proj4 from 'proj4';
import {measurementCell,mapMeasurements,measurementSource} from './measurement-grid.js';
const projection='+proj=utm +zone=43 +datum=WGS84 +units=m +no_defs';
const point=(x,y)=>{const [lng,lat]=proj4(projection,'EPSG:4326',[x,y]);return {lat,lng}};
const grid={epsg:32643,bounds:[780000,1433000,782000,1435000],rows:20,columns:20,cellSizeM:100,cells:Array.from({length:400},(_,i)=>({...point(780000+(i%20+.5)*100,1435000-(Math.floor(i/20)+.5)*100),ndvi:i/400,tempC:30}))};
test('projected lookup includes outer edges and selects east/south internal cells',()=>{
 assert.equal(measurementCell(point(780100,1434900),grid),grid.cells[21]);assert.equal(measurementCell(point(782000,1433000),grid),grid.cells[399]);assert.equal(measurementCell(point(779999,1434999),grid),null);
});
test('display lookup preserves only actual coverage, including rotated bbox corners',()=>{
 const corners=[[780000,1433000],[782000,1433000],[782000,1435000],[780000,1435000]].map(p=>point(...p));
 const corner={lat:Math.max(...corners.map(p=>p.lat)),lng:Math.min(...corners.map(p=>p.lng))};
 assert.equal(measurementCell(corner,grid),null);
 const mapped=mapMeasurements({cells:[grid.cells[210],corner]},grid);assert.equal(mapped.cells[0].ndvi,grid.cells[210].ndvi);assert.equal(mapped.cells[1].ndvi,null);assert.equal(mapped.cells[1].tempC,null);assert.equal(mapped.cells[0].measurementLat,grid.cells[210].lat);
});
test('sources are specific to each measured field',()=>{
 const metadata={provenance:[{field:'ndvi',sceneId:'S2-new',acquiredAt:'2026-09-01'},{field:'tempC',sceneId:'Landsat-new',acquiredAt:'2026-08-01'}]};assert.equal(measurementSource(metadata,'green').sceneId,'S2-new');assert.equal(measurementSource(metadata,'heat').sceneId,'Landsat-new');assert.equal(measurementSource(null,'heat'),null);
});

import {test} from 'node:test';
import assert from 'node:assert/strict';
import {bearing, relativeBearing, queryMock, queryGrid, projectCells, temperatureRange, layerFraction, MOCK_ORIGIN, mockGrid} from './layers.js';

test('cards cross north without a 360-degree jump',()=>{
 assert.equal(relativeBearing(5,355),10);
 assert.equal(relativeBearing(355,5),-10);
 assert.ok(Math.abs(bearing({lat:26,lng:80},{lat:27,lng:80}))<.01);
});
test('mock reference returns labeled synthetic grid with no invented AI answer',()=>{
 const response=queryMock({...MOCK_ORIGIN,heading:0,question:''});
 assert.equal(response.layers.source,'mock');
 assert.ok(response.layers.grid.cells.length>0);
 assert.equal(response.answer,null);
 assert.equal(response.scenario,null);
 assert.ok(mockGrid.cells.some(cell=>cell.ndvi===null && cell.tempC===null));
});
test('outside coverage and invalid coordinates return empty data',()=>{
 for(const point of [{lat:0,lng:0},{lat:null,lng:80},{lat:NaN,lng:80}]){
  const response=queryMock({...point,heading:0,question:''});
  assert.equal(response.layers.status,'no_data');
  assert.deepEqual(response.layers.grid.cells,[]);
 }
});
test('projection keeps only cells in front and excludes the origin cell',()=>{
 const north=projectCells(mockGrid,MOCK_ORIGIN,0);
 assert.equal(north.length,1);
 assert.equal(north[0].tempC,37);
 assert.equal(north[0].x,0);
 const east=projectCells(mockGrid,MOCK_ORIGIN,90);
 assert.equal(east.length,1);
 assert.equal(east[0].ndvi,.48);
 assert.deepEqual(projectCells(mockGrid,null,0),[]);
});
test('satellite grids never leak outside their coverage or accept malformed cells',()=>{
 assert.equal(queryGrid(mockGrid,MOCK_ORIGIN).cells.length,9);
 assert.deepEqual(queryGrid(mockGrid,{lat:0,lng:0}).cells,[]);
 assert.deepEqual(queryGrid(mockGrid,null).cells,[]);
 assert.deepEqual(queryGrid({bbox:[],cells:[{}]},MOCK_ORIGIN).cells,[]);
});

test('heat scale contains all measured temperatures and distinguishes values above 43 C',()=>{
 const cells=[{tempC:41.8168},{tempC:43.5},{tempC:44.6112},{tempC:null}];
 const range=temperatureRange(cells);
 assert.deepEqual(range,[41,45]);
 assert.ok(layerFraction(cells[1],'heat',range)<layerFraction(cells[2],'heat',range));
 for(const cell of cells.slice(0,3))assert.ok(cell.tempC>=range[0]&&cell.tempC<=range[1]);
});

test('missing measurements never get a heat range or overlay color value',()=>{
 assert.equal(temperatureRange([{tempC:null},{tempC:NaN}]),null);
 assert.equal(layerFraction({tempC:null},'heat',[41,45]),null);
 assert.equal(layerFraction({tempC:43},'heat',null),null);
 assert.equal(layerFraction({ndvi:null},'green'),null);
 assert.equal(layerFraction({ndvi:-.2},'green'),0);
});

test('constant temperature datasets still have a usable display scale',()=>{
 assert.deepEqual(temperatureRange([{tempC:42},{tempC:42}]),[42,43]);
 assert.equal(layerFraction({tempC:42},'heat',[42,43]),0);
});

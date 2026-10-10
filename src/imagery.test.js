import test from 'node:test';
import assert from 'node:assert/strict';
import {cellImageUV} from './imagery.js';
const image={cellRows:2,cellColumns:2,cells:[{lat:2,lng:1,row:0,column:0},{lat:1,lng:2,row:1,column:1}]};
test('satellite crops keep north at the top and each cell in its own image region',()=>{
 assert.deepEqual(cellImageUV({lat:2,lng:1},image),{u0:0,u1:.5,v0:.5,v1:1});
 assert.deepEqual(cellImageUV({lat:1,lng:2},image),{u0:.5,u1:1,v0:0,v1:.5});
});
test('imagery cannot be mapped onto cells outside its real coverage',()=>{
 assert.equal(cellImageUV({lat:9,lng:9},image),null);
 assert.equal(cellImageUV({lat:2,lng:1},null),null);
});

import {textureSources} from './imagery.js';
test('AI texture requires ready provenance and falls back to original',()=>{
 const meta={image:'/original.png',superResolvedImage:'/ai.png',superResolution:{status:'ready',displayOnly:true}};
 assert.deepEqual(textureSources(meta,'ai'),['/ai.png','/original.png']);
 assert.deepEqual(textureSources({...meta,superResolution:{status:'fallback'}},'ai'),['/original.png']);
 assert.deepEqual(textureSources(meta,'original'),['/original.png']);
});

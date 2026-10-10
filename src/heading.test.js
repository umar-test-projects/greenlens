import {test} from 'node:test';
import assert from 'node:assert/strict';
import {headingFromEvent, normalize} from './heading.js';
test('heading wraps across north',()=>{assert.equal(normalize(-5),355);assert.equal(normalize(365),5)});
test('accepts compass readings but rejects relative or invalid sensors',()=>{
 assert.equal(headingFromEvent({webkitCompassHeading:42}),42);
 assert.equal(headingFromEvent({absolute:true,alpha:90}),270);
 assert.equal(headingFromEvent({absolute:false,alpha:90}),null);
 assert.equal(headingFromEvent({webkitCompassHeading:NaN}),null);
 assert.equal(headingFromEvent({webkitCompassHeading:20,webkitCompassAccuracy:-1}),null);
});

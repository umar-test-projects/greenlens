import test from 'node:test';
import assert from 'node:assert/strict';
import {openToolsKeyboard} from './tools-focus.js';

test('opening tools focuses its first action and Escape closes it',()=>{
 const events=new EventTarget();let focused='',closed=0;
 const dispose=openToolsKeyboard({querySelector:()=>({focus:()=>focused='action'})},
  {focus:()=>focused='trigger'},()=>closed++,events);
 assert.equal(focused,'action');
 const other=new Event('keydown');other.key='ArrowDown';events.dispatchEvent(other);
 assert.equal(closed,0);
 const escape=new Event('keydown',{cancelable:true});escape.key='Escape';events.dispatchEvent(escape);
 assert.equal(closed,1);assert.equal(escape.defaultPrevented,true);
 dispose();assert.equal(focused,'trigger');
 events.dispatchEvent(escape);assert.equal(closed,1,'closed tools must release their listener');
});

test('empty tools remain dismissible and cleanup tolerates a missing trigger',()=>{
 const events=new EventTarget();let closed=0;
 const dispose=openToolsKeyboard({querySelector:()=>null},null,()=>closed++,events);
 const escape=new Event('keydown');escape.key='Escape';events.dispatchEvent(escape);
 assert.equal(closed,1);assert.doesNotThrow(dispose);
});

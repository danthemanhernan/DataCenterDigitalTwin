import test from 'node:test';
import assert from 'node:assert/strict';
import {defaults,simulate,tests,validate} from './model.js';
for(const [name,patch,check] of tests) test(name,()=>assert.ok(check(simulate({...defaults,...patch}))));
test('rejects invalid model and accepts boundary values',()=>{
 assert.ok(!validate({...defaults,maxFan:2}));
 assert.ok(!validate({...defaults,topic:'test/#'}));
 assert.ok(validate({...defaults,baseLoad:0,flow:0}));
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
let installed=true;try{require.resolve('yt-cast-receiver');}catch{installed=false;}
test('optional pinned dependency APIs work after patches',{skip:!installed},async()=>{
 const mod=require('yt-cast-receiver');assert.equal(typeof mod.default,'function');assert.equal(typeof mod.Player,'function');
 const query=require('query-string');assert.deepEqual([...query.parse('v=a&v=b').v],['a','b']);assert.equal(query.parse('name=A%20B').name,'A B');
 assert.equal(require('ejs').compile('<name><%= name %></name>')({name:'A&B'}),'<name>A&amp;B</name>');
 const uuid=require('uuid');assert.ok(uuid.validate(uuid.v4()));
 const {Window}=await import('happy-dom');const window=new Window();assert.equal(typeof window.document.createElement('canvas').getContext,'function');await window.happyDOM.close();
});

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
test('installer pins checked Node and helper PATH without enabling service',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'aperture-setup-'));
 const home=path.join(root,'home'),bin=path.join(root,'bin'),runtime=path.join(root,'runtime');
 await Promise.all([home,bin,runtime].map(p=>fs.mkdir(p,{mode:0o700})));
 // Mock the bus preflight with a marker file; never contact a real user bus.
 const source=path.join(root,'source');await fs.cp(fileURLToPath(new URL('..',import.meta.url)),source,{recursive:true,filter:p=>!p.split(path.sep).includes('node_modules')});
 const fixture=path.join(source,'setup.sh');const installer=await fs.readFile(fixture,'utf8');
 assert.equal(installer.split('[ -S "$XDG_RUNTIME_DIR/bus" ]').length,2);
 await fs.writeFile(fixture,installer.replace('[ -S "$XDG_RUNTIME_DIR/bus" ]','[ -f "$XDG_RUNTIME_DIR/bus" ]'));
 await fs.writeFile(path.join(runtime,'bus'),'mock');
 const executable=async(name,body)=>fs.writeFile(path.join(bin,name),'#!/bin/sh\n'+body,{mode:0o700});
 try{
  await executable('id','echo 1000\n');
  await executable('node',`if [ "$1" = -p ]; then printf '%s\\n' '${bin}/node'; else printf '%s\\n' "$*" >> '${root}/node.log'; fi\n`);
  await executable('npm','exit 0\n');await executable('pactl','exit 0\n');await executable('mpv','exit 0\n');
  await executable('systemctl',`printf '%s\\n' "$*" >> '${root}/systemctl.log'\n`);
  execFileSync('/bin/sh',[fixture,'--install','192.168.1.5'],{env:{...process.env,HOME:home,PATH:bin+':/usr/bin:/bin',XDG_RUNTIME_DIR:runtime},stdio:'pipe'});
  const builds=await fs.readdir(path.join(home,'.local/share/aperture-cast'));
  const run=path.join(home,'.local/share/aperture-cast',builds[0],'run.sh');
  const script=await fs.readFile(run,'utf8');assert.ok(script.includes(`exec "${bin}/node" receiver.mjs`));assert.ok(script.includes(`PATH="${bin}:/usr/local/bin:/usr/bin:/bin"`));
  execFileSync('/bin/sh',[run],{env:{PATH:'/nonexistent'},stdio:'pipe'});
  assert.match(await fs.readFile(path.join(root,'node.log'),'utf8'),/receiver.mjs/);
  assert.equal((await fs.readFile(path.join(root,'systemctl.log'),'utf8')).trim(),'--user daemon-reload');
 }finally{await fs.rm(root,{recursive:true,force:true});}
});

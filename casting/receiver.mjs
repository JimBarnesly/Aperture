import fs from 'node:fs/promises';
import {createRequire} from 'node:module';
import path from 'node:path';
import net from 'node:net';
import {Mpv} from './mpv.mjs';
import {makePlayer} from './player.mjs';
import {privateRuntime,privateLogger} from './safety.mjs';
import {createResolver} from './resolver.mjs';
process.umask(0o077);
let receiver,mpv,resolver,runtime,closing=false;
async function shutdown(code=0){
 if(closing)return;closing=true;
 const force=setTimeout(()=>process.exit(code||1),5000);force.unref();
 try{await receiver?.stop();}catch{}try{await resolver?.dispose();}catch{}
 mpv?.close();if(runtime)await fs.rm(runtime,{recursive:true,force:true});process.exit(code);
}
process.on('SIGINT',()=>shutdown());process.on('SIGTERM',()=>shutdown());
process.on('uncaughtException',()=>{console.error('Aperture casting stopped after a runtime error. No credential details were logged.');void shutdown(1);});
process.on('unhandledRejection',()=>{console.error('Aperture casting stopped after an asynchronous error.');void shutdown(1);});
try {
 if(process.getuid()===0)throw Error('Run as the same non-root user as Kodi');
 const bind=process.env.APERTURE_CAST_BIND;
 if(!bind||net.isIP(bind)!==4||bind==='0.0.0.0'||bind.startsWith('127.'))throw Error('Set APERTURE_CAST_BIND to the Pi LAN IPv4 address');
 runtime=await privateRuntime();
 const {default:Receiver,Player}=createRequire(import.meta.url)('yt-cast-receiver');
 resolver=await createResolver();mpv=new Mpv(path.join(runtime,'mpv.sock'));await mpv.start();
 const player=makePlayer(Player,mpv,(v,s)=>resolver.resolve(v,s));
 receiver=new Receiver(player,{
   dataStore:false,logger:privateLogger(),logLevel:'error',
   device:{name:'Aperture Music',brand:'Aperture',model:'Experimental DIAL audio receiver'},
   dial:{port:8099,bindToAddresses:[bind],corsAllowOrigins:false},
   app:{enableAutoplayOnConnect:false}
 });
 receiver.on('error',()=>console.error('Aperture casting connection error; try reconnecting from the phone.'));
 mpv.on('end-file',event=>{if(event.reason==='eof'&&!closing)void player.next().catch(()=>console.error('Could not advance the music queue.'));});
 mpv.on('fault',()=>{if(!closing)void shutdown(1);});
 await receiver.start();console.log('Aperture Music receiver is listening. Discovery and audible playback still need a phone test.');
}catch(e){console.error(e?.message?.startsWith('Set APERTURE')||e?.message?.startsWith('Run as')?e.message:'Aperture casting could not start. Check packages, active audio session and LAN address.');await shutdown(1);}

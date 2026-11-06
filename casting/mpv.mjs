import {spawn} from 'node:child_process';
import net from 'node:net';
import {EventEmitter} from 'node:events';
import {mediaUrl, numberIn} from './safety.mjs';
export class Mpv extends EventEmitter {
  constructor(socketPath, options={}) { super(); this.path=socketPath; this.spawn=options.spawn||spawn; this.connect=options.connect||net.connect; this.pending=new Map(); this.id=0; this.buffer=''; }
  async start() {
    this.proc=this.spawn('mpv',['--no-config','--load-scripts=no','--ytdl=no','--idle=yes','--vid=no','--vo=null','--ao=pulse','--volume=20','--volume-max=100','--no-terminal',`--input-ipc-server=${this.path}`],{stdio:'ignore',shell:false});
    let spawnError;
    this.proc.on('error',e=>{spawnError=e;this.emit('fault');});
    this.proc.on('exit',()=>{this.rejectPending();this.emit('fault');});
    for(let i=0;i<40;i++) {
      if(spawnError) throw Error('mpv could not start');
      try {await this.open(); return;} catch {await new Promise(r=>setTimeout(r,100));}
    }
    this.close(); throw Error('mpv IPC unavailable');
  }
  open() {return new Promise((resolve,reject)=>{
    const s=this.connect(this.path); const fail=()=>{s.destroy();reject(Error('IPC unavailable'));};
    s.once('error',fail); s.once('connect',()=>{s.removeListener('error',fail);s.on('error',()=>this.rejectPending());s.on('close',()=>this.rejectPending());s.on('data',d=>this.receive(d));this.socket=s;resolve();});
  });}
  receive(chunk) {
    this.buffer+=chunk.toString('utf8');
    if(this.buffer.length>1048576){this.socket?.destroy();this.buffer='';this.rejectPending();return;}
    let i;
    while((i=this.buffer.indexOf('\n'))>=0){const l=this.buffer.slice(0,i);this.buffer=this.buffer.slice(i+1);let m;try{m=JSON.parse(l);}catch{continue;}
      if(m.request_id!==undefined){const p=this.pending.get(m.request_id);if(p){clearTimeout(p.timer);this.pending.delete(m.request_id);m.error==='success'?p.resolve(m.data):p.reject(Error('mpv command failed'));}}
      if(m.event)this.emit(m.event,m);
    }
  }
  command(...command) {return new Promise((resolve,reject)=>{
    if(!this.socket||this.socket.destroyed)return reject(Error('mpv disconnected'));
    const request_id=++this.id;const timer=setTimeout(()=>{this.pending.delete(request_id);reject(Error('mpv timeout'));},5000);
    this.pending.set(request_id,{resolve,reject,timer});
    this.socket.write(JSON.stringify({command,request_id})+'\n',e=>{if(e){clearTimeout(timer);this.pending.delete(request_id);reject(Error('mpv write failed'));}});
  });}
  async load(url, position=0, signal) {
    const safe=mediaUrl(url), start=numberIn(position,0,864000);
    if(signal?.aborted)throw Error('Cancelled');
    await this.command('stop');
    await this.command('set_property','start',start?String(start):'none');
    let cleanup=()=>{};
    const loaded=new Promise((resolve,reject)=>{
      cleanup=()=>{clearTimeout(timer);this.off('file-loaded',ok);this.off('end-file',bad);this.off('fault',fault);signal?.removeEventListener('abort',cancel);};
      const ok=()=>{cleanup();resolve();};
      const bad=m=>{if(m.reason==='error'){cleanup();reject(Error('Media playback failed'));}};
      const fault=()=>{cleanup();reject(Error('mpv exited'));};
      const cancel=()=>{cleanup();reject(Error('Cancelled'));};
      const timer=setTimeout(()=>{cleanup();reject(Error('Media load timeout'));},30000);
      this.once('file-loaded',ok);this.on('end-file',bad);this.once('fault',fault);signal?.addEventListener('abort',cancel,{once:true});
      if(signal?.aborted)cancel();
    });
    // Attach rejection handling immediately while waiting for the command reply.
    loaded.catch(()=>{});
    try {
      if(signal?.aborted)throw Error('Cancelled');
      await this.command('loadfile',safe,'replace');
      await loaded;
      if(signal?.aborted)throw Error('Cancelled');
      await this.command('set_property','pause',false);
    }finally{cleanup();}
  }
  rejectPending(){for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(Error('mpv disconnected'));}this.pending.clear();}
  close(){this.socket?.destroy();this.rejectPending();this.proc?.kill('SIGTERM');}
}

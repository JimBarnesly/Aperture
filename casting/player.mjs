import {videoId, numberIn} from './safety.mjs';
// Dependency injection keeps protocol/media adapter tests offline and credential-free.
export function makePlayer(Base, mpv, resolveMedia) {
  return new class extends Base {
    constructor(){super();this.generation=0;this.abort=null;this.failures=0;}
    async doPlay(video,position=0){
      const id=videoId(video.id);numberIn(position,0,864000);
      this.abort?.abort();const abort=this.abort=new AbortController();const generation=++this.generation;
      try {
        const url=await resolveMedia({...video,id},abort.signal);
        if(abort.signal.aborted||generation!==this.generation)return false;
        await mpv.load(url,position,abort.signal);
        if(abort.signal.aborted||generation!==this.generation)return false;
        this.failures=0;return true;
      }catch{this.failures++;return false;}
    }
    async doPause(){await mpv.command('set_property','pause',true);return true;}
    async doResume(){await mpv.command('set_property','pause',false);return true;}
    async doStop(){++this.generation;this.abort?.abort();await mpv.command('stop');return true;}
    async doSeek(position){await mpv.command('seek',numberIn(position,0,864000),'absolute');return true;}
    async doSetVolume(v){await mpv.command('set_property','volume',numberIn(v.level,0,100));await mpv.command('set_property','mute',Boolean(v.muted));return true;}
    async doGetVolume(){return {level:await mpv.command('get_property','volume'),muted:await mpv.command('get_property','mute')};}
    async doGetPosition(){return (await mpv.command('get_property','time-pos'))||0;}
    async doGetDuration(){return (await mpv.command('get_property','duration'))||0;}
  }();
}

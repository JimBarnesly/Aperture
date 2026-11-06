import {createRequire} from 'node:module';
import {videoId,mediaUrl,privateLogger} from './safety.mjs';
// These optional third-party packages are loaded only for an explicitly started receiver.
// The phone's per-video CTT is used only for the matching YouTube request, never saved/logged.
export async function createResolver() {
  const require=createRequire(import.meta.url);
  const {InnertubeFactory}=require('volumio-yt-support');
  const lib=require('volumio-yt-support/dist/innertube.js');
  const wrapper=await InnertubeFactory.getWrappedInstance({jsRuntime:'node',locale:{region:'AU',language:'en'},logger:privateLogger()});
  let tail=Promise.resolve();
  return {
    resolve(video,signal){
      const run=tail.then(async()=>{
        const id=videoId(video.id);if(signal.aborted)throw Error('Cancelled');
        const inner=wrapper.getInnertube();
        const priorUser=inner.session.context.user;
        // No account cookie or persistent account login is supplied.
        inner.session.context.user={...(priorUser||{})};
        delete inner.session.context.user.credentialTransferTokens;
        if(video.context?.ctt)inner.session.context.user.credentialTransferTokens=[{scope:'VIDEO',token:video.context.ctt}];
        try {
          const pot=(await wrapper.generatePoToken(id)).poToken;
          if(signal.aborted)throw Error('Cancelled');
          const response=await inner.actions.execute('/player',{
            videoId:id,client:'YTMUSIC',isMdxPlayback:true,
            serviceIntegrityDimensions:{poToken:pot},
            playbackContext:{contentPlaybackContext:{signatureTimestamp:inner.session.player?.signature_timestamp||0}}
          });
          if(signal.aborted)throw Error('Cancelled');
          const info=new lib.YT.VideoInfo([response],inner.actions,lib.Utils.generateRandomString(16));
          if(info.playability_status?.status!=='OK')throw Error('Video is not playable');
          const format=info.chooseFormat({type:'audio',format:'any',quality:'best'});
          const url=new URL(await format.decipher(inner.session.player));
          if(pot)url.searchParams.set('pot',pot);
          const safe=mediaUrl(url.toString());
          const test=await fetch(safe,{headers:{Range:'bytes=0-1023'},signal});
          try{if(!test.ok)throw Error('Stream is unavailable');}finally{await test.body?.cancel();}
          return safe;
        }finally{inner.session.context.user=priorUser;}
      });
      tail=run.catch(()=>{});return run;
    },
    dispose(){return wrapper.dispose();}
  };
}

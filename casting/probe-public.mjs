// Explicit, credential-free network probe. Does not start discovery or audio.
import {createResolver} from './resolver.mjs';
if(process.argv[2]!=='--run'){console.log('Usage: node probe-public.mjs --run [public-music-video-id]');process.exit(0);}
const timeout=setTimeout(()=>{console.error('Public stream probe timed out');process.exit(2);},45000);
let resolver;
try {
 resolver=await createResolver();
 console.log('Resolver initialized');
 const stream=await resolver.resolve({id:process.argv[3]||'dQw4w9WgXcQ'},new AbortController().signal);
 if(!new URL(stream).hostname.endsWith('.googlevideo.com'))throw Error('Unexpected stream host');
 console.log('Public music stream resolved and HTTP range read succeeded');
 console.log('This does not verify Premium, phone discovery, audio, or queues.');
}catch{console.error('Public stream probe failed; no credentials or stream URLs logged.');process.exitCode=1;}
finally{await resolver?.dispose();clearTimeout(timeout);}

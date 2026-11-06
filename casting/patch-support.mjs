// Fail closed if upstream layout changes. Avoid implicit npx/Deno execution.
import {readFileSync,writeFileSync} from 'node:fs';
const target=new URL('./node_modules/volumio-yt-support/dist/lib/innertube/Spawn.js',import.meta.url);
const original='const denoStatus = (0, Utils_1.isDenoInstalled)();';
const replacement="const denoStatus = runtime === 'node' ? { installed: false } : (0, Utils_1.isDenoInstalled)();";
const text=readFileSync(target,'utf8');
if(!text.includes(replacement)) {
if(text.split(original).length!==2)throw Error('Unexpected support helper; refusing to patch');
writeFileSync(target,text.replace(original,replacement));
}
// query-string 7 requires CommonJS. The fixed decoder is ESM-only; adapt only
// its single export, preserving upstream algorithm and licence unchanged.
const decoderRoot=new URL('./node_modules/decode-uri-component/',import.meta.url);
const manifest=JSON.parse(readFileSync(new URL('package.json',decoderRoot),'utf8'));
if(manifest.version!=='0.5.1')throw Error('Unexpected decoder version');
const decoderFile=new URL('index.js',decoderRoot);
const decoder=readFileSync(decoderFile,'utf8');
const oldExport='export default function decodeUriComponent(encodedURI)';
const newExport='module.exports = function decodeUriComponent(encodedURI)';
if(!decoder.includes(newExport)) {
 if(decoder.split(oldExport).length!==2)throw Error('Unexpected decoder source');
 writeFileSync(decoderFile,decoder.replace(oldExport,newExport));
}
manifest.type='commonjs';
writeFileSync(new URL('package.json',decoderRoot),JSON.stringify(manifest,null,2)+'\n');
// Upstream create otherwise leaks the helper if session-token initialization fails.
const wrapperFile=new URL('./node_modules/volumio-yt-support/dist/lib/innertube/Wrapper.js',import.meta.url);
const wrapper=readFileSync(wrapperFile,'utf8');
const init='await __classPrivateFieldGet(instance, _InnertubeWrapper_instances, "m", _InnertubeWrapper_init).call(instance, config);';
const safeInit='try { '+init+' } catch (error) { await instance.dispose(); throw error; }';
if(!wrapper.includes(safeInit)) {
 if(wrapper.split(init).length!==2)throw Error('Unexpected wrapper initialization');
 writeFileSync(wrapperFile,wrapper.replace(init,safeInit));
}

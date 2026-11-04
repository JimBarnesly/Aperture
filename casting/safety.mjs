import fs from 'node:fs/promises';
import path from 'node:path';
export function videoId(value) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9_-]{11}$/.test(value)) throw Error('Invalid video identifier');
  return value;
}
export function mediaUrl(value) {
  const u = new URL(value);
  if (u.protocol !== 'https:' || u.username || u.password || !(u.hostname === 'googlevideo.com' || u.hostname.endsWith('.googlevideo.com'))) throw Error('Unexpected media origin');
  return u.toString();
}
export function numberIn(value, min, max) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < min || n > max) throw Error('Invalid control value');
  return n;
}
export async function privateRuntime(base = process.env.XDG_RUNTIME_DIR) {
  if (!base || !path.isAbsolute(base)) throw Error('An active user runtime directory is required');
  const st = await fs.lstat(base);
  if (!st.isDirectory() || st.isSymbolicLink() || st.uid !== process.getuid() || (st.mode & 0o077)) throw Error('User runtime directory is not private');
  return fs.mkdtemp(path.join(base, 'aperture-cast-'));
}
// Third-party log payloads can include credential-transfer tokens and signed URLs.
// Never pass their messages to the journal, even at info/error level.
export function privateLogger() {
  const noop = () => {};
  return {setLevel:noop,debug:noop,info:noop,warn:noop,error:noop,verbose:noop};
}

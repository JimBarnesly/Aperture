#!/usr/bin/env bash
# Diagnostic-only child launcher: no attach, host core policy, or personal profile.
set -Eeuo pipefail
runtime=${APERTURE_MOVIES_RUNTIME:-}
out=${APERTURE_MOVIES_OUT:-}
[[ -d "$runtime" && "${runtime##*/}" == aperture-movies-qa.* &&
   "${HOME:-}" == "$runtime/home" && "${KODI_DATA:-}" == "$runtime/data" && -d "$out" ]] || {
  echo 'Native capture requires the disposable Movies fixture profile' >&2; exit 2;
}
[[ $# -gt 0 ]] || exit 2
command -v gdb >/dev/null
# Never persist a potentially huge raw core or enable network symbol downloads.
ulimit -c 0
export DEBUGINFOD_URLS=
{
  uname -sm
  dpkg-query -W -f='${Package} ${Version} ${Architecture}\n' kodi-bin libpython3.14 libgl1-mesa-dri libc6 2>/dev/null || true
  sha256sum "$1"
  readelf -n "$1" 2>/dev/null || true
} > "$out/native-environment.txt"
cat > "$runtime/native-debug.gdb" <<'GDB'
set pagination off
set confirm off
set debuginfod enabled off
set print elements 32
set print frame-arguments scalars
set auto-load off
set disable-randomization off
handle SIGPIPE nostop noprint pass
run
if $_isvoid($_exitcode)
  thread apply all bt 40
  info registers
  info sharedlibrary
  quit 139
else
  quit $_exitcode
end
GDB
# Same runtime bound as normal acceptance, including traceback production.
# GDB starts only this child as the unprivileged fixture user; never attaches.
exec timeout --kill-after=5s 240s gdb --batch --nx --quiet \
  -x "$runtime/native-debug.gdb" --args "$@" > "$out/native-backtrace.txt" 2>&1

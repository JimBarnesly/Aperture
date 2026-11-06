#!/usr/bin/env bash
# Disposable real Kodi acceptance; never uses a personal profile or opens an RPC server.
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
OUT="${APERTURE_MOVIES_OUT:-$ROOT/build/menus-smoke}"
SCENARIO="${APERTURE_MOVIES_SCENARIO:-single}"
[[ "$SCENARIO" =~ ^(single|default|multiple|empty)$ ]] || { echo 'Invalid source scenario' >&2; exit 2; }
[[ ! -d "$OUT" || -z "$(ls -A "$OUT")" ]] || { echo 'Output directory must be empty; preserving prior evidence' >&2; exit 2; }
mkdir -p "$OUT"; OUT=$(cd "$OUT" && pwd)
printf '{"status":"not_run","reason":"GUI acceptance has not completed"}\n' > "$OUT/result.json"
printf '%s\n' "${GITHUB_SHA:-uncommitted-local-source}" > "$OUT/tested-revision.txt"
RUNTIME=$(mktemp -d /tmp/aperture-movies-qa.XXXXXXXX)
export APERTURE_MOVIES_OUT="$OUT" APERTURE_MOVIES_RUNTIME="$RUNTIME" APERTURE_MOVIES_SCENARIO="$SCENARIO"
export HOME="$RUNTIME/home" KODI_DATA="$RUNTIME/data" KODI_HOME="$RUNTIME/system" KODI_TEMP="$OUT/logs"
export XDG_CONFIG_HOME="$HOME/.config" XDG_CACHE_HOME="$HOME/.cache" XDG_DATA_HOME="$HOME/.local/share" XDG_RUNTIME_DIR="$RUNTIME/run"
export DISPLAY=:93 XAUTHORITY="$RUNTIME/Xauthority" LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
mkdir -p "$HOME" "$KODI_DATA" "$KODI_TEMP" "$XDG_RUNTIME_DIR"; chmod 700 "$XDG_RUNTIME_DIR"
K_PID=''; P_PID=''; X_PID=''
cleanup() {
  local rc=$?
  for pid in "$K_PID" "$P_PID" "$X_PID"; do [[ -z "$pid" ]] || kill "$pid" 2>/dev/null || true; done
  if [[ $rc -ne 0 ]]; then
    python3 - "$OUT/result.json" "$rc" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]); r=json.loads(p.read_text())
if r['status']!='failed':
    r.update(status='failed',reason='Runtime exited before all movie assertions passed',exit_code=int(sys.argv[2]))
p.write_text(json.dumps(r,indent=2)+'\n')
PY
    tail -80 "$KODI_TEMP/kodi.log" 2>/dev/null || true
  fi
}
trap cleanup EXIT
KODI_BIN=$(dpkg -L kodi-bin | grep '/kodi\.bin$' | head -1)
export KODI_BIN_HOME=$(dirname "$KODI_BIN") KODI_BINADDON_PATH="$(dirname "$KODI_BIN")/addons"
"$KODI_BIN" --version | tee "$OUT/kodi-version.txt"
grep -Eq 'Center 21\.3([ .-]|$)' "$OUT/kodi-version.txt" || { echo 'Exact Kodi 21.3 required; refusing to imply version coverage' >&2; exit 2; }
python3 "$ROOT/tools/movies_fixture.py" --root "$ROOT" --runtime "$RUNTIME" --out "$OUT" --scenario "$SCENARIO"
cp "$ROOT/tools/menus_qa_service.py" "$RUNTIME/system/addons/service.aperture.moviesqa/service.py"
# Original synthetic tones only; no private media or provider requests.
ffmpeg -nostdin -loglevel error -f lavfi -i sine=frequency=440:duration=120 -c:a pcm_s16le "$RUNTIME/home-bar.wav"
ffmpeg -nostdin -loglevel error -f lavfi -i color=c=navy:s=640x360:r=10:d=120 -an -c:v mpeg4 "$RUNTIME/home-bar.mp4"
export PULSE_RUNTIME_PATH="$RUNTIME/pulse" PULSE_STATE_PATH="$RUNTIME/pulse-state" PULSE_SERVER="unix:$RUNTIME/pulse/native" PULSE_COOKIE="$RUNTIME/pulse/cookie"
mkdir -m 700 "$PULSE_RUNTIME_PATH" "$PULSE_STATE_PATH"
cat > "$RUNTIME/pulse.pa" <<PULSE
load-module module-native-protocol-unix socket=$RUNTIME/pulse/native auth-cookie=$RUNTIME/pulse/cookie
load-module module-null-sink sink_name=movies_qa
set-default-sink movies_qa
PULSE
pulseaudio --daemonize=no --use-pid-file=no --exit-idle-time=-1 --high-priority=no --realtime=no --disable-shm=yes --disallow-module-loading=yes -n --file="$RUNTIME/pulse.pa" > "$OUT/pulse.log" 2>&1 & P_PID=$!
touch "$XAUTHORITY"; xauth -f "$XAUTHORITY" add "$DISPLAY" . "$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
Xvfb "$DISPLAY" -auth "$XAUTHORITY" -screen 0 1920x1080x24 -nolisten tcp +extension GLX +render > "$OUT/xvfb.log" 2>&1 & X_PID=$!
for _ in {1..100}; do xdpyinfo >/dev/null 2>&1 && pactl info >/dev/null 2>&1 && break; sleep .1; done
xdpyinfo >/dev/null; pactl info > "$OUT/pulse-info.txt"
timeout --kill-after=5s 150s "$KODI_BIN" --windowing=x11 --gl-interface=glx --audio-backend=pulseaudio --debug -fs > "$OUT/kodi.stdout" 2>&1 & K_PID=$!
for _ in {1..1500}; do
  grep -q '"status": "\(passed\|failed\)"' "$OUT/result.json" && break
  kill -0 "$K_PID" 2>/dev/null || { echo 'Kodi exited before acceptance result'; cat "$OUT/kodi.stdout"; exit 1; }
  sleep .1
done
python3 - "$OUT/result.json" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); print(json.dumps(r,indent=2)); assert r['status']=='passed'
PY

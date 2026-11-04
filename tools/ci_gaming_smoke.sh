#!/usr/bin/env bash
# Disposable CI only. Does not configure the host or open any network endpoint.
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
OUT="${APERTURE_GAMING_OUT:-$ROOT/build/gaming-smoke}"
[[ ! -d "$OUT" || -z "$(ls -A "$OUT")" ]] || { echo "Output directory must be empty; prior QA evidence is preserved" >&2; exit 2; }
mkdir -p "$OUT"
RUNTIME=$(mktemp -d /tmp/aperture-gaming-qa.XXXXXXXX)
export APERTURE_GAMING_OUT="$OUT" APERTURE_GAMING_RUNTIME="$RUNTIME"
export HOME="$RUNTIME/home" KODI_DATA="$RUNTIME/data" KODI_HOME="$RUNTIME/system" KODI_TEMP="$OUT/logs"
export XDG_CONFIG_HOME="$HOME/.config" XDG_CACHE_HOME="$HOME/.cache" XDG_DATA_HOME="$HOME/.local/share" XDG_RUNTIME_DIR="$RUNTIME/run"
export DISPLAY=:92 XAUTHORITY="$RUNTIME/Xauthority" LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
mkdir -p "$HOME" "$KODI_DATA" "$KODI_TEMP" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
KODI_BIN=$(dpkg -L kodi-bin | grep '/kodi\.bin$' | head -1)
export KODI_BIN_HOME=$(dirname "$KODI_BIN") KODI_BINADDON_PATH="$(dirname "$KODI_BIN")/addons"
"$KODI_BIN" --version > "$OUT/kodi-version.txt"
python3 "$ROOT/tools/build_pcsx_core.py" --output-dir "$RUNTIME/pcsx" > "$OUT/pcsx-build.log" 2>&1
python3 "$ROOT/tools/gaming_fixture.py" --root "$ROOT" --runtime "$RUNTIME" --out "$OUT" --pcsx "$RUNTIME/pcsx/pcsx_rearmed_libretro.so"
export PULSE_RUNTIME_PATH="$RUNTIME/pulse" PULSE_STATE_PATH="$RUNTIME/pulse-state" PULSE_SERVER="unix:$RUNTIME/pulse/native" PULSE_COOKIE="$RUNTIME/pulse/cookie"
mkdir -m 700 "$PULSE_RUNTIME_PATH" "$PULSE_STATE_PATH"
cat > "$RUNTIME/pulse.pa" <<EOF
load-module module-native-protocol-unix socket=$RUNTIME/pulse/native auth-cookie=$RUNTIME/pulse/cookie
load-module module-null-sink sink_name=gaming_qa
set-default-sink gaming_qa
EOF
X_PID=''; P_PID=''; K_PID=''
cleanup() { for pid in "$K_PID" "$P_PID" "$X_PID"; do [[ -z "$pid" ]] || kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT
pulseaudio --daemonize=no --use-pid-file=no --exit-idle-time=-1 --high-priority=no --realtime=no --disable-shm=yes --disallow-module-loading=yes -n --file="$RUNTIME/pulse.pa" > "$OUT/pulse.log" 2>&1 & P_PID=$!
touch "$XAUTHORITY"; xauth -f "$XAUTHORITY" add "$DISPLAY" . "$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
Xvfb "$DISPLAY" -auth "$XAUTHORITY" -screen 0 1280x720x24 -nolisten tcp +extension GLX +render > "$OUT/xvfb.log" 2>&1 & X_PID=$!
for _ in {1..100}; do xdpyinfo >/dev/null 2>&1 && pactl info >/dev/null 2>&1 && break; sleep .1; done
xdpyinfo >/dev/null; pactl info > "$OUT/pulse-info.txt"
"$KODI_BIN" --standalone > "$OUT/kodi.stdout" 2>&1 & K_PID=$!
for _ in {1..1800}; do
  [[ -f "$OUT/result.json" ]] && break
  kill -0 "$K_PID" 2>/dev/null || { echo 'Kodi exited without test result'; cat "$OUT/kodi.stdout"; exit 1; }
  sleep .1
done
python3 - "$OUT/result.json" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); print(json.dumps(r,indent=2)); assert r['status']=='passed'
PY

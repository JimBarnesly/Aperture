#!/usr/bin/env bash
# Diagnostic only. Never use a real profile, seat, display, input device or bus.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
COMMIT="${GITHUB_SHA:-$(git -C "$ROOT" rev-parse HEAD)}"
OUT="${APERTURE_WAYLAND_OUT:-$ROOT/build/labwc-relaunch}"
[[ ! -d "$OUT" || -z "$(ls -A "$OUT")" ]] || { echo 'Output must be empty'; exit 2; }
mkdir -p "$OUT"
OUT="$(cd -- "$OUT" && pwd)"
printf '{"status":"harness_failure","stage":"preflight","reason":"Harness did not finish"}\n' > "$OUT/result.json"
[[ "$EUID" != 0 ]] || { echo 'Refusing root GUI execution'; exit 2; }
[[ ! -e /dev/dri && ! -e /dev/input ]] || { echo 'Unexpected hardware device tree'; exit 2; }
for command in labwc dbus-run-session wtype grim wlr-randr wayland-info tesseract python3 dpkg-query timeout; do
  command -v "$command" >/dev/null || { echo "Missing prerequisite: $command"; exit 2; }
done
export APERTURE_WAYLAND_ROOT="$ROOT" APERTURE_WAYLAND_OUT="$OUT"
# Runner temp is owned by the container runner, not our disposable user.
# Keep assignment separate from export so mktemp failure cannot be masked.
APERTURE_WAYLAND_RUNTIME="$(mktemp -d /tmp/aperture-labwc.XXXXXXXX)"
export APERTURE_WAYLAND_RUNTIME
export HOME="$APERTURE_WAYLAND_RUNTIME/home"
export XDG_RUNTIME_DIR="$APERTURE_WAYLAND_RUNTIME/run"
export XDG_CONFIG_HOME="$HOME/.config" XDG_DATA_HOME="$HOME/.local/share" XDG_CACHE_HOME="$HOME/.cache"
mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_CACHE_HOME" "$XDG_RUNTIME_DIR" "$APERTURE_WAYLAND_RUNTIME/labwc"
chmod 700 "$APERTURE_WAYLAND_RUNTIME" "$HOME" "$XDG_RUNTIME_DIR"
unset DISPLAY WAYLAND_DISPLAY WAYLAND_SOCKET XDG_SESSION_ID DBUS_SESSION_BUS_ADDRESS DBUS_STARTER_ADDRESS DBUS_STARTER_BUS_TYPE
export DBUS_SYSTEM_BUS_ADDRESS="unix:path=$APERTURE_WAYLAND_RUNTIME/no-system-bus"
export PULSE_SERVER="unix:$APERTURE_WAYLAND_RUNTIME/no-pulse-server"
export WLR_BACKENDS=headless WLR_HEADLESS_OUTPUTS=1 WLR_RENDERER=pixman LABWC_UPDATE_ACTIVATION_ENV=0
export LIBGL_ALWAYS_SOFTWARE=true GALLIUM_DRIVER=llvmpipe EGL_PLATFORM=wayland
export APERTURE_KODI_BIN="$(dpkg -L kodi-bin | grep '/kodi\.bin$' | head -1)"
[[ -x "$APERTURE_KODI_BIN" ]] || { echo 'No distro Kodi binary'; exit 2; }
export KODI_BIN_HOME="$(dirname -- "$APERTURE_KODI_BIN")" KODI_BINADDON_PATH="$(dirname -- "$APERTURE_KODI_BIN")/addons"
"$APERTURE_KODI_BIN" --version > "$OUT/kodi-version.txt" 2>&1
"$APERTURE_KODI_BIN" --help > "$OUT/kodi-help.txt" 2>&1 || true
labwc --version > "$OUT/labwc-version.txt" 2>&1
dpkg-query -W kodi kodi-bin kodi-data labwc libegl-mesa0 libgl1-mesa-dri wtype grim wlr-randr wayland-utils > "$OUT/runtime-packages.txt"
printf '%s\n' "$COMMIT" > "$OUT/commit.txt"
grep -Eq 'Center 21\.3([ .]|$)' "$OUT/kodi-version.txt" || { cat "$OUT/kodi-version.txt"; echo 'Kodi 21.3 required'; exit 2; }
grep -qi wayland "$OUT/kodi-help.txt" || { cat "$OUT/kodi-help.txt"; echo 'Wayland backend not advertised'; exit 2; }
python3 "$ROOT/tools/build_skin.py" > "$OUT/skin-build.log" 2>&1
cat > "$APERTURE_WAYLAND_RUNTIME/labwc/rc.xml" <<'XML'
<?xml version="1.0"?><labwc_config><core><decoration>server</decoration><gap>0</gap></core></labwc_config>
XML
: > "$APERTURE_WAYLAND_RUNTIME/labwc/autostart"
: > "$APERTURE_WAYLAND_RUNTIME/labwc/shutdown"
cat > "$APERTURE_WAYLAND_RUNTIME/session.sh" <<'SESSION'
#!/usr/bin/env bash
exec python3 "$APERTURE_WAYLAND_ROOT/tools/labwc_relaunch_driver.py"
SESSION
chmod 700 "$APERTURE_WAYLAND_RUNTIME/session.sh"
set +e
timeout --signal=TERM --kill-after=10s 12m dbus-run-session -- labwc --debug \
  --config-dir "$APERTURE_WAYLAND_RUNTIME/labwc" --session "$APERTURE_WAYLAND_RUNTIME/session.sh" \
  > "$OUT/labwc.log" 2>&1
RC=$?
set -e
cat "$OUT/result.json"
# Labwc's session exit status is not the Python diagnostic exit status.
python3 - "$OUT/result.json" "$RC" <<'PY'
import json, sys
result=json.load(open(sys.argv[1]))
assert result.get('status')=='passed' and int(sys.argv[2])==0, result
PY

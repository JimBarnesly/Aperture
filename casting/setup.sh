#!/bin/sh
# Optional EXPERIMENTAL sidecar. Nothing is installed without --install.
set -eu
mode=${1:---check}
case "$mode" in --check|--install) ;; *) echo 'Usage: setup.sh --check | --install LAN_IPV4'; exit 2;; esac
[ "$(id -u)" -ne 0 ] || { echo 'Run as the normal Kodi user, not root.'; exit 1; }
for cmd in node npm mpv pactl systemctl; do
  command -v "$cmd" >/dev/null || { echo "Missing $cmd. Install the appropriate Raspberry Pi OS package first."; exit 1; }
done
node -e 'if(Number(process.versions.node.split(".")[0])<20)process.exit(1)' || { echo 'Node 20 or newer required. Do not upgrade the OS just for casting.'; exit 1; }
node_bin=$(node -p 'process.execPath')
case "$node_bin" in /*) ;; *) echo 'Cannot resolve an absolute Node executable.'; exit 1;; esac
case "$node_bin" in *[!a-zA-Z0-9_./-]*) echo 'Unsupported Node executable path.'; exit 1;; esac
node_dir=$(dirname -- "$node_bin")
pactl info >/dev/null || { echo 'No working PulseAudio/PipeWire session for this user. Do not run this installer with sudo.'; exit 1; }
[ -n "${XDG_RUNTIME_DIR:-}" ] && [ -S "$XDG_RUNTIME_DIR/bus" ] || { echo 'No active user session bus. Log into the Pi desktop first.'; exit 1; }
[ "$mode" = --install ] || { echo 'Basic prerequisites present. This does not verify casting or audio.'; exit 0; }
# Reject shell/systemd metacharacters in generated service paths.
case "$HOME" in *[!a-zA-Z0-9_./-]*) echo 'Unsupported home path for this experimental installer.'; exit 1;; esac
printf '%s\n' 'Installing experimental YouTube-specific receiver dependencies. Pi playback is not yet verified.'
bind=${2:-}
node -e 'const a=process.argv[1]; if(require("node:net").isIP(a)!==4||a==="0.0.0.0"||a.startsWith("127."))process.exit(1)' "$bind" || { echo 'Supply the Pi LAN IPv4 address. No wildcard listener is allowed.'; exit 1; }
src=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
umask 077
root="$HOME/.local/share/aperture-cast"
mkdir -p "$root"
work=$(mktemp -d "$root/build.XXXXXX")
cp "$src"/*.mjs "$src/package.json" "$src/package-lock.json" "$work/"
cp -R "$src/test" "$work/test"
cp "$src/setup.sh" "$work/setup.sh"
# --install is an explicit opt-in to the pinned third-party packages below.
# npm executes the upstream compile step required by the YouTube.js dependency.
(cd "$work" && npm ci --no-audit --no-fund)
(cd "$work" && node patch-support.mjs && npm audit --omit=dev && node --test test/*.test.mjs)
for f in "$work"/*.mjs; do node --check "$f"; done
mkdir -p "$HOME/.config/systemd/user"
unit="$HOME/.config/systemd/user/aperture-cast.service"
[ ! -e "$unit" ] || cp "$unit" "$unit.backup.$(date +%Y%m%d%H%M%S)"
# Use a wrapper so shell path quoting is not confused with systemd command syntax.
printf '#!/bin/sh\nPATH="%s:/usr/local/bin:/usr/bin:/bin"\nexport PATH\ncd "%s"\nexec "%s" receiver.mjs\n' "$node_dir" "$work" "$node_bin" > "$work/run.sh"
chmod 700 "$work/run.sh"
cat > "$unit" <<UNIT
[Unit]
Description=Aperture experimental YouTube Music receiver
After=pipewire-pulse.service wireplumber.service
[Service]
Type=simple
WorkingDirectory=$work
Environment=APERTURE_CAST_BIND=$bind
Environment=HOME=$HOME
ExecStart=/bin/sh "$work/run.sh"
UMask=0077
NoNewPrivileges=yes
Restart=no
TimeoutStopSec=10
[Install]
WantedBy=default.target
UNIT
systemctl --user daemon-reload
printf '\nInstalled but NOT started or enabled at boot.\n'
printf 'Start a supervised test: systemctl --user start aperture-cast\n'
printf 'Stop it: systemctl --user stop aperture-cast\n'
printf 'No Kodi, Bluetooth, firewall, or audio-device settings were changed.\n'

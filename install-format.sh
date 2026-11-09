#!/bin/sh
set -eu

# Install as the Kodi user on Pi OS, or root on LibreELEC.
if [ -n "${APERTURE_KODI_HOME:-}" ]; then
  KODI_HOME=$APERTURE_KODI_HOME
elif [ "$(id -u)" -eq 0 ] && [ -d /storage/.kodi ]; then
  KODI_HOME=/storage/.kodi
elif [ "$(id -u)" -eq 0 ]; then
  echo "ERROR: Run as the Kodi desktop user, not with sudo (LibreELEC is detected automatically)." >&2
  echo "For a custom profile, explicitly set APERTURE_KODI_HOME to its absolute path." >&2
  exit 1
else
  KODI_HOME="${HOME}/.kodi"
fi
case "$KODI_HOME" in /*) ;; *) echo "ERROR: Kodi home must be an absolute path" >&2; exit 1;; esac
# Replacing an enabled add-on while Kodi is executing it can mix old/new files.
if command -v pidof >/dev/null 2>&1; then
  RUNNING=$(pidof kodi.bin kodi-wayland kodi-x11 kodi-gbm kodi 2>/dev/null || true)
elif command -v pgrep >/dev/null 2>&1; then
  RUNNING=$(pgrep -x 'kodi|kodi.bin|kodi-wayland|kodi-x11|kodi-gbm' || true)
else
  echo "ERROR: Cannot check whether Kodi is running (pidof or pgrep required)." >&2
  exit 1
fi
[ -z "$RUNNING" ] || { echo "ERROR: Stop Kodi before installing Format, then restart it afterwards." >&2; exit 1; }
ADDONS="$KODI_HOME/addons"
TARGET="$ADDONS/plugin.audio.aperture.format"
mkdir -p "$ADDONS"
LOCK="$KODI_HOME/.aperture-format-install.lock"
mkdir "$LOCK" 2>/dev/null || { echo "ERROR: A Format install is already running (lock: $LOCK)" >&2; exit 1; }
STAGE=""
cleanup() {
  [ -z "$STAGE" ] || rm -rf "$STAGE"
  rmdir "$LOCK" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
STAGE=$(mktemp -d "$KODI_HOME/.aperture-format.XXXXXX")
# Prefer the files shipped alongside this exact installer, including offline
# source archives. A detached script must name an immutable revision explicitly.
SOURCE=${APERTURE_SOURCE_DIR:-}
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -z "$SOURCE" ] && [ -d "$SCRIPT_DIR/format-kodi" ]; then
  SOURCE=$SCRIPT_DIR
fi
BASE=""
if [ -z "$SOURCE" ]; then
  REF=${APERTURE_REF:-}
  case "$REF" in
    *[!0-9a-fA-F]*|"") echo "ERROR: A detached installer requires APERTURE_REF set to a full 40-character commit SHA, or APERTURE_SOURCE_DIR." >&2; exit 1;;
  esac
  [ "${#REF}" -eq 40 ] || { echo "ERROR: APERTURE_REF must be a full 40-character commit SHA." >&2; exit 1; }
  BASE="https://raw.githubusercontent.com/JimBarnesly/Aperture/$REF/format-kodi"
fi
FILES="addon.xml addon.py shelf_service.py turntable_keymap.py resources/keymaps/aperture-turntable.xml resources/settings.xml resources/language/resource.language.en_gb/strings.po"
for file in $FILES; do
  mkdir -p "$(dirname "$STAGE/$file")"
  if [ -n "$SOURCE" ]; then
    cp "$SOURCE/format-kodi/$file" "$STAGE/$file"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -T 30 -O "$STAGE/$file" "$BASE/$file" || { echo "ERROR: Failed to fetch $file" >&2; exit 1; }
  elif command -v curl >/dev/null 2>&1; then
    curl -fsSL --connect-timeout 15 --max-time 60 "$BASE/$file" -o "$STAGE/$file" || { echo "ERROR: Failed to fetch $file" >&2; exit 1; }
  else
    echo "ERROR: wget or curl is required" >&2
    exit 1
  fi
  [ -s "$STAGE/$file" ] || { echo "ERROR: Empty file: $file" >&2; exit 1; }
done
grep -q 'id="plugin.audio.aperture.format"' "$STAGE/addon.xml" || { echo "ERROR: Invalid Format manifest" >&2; exit 1; }
# Python is not available on every LibreELEC shell; validate when it is present.
if command -v python3 >/dev/null 2>&1; then
  python3 - "$STAGE" <<'PY'
import ast
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
root = Path(sys.argv[1])
manifest = ET.parse(root / "addon.xml").getroot()
assert manifest.tag == "addon" and manifest.get("id") == "plugin.audio.aperture.format"
ast.parse((root / "addon.py").read_text(encoding="utf-8"))
ast.parse((root / "shelf_service.py").read_text(encoding="utf-8"))
ast.parse((root / "turntable_keymap.py").read_text(encoding="utf-8"))
assert ET.parse(root / "resources/keymaps/aperture-turntable.xml").getroot().tag == "keymap"
assert ET.parse(root / "resources/settings.xml").find("section").get("id") == manifest.get("id")
PY
fi
BACKUP=""
if [ -e "$TARGET" ] || [ -L "$TARGET" ]; then
  [ -d "$TARGET" ] && [ ! -L "$TARGET" ] || { echo "ERROR: Existing add-on is not a regular directory" >&2; exit 1; }
  mkdir -p "$KODI_HOME/aperture-backups"
  BACKUP=$(mktemp -d "$KODI_HOME/aperture-backups/format.XXXXXX")
  mv "$TARGET" "$BACKUP/plugin.audio.aperture.format"
fi
if ! mv "$STAGE" "$TARGET"; then
  [ -z "$BACKUP" ] || mv "$BACKUP/plugin.audio.aperture.format" "$TARGET"
  echo "ERROR: Install failed; the previous add-on was restored when present." >&2
  exit 1
fi
STAGE=""
echo "Format add-on installed to $TARGET"
[ -z "$BACKUP" ] || echo "Previous add-on saved in $BACKUP"
echo "Restart Kodi, then enable Format for Aperture in Add-ons > My add-ons > Music add-ons."
echo "Configure its Format server URL. Existing saved settings are preserved."
echo "Open Albums. Long-press an album (or press C) and choose Play album for the full ordered release."
echo "Format must already be running on a server reachable from the Pi."

#!/bin/sh
set -eu

# Safe Aperture baseline: retain Estuary's known-working Home.xml.
# The experimental custom home is intentionally NOT activated by default.
if [ "$(id -u)" -eq 0 ] && [ -d /storage/.kodi ]; then
  KODI_HOME=/storage/.kodi
else
  KODI_HOME="${HOME}/.kodi"
fi
SOURCE=""
for p in /usr/share/kodi/addons/skin.estuary /usr/local/share/kodi/addons/skin.estuary; do
  if [ -f "$p/addon.xml" ]; then SOURCE="$p"; break; fi
done
[ -n "$SOURCE" ] || { echo "ERROR: Installed Estuary not found" >&2; exit 1; }

ADDONS="$KODI_HOME/addons"
TARGET="$ADDONS/skin.aperture"
TMP="$ADDONS/.skin.aperture.new"
mkdir -p "$ADDONS"
rm -rf "$TMP"
trap 'rm -rf "$TMP"' EXIT HUP INT TERM

# Debian's Kodi skin resources can contain symlinks to shared font assets.
# Copy actual bytes, not links that may become invalid in the new add-on path.
cp -RL "$SOURCE" "$TMP"
sed -i 's/id="skin.estuary"/id="skin.aperture"/;s/name="Estuary"/name="Aperture"/' "$TMP/addon.xml"
grep -q 'id="skin.aperture"' "$TMP/addon.xml" || { echo "ERROR: Invalid skin manifest" >&2; exit 1; }

LAYOUT=""
for p in xml 1080i 720p; do
  if [ -f "$TMP/$p/Home.xml" ]; then LAYOUT="$p"; break; fi
done
[ -n "$LAYOUT" ] || { echo "ERROR: Estuary Home.xml missing" >&2; exit 1; }

# Validate core fonts before exposing the skin to Kodi.
if [ ! -f "$TMP/fonts/notosans-regular.ttf" ] && [ ! -f "$TMP/fonts/NotoSans-Regular.ttf" ]; then
  echo "WARNING: Noto Sans not found at the expected skin font path." >&2
  echo "Check font resources before switching to this skin." >&2
fi

# Preserve the exact Estuary Home.xml. The previous experimental XML was
# implicated in a crash on Kodi 21 and is kept in Git for development only.
if [ -d "$TARGET" ]; then
  rm -rf "$TARGET.previous"
  mv "$TARGET" "$TARGET.previous"
fi
mv "$TMP" "$TARGET"
echo "Installed safe Aperture baseline: $TARGET"
echo "No custom home layout enabled yet. This build should look like Estuary."
echo "Switch to Aperture only after confirming Kodi works with Estuary."

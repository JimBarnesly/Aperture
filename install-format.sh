#!/bin/sh
set -eu
if [ "$(id -u)" -eq 0 ] && [ -d /storage/.kodi ]; then
  KODI_HOME=/storage/.kodi
else
  KODI_HOME="${HOME}/.kodi"
fi
TARGET="$KODI_HOME/addons/plugin.audio.aperture.format"
mkdir -p "$TARGET/resources"
BASE="https://raw.githubusercontent.com/JimBarnesly/Aperture/main/format-kodi"
for file in addon.xml addon.py resources/settings.xml; do
  wget -q -O "$TARGET/$file" "$BASE/$file" || { echo "Failed to fetch $file" >&2; exit 1; }
  [ -s "$TARGET/$file" ] || { echo "Empty file: $file" >&2; exit 1; }
done
echo "Format add-on installed to $TARGET"
echo "Set your Format server URL in Kodi > Add-ons > Music add-ons > Format for Aperture > Configure"
echo "This is a read-only library client; Format must be running on a reachable server."

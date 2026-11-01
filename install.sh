#!/bin/sh
set -eu

# Aperture installer for Kodi on LibreELEC and Raspberry Pi OS.
if [ "$(id -u)" -eq 0 ] && [ -d /storage/.kodi ]; then
  KODI_HOME=/storage/.kodi
else
  KODI_HOME="${HOME}/.kodi"
fi

SOURCE=""
for p in /usr/share/kodi/addons/skin.estuary /usr/local/share/kodi/addons/skin.estuary; do
  if [ -f "$p/addon.xml" ]; then SOURCE="$p"; break; fi
done
[ -n "$SOURCE" ] || { echo "ERROR: Estuary not found. No changes made." >&2; exit 1; }

ADDONS="$KODI_HOME/addons"
TARGET="$ADDONS/skin.aperture"
TMP="$ADDONS/.skin.aperture.new"
mkdir -p "$ADDONS"
rm -rf "$TMP"
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
cp -R "$SOURCE" "$TMP"
sed -i 's/id="skin.estuary"/id="skin.aperture"/;s/name="Estuary"/name="Aperture"/' "$TMP/addon.xml"
grep -q 'id="skin.aperture"' "$TMP/addon.xml" || { echo "ERROR: Could not patch skin manifest" >&2; exit 1; }

# Estuary's active layout is selected by addon.xml's <res folder="...">.
# Install into that layout rather than assuming an xml/ directory.
LAYOUT=""
for p in xml 1080i 720p; do
  if [ -f "$TMP/$p/Home.xml" ]; then LAYOUT="$p"; break; fi
done
[ -n "$LAYOUT" ] || { echo "ERROR: Home.xml not found in Estuary" >&2; exit 1; }

wget -q -O "$TMP/$LAYOUT/Home.xml" \
  "https://raw.githubusercontent.com/JimBarnesly/Aperture/main/skin/xml/Home.xml"
[ -s "$TMP/$LAYOUT/Home.xml" ] || { echo "ERROR: Could not download Home.xml" >&2; exit 1; }

# Never overwrite the previous working version without a backup.
if [ -d "$TARGET" ]; then
  rm -rf "$TARGET.previous"
  mv "$TARGET" "$TARGET.previous"
fi
mv "$TMP" "$TARGET"

echo "Installed Aperture into $TARGET"
echo "Enable it in Kodi: Settings > Add-ons > My add-ons > Look and feel > Skin"
echo "Then select it under Settings > Interface > Skin."
echo "Fallback: switch to Estuary from Kodi, or restore $TARGET.previous."

#!/bin/sh
set -eu
SOURCE=""
for p in /usr/share/kodi/addons/skin.estuary /usr/share/kodi/addons/skin.estuary; do
  if [ -f "$p/addon.xml" ]; then SOURCE="$p"; break; fi
done
if [ -z "$SOURCE" ]; then
  echo "Cannot locate the built-in Estuary skin. No changes made." >&2
  exit 1
fi
TARGET="/storage/.kodi/addons/skin.aperture"
TMP="/storage/.kodi/addons/.skin.aperture.new"
mkdir -p /storage/.kodi/addons
rm -rf "$TMP"
cp -R "$SOURCE" "$TMP"
sed -i 's/id="skin.estuary"/id="skin.aperture"/;s/name="Estuary"/name="Aperture"/' "$TMP/addon.xml"
if ! grep -q 'id="skin.aperture"' "$TMP/addon.xml"; then
  echo "Could not patch skin manifest. Aborting." >&2
  rm -rf "$TMP"; exit 1
fi
wget -q -O "$TMP/xml/Home.xml" "https://raw.githubusercontent.com/JimBarnesly/Aperture/main/skin/xml/Home.xml"
test -s "$TMP/xml/Home.xml"
if [ -d "$TARGET" ]; then
  rm -rf "${TARGET}.previous"
  mv "$TARGET" "${TARGET}.previous"
fi
mv "$TMP" "$TARGET"
echo "Aperture installed at $TARGET"
echo "In Kodi: Settings > Interface > Skin > Aperture."
echo "To recover from a broken skin via SSH:"
echo '  sed -i "s/skin.aperture/skin.estuary/g" /storage/.kodi/userdata/guisettings.xml'
echo "  systemctl restart kodi"

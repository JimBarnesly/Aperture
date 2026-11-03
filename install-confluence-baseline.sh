#!/bin/sh
set -eu
# Install a safe Aperture baseline by cloning Kodi's official Confluence skin.
# Prerequisite: install Confluence in Kodi's official Add-on repository first.
if [ "$(id -u)" -eq 0 ] && [ -d /storage/.kodi ]; then
  HOME_KODI=/storage/.kodi
else
  HOME_KODI="${HOME}/.kodi"
fi
SOURCE=""
for path in "$HOME_KODI/addons/skin.confluence" /usr/share/kodi/addons/skin.confluence; do
  if [ -f "$path/addon.xml" ]; then SOURCE="$path"; break; fi
done
if [ -z "$SOURCE" ]; then
  echo "Install official Confluence in Kodi first: Add-ons > Install from repository > Look and feel > Skin > Confluence." >&2
  exit 1
fi
DEST="$HOME_KODI/addons/skin.aperture"
TMP="$HOME_KODI/addons/.skin.aperture.stage"
mkdir -p "$HOME_KODI/addons"
rm -rf "$TMP"
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
cp -RL "$SOURCE" "$TMP"
sed -i 's/id="skin.confluence"/id="skin.aperture"/;s/name="Confluence"/name="Aperture"/' "$TMP/addon.xml"
grep -q 'id="skin.aperture"' "$TMP/addon.xml" || exit 1
# Keep all official Confluence XML, textures and fonts untouched for baseline testing.
[ -f "$TMP/addon.xml" ] || exit 1
if [ -d "$DEST" ]; then
  rm -rf "$DEST.previous"
  mv "$DEST" "$DEST.previous"
fi
mv "$TMP" "$DEST"
echo "Installed Aperture Confluence baseline. It should look identical to Confluence."
echo "Restart Kodi from the local desktop, then enable Aperture in Add-ons."

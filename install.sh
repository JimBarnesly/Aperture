#!/bin/sh
# Install a complete Aperture skin without changing Kodi settings or databases.
# Stop Kodi yourself first. Estuary remains installed for recovery.
set -eu

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
BASELINE=0
case "${1:-}" in '') ;; --baseline) BASELINE=1 ;; *) fail 'Usage: sh install.sh [--baseline]' ;; esac
[ "$#" -le 1 ] || fail 'Too many arguments'

if [ -n "${APERTURE_KODI_HOME:-}" ]; then
  KODI_HOME=$APERTURE_KODI_HOME
elif [ "$(id -u)" -eq 0 ] && [ -d /storage/.kodi ]; then
  KODI_HOME=/storage/.kodi
elif [ "$(id -u)" -eq 0 ] || [ -n "${SUDO_USER:-}" ]; then
  fail 'On Raspberry Pi OS run as the Kodi desktop user, not root or sudo.'
else
  KODI_HOME=${HOME:?}/.kodi
fi
case "$KODI_HOME" in /*) ;; *) fail 'Kodi profile must be an absolute path' ;; esac
[ "$KODI_HOME" != / ] || fail 'Refusing to use the filesystem root as a Kodi profile'
if command -v pgrep >/dev/null 2>&1; then
  if pgrep -x kodi.bin >/dev/null 2>&1 || pgrep -x kodi >/dev/null 2>&1; then
    fail 'Kodi is running. Exit Kodi first, then rerun this installer.'
  fi
elif command -v pidof >/dev/null 2>&1; then
  if pidof kodi.bin kodi >/dev/null 2>&1; then
    fail 'Kodi is running. Exit Kodi first, then rerun this installer.'
  fi
else
  fail 'Cannot check whether Kodi is running (pgrep or pidof required).'
fi

SOURCE=${APERTURE_SKIN_SOURCE:-}
if [ -z "$SOURCE" ]; then
  for path in /usr/share/kodi/addons/skin.estuary /usr/local/share/kodi/addons/skin.estuary; do
    if [ -f "$path/addon.xml" ]; then SOURCE=$path; break; fi
  done
fi
[ -f "$SOURCE/addon.xml" ] || fail 'Installed Estuary not found'
grep -q 'id="skin.estuary"' "$SOURCE/addon.xml" || fail 'Source is not Estuary'
grep -q 'addon="xbmc.gui" version="5.17.0"' "$SOURCE/addon.xml" || fail 'This candidate requires Kodi 21 Omega'
for file in xml/Home.xml xml/Font.xml xml/Settings.xml xml/SettingsCategory.xml xml/DialogConfirm.xml; do
  [ -f "$SOURCE/$file" ] || fail "Incomplete Estuary source: $file"
done

SOURCE_DIR=${APERTURE_SOURCE_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)}
FONT_ROOT=${APERTURE_FONT_ROOT:-/usr/share/fonts}
case "$FONT_ROOT" in /*) ;; *) fail 'Font search root must be an absolute path' ;; esac

mkdir -p "$KODI_HOME"
LOCK=$KODI_HOME/.aperture-skin-install.lock
mkdir "$LOCK" 2>/dev/null || fail "Another skin installation is running: $LOCK"
STAGE=
TARGET=$KODI_HOME/addons/skin.aperture
BACKUP=
cleanup() {
  rc=$?
  trap - EXIT HUP INT TERM
  if [ "$rc" -ne 0 ] && [ -n "$BACKUP" ] && [ ! -e "$TARGET" ] && [ -d "$BACKUP/skin.aperture" ]; then
    mv "$BACKUP/skin.aperture" "$TARGET" || printf 'Restore previous skin from %s\n' "$BACKUP" >&2
  fi
  [ -z "$STAGE" ] || rm -rf "$STAGE"
  rmdir "$LOCK" 2>/dev/null || true
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' HUP INT TERM
STAGE=$(mktemp -d "$KODI_HOME/.aperture-skin.XXXXXX")
TMP=$STAGE/skin.aperture
# Preserve the Python-free path for intact distro resources (including directory
# links). On Debian/Pi OS a broken font link can point at an old package layout.
# Retry only in staging, using the ZIP builder's exact-name, unique-match lookup.
# Never repair system links, download fonts or replace an arbitrary font face.
if ! cp -RL "$SOURCE" "$TMP" 2>"$STAGE/copy.log"; then
  rm -rf "$TMP"
  if command -v python3 >/dev/null 2>&1 && [ -f "$SOURCE_DIR/tools/build_skin.py" ]; then
    printf 'Resolving distribution resources from installed system fonts...\n'
    python3 "$SOURCE_DIR/tools/build_skin.py" --copy-only --source "$SOURCE" --output "$TMP" --font-root "$FONT_ROOT" ||
      fail 'Could not resolve distribution assets. No skin was replaced; use the verified complete ZIP.'
  else
    cat "$STAGE/copy.log" >&2
    fail 'A distribution asset is missing. No skin was replaced; use Python 3 with the complete checkout to resolve fonts, or install the verified complete ZIP.'
  fi
fi
sed -i '/<addon /s/id="skin.estuary"/id="skin.aperture"/; /<addon /s/name="Estuary"/name="Aperture"/; /<addon /s/version="[^"]*"/version="4.0.1~rc1"/' "$TMP/addon.xml"

if [ "$BASELINE" -eq 0 ]; then
  # Use one complete, matching source checkout, never moving remote fragments.
  [ -f "$SOURCE_DIR/skin/xml/Home.xml" ] || fail 'Use the complete source checkout or install the complete ZIP through Kodi.'
  HOME_SHA=1cd13e743b826697a83ef666ba7eeb8d793ec1bc0f5910e79d2b15d03159e904
  cp "$SOURCE_DIR/skin/xml/Home.xml" "$STAGE/Home.xml"
  printf '%s  %s\n' "$HOME_SHA" "$STAGE/Home.xml" | sha256sum -c - >/dev/null || fail 'Home.xml integrity check failed'
  [ -d "$SOURCE_DIR/skin/media/aperture" ] || fail 'Matching Aperture artwork missing'
  [ -f "$SOURCE_DIR/skin/licenses/MediaStream-CC-BY-SA-3.0.txt" ] || fail 'Artwork attribution missing'
  cp "$STAGE/Home.xml" "$TMP/xml/Home.xml"
  cp "$SOURCE_DIR/skin/xml/DialogButtonMenu.xml" "$TMP/xml/DialogButtonMenu.xml"
  if command -v python3 >/dev/null 2>&1; then
    python3 "$SOURCE_DIR/tools/style_dialogs.py" "$TMP"
  else
    printf "Python 3 unavailable: shared dialog palette remains upstream.\n"
  fi
  [ -f "$SOURCE_DIR/skin/xml/MyGames.xml" ] || fail 'Matching game browser XML missing'
  GAMES_SHA=0338a9eac75c4b3200ec050df0cd66d21f7bec9557293066aa7a5c9419dfeb5b
  printf '%s  %s\n' "$GAMES_SHA" "$SOURCE_DIR/skin/xml/MyGames.xml" | sha256sum -c - >/dev/null || fail 'MyGames.xml integrity check failed'
  cp "$SOURCE_DIR/skin/xml/MyGames.xml" "$TMP/xml/MyGames.xml"
  [ -f "$SOURCE_DIR/skin/xml/MyVideoNav.xml" ] || fail 'Matching movie browser XML missing'
  MOVIES_SHA=65c9f400e002bdfe6f2abb2e954276b9a36bea6e1743a17379e462a82a9e5b5f
  printf '%s  %s\n' "$MOVIES_SHA" "$SOURCE_DIR/skin/xml/MyVideoNav.xml" | sha256sum -c - >/dev/null || fail 'MyVideoNav.xml integrity check failed'
  cp "$SOURCE_DIR/skin/xml/MyVideoNav.xml" "$TMP/xml/MyVideoNav.xml"
  [ -f "$SOURCE_DIR/skin/xml/MyMusicNav.xml" ] || fail 'Matching music browser XML missing'
  MUSIC_SHA=8d34351d6e5453ed3c00c661d36d2928fc464c3c05ed9537a31a148001c22b98
  printf '%s  %s\n' "$MUSIC_SHA" "$SOURCE_DIR/skin/xml/MyMusicNav.xml" | sha256sum -c - >/dev/null || fail 'MyMusicNav.xml integrity check failed'
  cp "$SOURCE_DIR/skin/xml/MyMusicNav.xml" "$TMP/xml/MyMusicNav.xml"
  [ -f "$SOURCE_DIR/skin/xml/MusicVisualisation.xml" ] || fail 'Matching now-playing XML missing'
  VISUALISATION_SHA=ca760a9025dd4b43ec01de37d305128c076ea91d66c28c7fc605522f34e68bc5
  printf '%s  %s\n' "$VISUALISATION_SHA" "$SOURCE_DIR/skin/xml/MusicVisualisation.xml" | sha256sum -c - >/dev/null || fail 'MusicVisualisation.xml integrity check failed'
  cp "$SOURCE_DIR/skin/xml/MusicVisualisation.xml" "$TMP/xml/MusicVisualisation.xml"
  [ -f "$SOURCE_DIR/skin/xml/DialogSeekBar.xml" ] || fail 'Matching playback overlay XML missing'
  SEEKBAR_SHA=ef7d10d10b63dd283331555c4032fbd321e4cb37388681d6019a79619161bd87
  printf '%s  %s\n' "$SEEKBAR_SHA" "$SOURCE_DIR/skin/xml/DialogSeekBar.xml" | sha256sum -c - >/dev/null || fail 'DialogSeekBar.xml integrity check failed'
  cp "$SOURCE_DIR/skin/xml/DialogSeekBar.xml" "$TMP/xml/DialogSeekBar.xml"
  cp -R "$SOURCE_DIR/skin/media/." "$TMP/media/"
  mkdir -p "$TMP/licenses"
  cp -R "$SOURCE_DIR/skin/licenses/." "$TMP/licenses/"
fi
# Missing declared fonts are fatal, except Kodi's own global Arial fallback.
for font in $(sed -n 's/.*<filename>\([^<]*\)<\/filename>.*/\1/p' "$TMP/xml/Font.xml" | sort -u); do
  case "$font" in arial.ttf) ;; *) [ -s "$TMP/fonts/$font" ] || fail "Missing font: $font" ;; esac
done
grep -q 'id="skin.aperture"' "$TMP/addon.xml" || fail 'Manifest identity validation failed'
[ -s "$TMP/xml/Home.xml" ] || fail 'Home.xml missing'
[ ! -L "$TARGET" ] || fail 'Refusing to replace a symlinked skin directory'
[ ! -e "$TARGET" ] || [ -d "$TARGET" ] || fail 'Skin target is not a directory'

mkdir -p "$KODI_HOME/addons" "$KODI_HOME/aperture-backups"
if [ -d "$TARGET" ]; then
  BACKUP=$(mktemp -d "$KODI_HOME/aperture-backups/skin.XXXXXX")
  mv "$TARGET" "$BACKUP/skin.aperture"
fi
# Preserve legacy duplicate-ID backups outside Kodi's add-on scan directory.
for old in "$TARGET.previous" "$KODI_HOME/addons/.skin.aperture.new" "$KODI_HOME/addons/.skin.aperture.stage"; do
  if [ -d "$old" ] && [ ! -L "$old" ] && [ -f "$old/addon.xml" ] && grep -q 'id="skin.aperture"' "$old/addon.xml"; then
    legacy=$(mktemp -d "$KODI_HOME/aperture-backups/legacy.XXXXXX")
    mv "$old" "$legacy/skin.aperture"
  fi
done
mv "$TMP" "$TARGET"
printf 'Installed Aperture 4.0.1~rc1: %s\n' "$TARGET"
[ -z "$BACKUP" ] || printf 'Previous skin preserved: %s/skin.aperture\n' "$BACKUP"
[ "$BASELINE" -eq 0 ] || printf 'Diagnostic baseline selected: Home is unchanged Estuary.\n'
printf 'Start Kodi, enable Aperture in My add-ons, then choose it in Settings > Interface > Skin.\n'
printf 'Confirm Keep only if the screen and controls work. Estuary is unchanged.\n'

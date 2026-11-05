#!/usr/bin/env bash
# CI-only official signed package setup. Run only inside a disposable ARM64 container.
set -Eeuo pipefail
[[ "$EUID" == 0 && "$(dpkg --print-architecture)" == arm64 ]] || { echo 'Requires disposable ARM64 container root'; exit 2; }
[[ ! -e /dev/dri && ! -e /dev/input ]] || { echo 'Unexpected hardware device tree'; exit 2; }
SETUP="${APERTURE_RPT3_SETUP:-/tmp/labwc-rpt3-setup}"
mkdir -p "$SETUP"
printf '{"status":"harness_failure","stage":"signed_package_setup","reason":"Package setup did not finish"}\n' > "$SETUP/result.json"
exec > >(tee "$SETUP/install.log") 2>&1
KODI_VERSION='3:21.3+dfsg-1+rpt3'
FFMPEG_VERSION='8:7.1.5-0+deb13u1+rpt2'
MESA_VERSION='25.0.7-2+deb13u1'
LABWC_VERSION='0.8.3-1'
KEY_FINGERPRINT='CF8A1AF502A2AA2D763BAE7E82B129927FA3303E'
# Baseline graphics/compositor comes from signed Debian trixie, before adding Pi sources.
apt-get -o APT::Update::Error-Mode=any update
apt-get install --yes --no-install-recommends ca-certificates curl gnupg git python3 python3-pil \
  "labwc=$LABWC_VERSION" dbus-daemon libegl1 "libegl-mesa0=$MESA_VERSION" \
  "libgl1-mesa-dri=$MESA_VERSION" "libgbm1=$MESA_VERSION" libgl1 libgles2 \
  wtype grim wlr-randr wayland-utils procps tesseract-ocr tesseract-ocr-eng \
  fonts-noto-core fonts-noto-mono fonts-roboto-unhinted
curl --fail --show-error --silent --location --proto '=https' --proto-redir '=https' \
  https://archive.raspberrypi.com/debian/raspberrypi.gpg.key -o "$SETUP/raspberrypi.gpg.key"
gpg --batch --show-keys --with-colons "$SETUP/raspberrypi.gpg.key" > "$SETUP/signing-key.txt"
ACTUAL="$(awk -F: '$1 == "fpr" { print $10; exit }' "$SETUP/signing-key.txt")"
[[ "$ACTUAL" == "$KEY_FINGERPRINT" ]] || { echo 'Official repository key fingerprint changed; stopping'; exit 2; }
gpg --batch --dearmor --output /usr/share/keyrings/aperture-ci-raspberrypi.gpg "$SETUP/raspberrypi.gpg.key"
printf '%s\n' 'deb [arch=arm64 signed-by=/usr/share/keyrings/aperture-ci-raspberrypi.gpg] https://archive.raspberrypi.com/debian/ trixie main' > /etc/apt/sources.list.d/aperture-ci-raspberrypi.list
# Prefer Debian for unrelated packages. Explicit exact versions below select only
# the requested Kodi and its required matching downstream FFmpeg userspace libraries.
printf 'Package: *\nPin: origin archive.raspberrypi.com\nPin-Priority: 100\n' > /etc/apt/preferences.d/aperture-ci-raspberrypi
apt-get -o APT::Update::Error-Mode=any update
cp /var/lib/apt/lists/archive.raspberrypi.com_debian_dists_trixie_InRelease "$SETUP/raspberrypi-InRelease"
apt-cache policy kodi kodi-bin kodi-data labwc libegl-mesa0 libavcodec61 > "$SETUP/package-policy.txt"
PACKAGES=("kodi=$KODI_VERSION" "kodi-bin=$KODI_VERSION" "kodi-data=$KODI_VERSION")
for package in libavcodec61 libavfilter10 libavformat61 libavutil59 libpostproc58 libswresample5 libswscale8; do
  PACKAGES+=("$package=$FFMPEG_VERSION")
done
apt-get --simulate --no-install-recommends install "${PACKAGES[@]}" > "$SETUP/install-plan.txt"
cat "$SETUP/install-plan.txt"
apt-get install --yes --no-install-recommends "${PACKAGES[@]}"
dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' > "$SETUP/all-packages.tsv"
python3 - "$SETUP" <<'PY'
import json, pathlib, sys
path=pathlib.Path(sys.argv[1]);rows={fields[0]:fields[1:] for line in (path/'all-packages.tsv').read_text().splitlines() if len(fields:=line.split('\t'))==3}
expected={'kodi':'3:21.3+dfsg-1+rpt3','kodi-bin':'3:21.3+dfsg-1+rpt3','kodi-data':'3:21.3+dfsg-1+rpt3', 'labwc':'0.8.3-1','libegl-mesa0':'25.0.7-2+deb13u1','libgl1-mesa-dri':'25.0.7-2+deb13u1'}
for key,version in expected.items():
 assert rows.get(key,[None])[0]==version, (key,rows.get(key))
assert rows['kodi-bin'][1]=='arm64'
(path/'result.json').write_text(json.dumps({'status':'passed','stage':'signed_package_setup','packages':{k:rows[k] for k in expected},'signature_verification':'APT signed-by; no insecure overrides'},indent=2)+'\n')
PY

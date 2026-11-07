#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8 TZ=UTC
ROOT=/work
OUT=$ROOT/kodi-build-output
WORK=/build
TOOLS=$ROOT/tools/kodi-audio-fix
mkdir -p "$OUT" "$WORK"
exec > >(tee "$OUT/build.log") 2>&1
finish() {
  rc=$?
  trap - EXIT
  echo "BUILD_EXIT_STATUS=$rc"
  find /build -path '*/Testing/Temporary/*' -type f -exec cp --parents {} "$OUT" \; 2>/dev/null || true
  (cd "$OUT"; find . -type f ! -name SHA256SUMS ! -name build.log -print0 | sort -z | xargs -0 -r sha256sum > SHA256SUMS) || true
  exit "$rc"
}
trap finish EXIT
printf '%s\n' "$SOURCE_COMMIT" > "$OUT/workflow-commit.txt"
test "$(dpkg --print-architecture)" = arm64
# Immutable Debian snapshot. RPi has no snapshot service; retain package bytes,
# versions and signed indexes so this build's exact dependency set can be reused.
rm -f /etc/apt/sources.list.d/* /etc/apt/sources.list
cat > /etc/apt/sources.list <<'APT'
deb [check-valid-until=no signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] http://snapshot.debian.org/archive/debian/20261107T000000Z trixie main
deb [check-valid-until=no signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] http://snapshot.debian.org/archive/debian-security/20261107T000000Z trixie-security main
APT
rm -f /etc/apt/apt.conf.d/docker-clean
printf 'APT::Keep-Downloaded-Packages "true";\nBinary::apt::APT::Keep-Downloaded-Packages "true";\n' > /etc/apt/apt.conf.d/keep-packages
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl gnupg build-essential devscripts equivs python3 xz-utils
curl --fail --location --retry 3 https://archive.raspberrypi.com/debian/raspberrypi.gpg.key -o /tmp/rpi.asc
fingerprint=$(gpg --show-keys --with-colons /tmp/rpi.asc | awk -F: '$1=="fpr" {print $10; exit}')
test "$fingerprint" = CF8A1AF502A2AA2D763BAE7E82B129927FA3303E
gpg --dearmor --output /usr/share/keyrings/raspberrypi-archive.gpg /tmp/rpi.asc
cat >> /etc/apt/sources.list <<'APT'
deb [signed-by=/usr/share/keyrings/raspberrypi-archive.gpg] https://archive.raspberrypi.com/debian/ trixie main
APT
apt-get update
python3 "$TOOLS/verify_source_provenance.py" /usr/share/keyrings/raspberrypi-archive.gpg
cp -a "$TOOLS/provenance" "$OUT/source-provenance"
cp /etc/apt/sources.list "$OUT/apt-sources.list"
cp /tmp/rpi.asc "$OUT/raspberrypi-archive-key.asc"
cd "$WORK"
while read -r hash filename; do
  curl --fail --location --retry 3 "https://archive.raspberrypi.com/debian/pool/main/k/kodi/$filename" -o "$filename"
done < "$TOOLS/source.sha256"
sha256sum --check "$TOOLS/source.sha256"
cp "$TOOLS/source.sha256" "$OUT/original-source.sha256"
dpkg-source -x kodi_21.3+dfsg-1+rpt3.dsc source
cd source
mkdir -p debian/patches/local
cp "$TOOLS/0001-close-failed-game-stream.patch" debian/patches/local/
printf '\nlocal/0001-close-failed-game-stream.patch\n' >> debian/patches/series
python3 - <<'PY'
from pathlib import Path
p=Path('debian/changelog')
p.write_text('kodi (3:21.3+dfsg-1+rpt3+ff9fix1) trixie; urgency=medium\n\n  * Local diagnostic build: backport only failed-open stream cleanup.\n\n -- Local build <local@localhost>  Sat, 07 Nov 2026 14:00:00 +0000\n\n'+p.read_text())
PY
dpkg-source --before-build .
mkdir -p "$WORK/build-deps"
(cd "$WORK/build-deps"; mk-build-deps --install --remove --tool 'apt-get -y --no-install-recommends' "$WORK/source/debian/control")
dpkg-checkbuilddeps
export DEB_BUILD_OPTIONS=parallel=2
# Derive rather than duplicate the changelog timestamp.
export SOURCE_DATE_EPOCH=$(date -u -d "$(dpkg-parsechangelog -S Date)" +%s)
test "$SOURCE_DATE_EPOCH" = 1794060000
unset DEB_BUILD_PROFILES || true
dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\n' | sort > "$OUT/build-dependencies.tsv"
apt-cache policy > "$OUT/apt-policy.txt"
tar -C /var/lib/apt/lists --exclude=lock --exclude=partial --exclude=auxfiles -cf "$OUT/apt-lists.tar" .
mkdir -p "$OUT/dependency-debs"
cp /var/cache/apt/archives/*.deb "$OUT/dependency-debs/"
(cd "$OUT/dependency-debs"; sha256sum *.deb > SHA256SUMS)
gcc --version > "$OUT/compiler.txt"
ld --version >> "$OUT/compiler.txt"
dpkg-buildflags --export=sh > "$OUT/build-flags.txt"
KODI_SOURCE="$WORK/source" TEST_OUTPUT="$OUT/focused-regression" python3 "$TOOLS/test_cleanup.py"
dpkg-source -b .
cp "$WORK"/*.dsc "$WORK"/*.tar.xz "$OUT/"
# Preserve distribution rules and tests. No nocheck/nostrip/noautodbgsym/-d.
dpkg-buildpackage -b -us -uc -j2
cp "$WORK"/*.deb "$WORK"/*.changes "$WORK"/*.buildinfo "$OUT/"
bash "$TOOLS/validate.sh" "$OUT"

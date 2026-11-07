#!/bin/bash
set -euo pipefail
OUT=$(realpath "$1")
BIN=$OUT/kodi-bin_21.3+dfsg-1+rpt3+ff9fix1_arm64.deb
DBG=$OUT/kodi-bin-dbgsym_21.3+dfsg-1+rpt3+ff9fix1_arm64.deb
test -f "$BIN" && test -f "$DBG"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
dpkg-deb -x "$BIN" "$STAGE/bin"
dpkg-deb -x "$DBG" "$STAGE/dbg"
ELF=$STAGE/bin/usr/lib/aarch64-linux-gnu/kodi/kodi.bin
readelf -h "$ELF" > "$OUT/elf-header.txt"
grep -q AArch64 "$OUT/elf-header.txt"
BUILD_ID=$(readelf -n "$ELF" | awk '/Build ID:/ {print $3; exit}')
test -n "$BUILD_ID"
test "$BUILD_ID" != fb8d48fe36a5270e5ac3ccdff4e961a18bd3c638
DEBUG=$STAGE/dbg/usr/lib/debug/.build-id/${BUILD_ID:0:2}/${BUILD_ID:2}.debug
test -f "$DEBUG"
readelf -n "$DEBUG" > "$OUT/debug-notes.txt"
grep -q "$BUILD_ID" "$OUT/debug-notes.txt"
readelf --wide --section-headers "$DEBUG" > "$OUT/debug-sections.txt"
grep -qE "[[:space:]]\.debug_info[[:space:]]" "$OUT/debug-sections.txt"
grep -qE "[[:space:]]\.debug_line[[:space:]]" "$OUT/debug-sections.txt"
printf '%s\n' "$BUILD_ID" > "$OUT/patched-build-id.txt"
dpkg-deb -f "$BIN" > "$OUT/patched-binary-control.txt"
dpkg-deb -f "$DBG" > "$OUT/patched-dbgsym-control.txt"
printf 'ARM64 binary and same-build debug symbols verified. Pi validation is still required.\n' > "$OUT/BUILD-STATUS.txt"

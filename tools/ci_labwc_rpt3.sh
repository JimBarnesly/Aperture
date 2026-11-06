#!/usr/bin/env bash
# Wrap the unchanged passing lifecycle diagnostic with exact rpt3/GLES checks.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export APERTURE_WAYLAND_OUT="${APERTURE_WAYLAND_OUT:-/tmp/labwc-rpt3-output}"
SETUP="${APERTURE_RPT3_SETUP:-/tmp/labwc-rpt3-setup}"
[[ "$(dpkg --print-architecture)" == arm64 ]] || { echo 'ARM64 required'; exit 2; }
python3 - "$ROOT" "$SETUP" <<'PY'
import pathlib,sys
sys.path.insert(0,str(pathlib.Path(sys.argv[1])/'tools'))
from labwc_rpt3_verify import package_evidence
package_evidence((pathlib.Path(sys.argv[2])/'all-packages.tsv').read_text())
PY
set +e
bash "$ROOT/tools/ci_labwc_relaunch.sh"
RC=$?
set -e
# Preserve a lifecycle failure; additionally prohibit a silent GL/package substitution.
python3 "$ROOT/tools/labwc_rpt3_verify.py" "$APERTURE_WAYLAND_OUT" "$SETUP"
exit "$RC"

#!/usr/bin/env bash
# Same output-size-churn driver and acceptance, separately verified exact Pi userspace.
set -Eeuo pipefail
[[ "${APERTURE_PI_USERSPACE_COMPARISON:-}" == exact-2026-11-05 ]] || exit 2
[[ "${APERTURE_WAYLAND_EXPERIMENT:-}" == output-size-churn ]] || exit 2
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export APERTURE_WAYLAND_OUT="${APERTURE_WAYLAND_OUT:-/tmp/labwc-pi-userspace-output}"
SETUP="${APERTURE_RPT3_SETUP:-/tmp/labwc-rpt3-setup}"
python3 - "$ROOT" "$SETUP" <<'PY'
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(sys.argv[1]) / 'tools'))
from labwc_pi_userspace_verify import package_evidence
package_evidence((pathlib.Path(sys.argv[2]) / 'all-packages.tsv').read_text())
PY
set +e
bash "$ROOT/tools/ci_labwc_relaunch.sh"
RC=$?
set -e
python3 "$ROOT/tools/labwc_pi_userspace_verify.py" "$APERTURE_WAYLAND_OUT" "$SETUP"
exit "$RC"

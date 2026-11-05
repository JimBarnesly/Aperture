#!/usr/bin/env bash
# Explicit opt-in: upgrade only isolated userspace after the unchanged signed baseline setup.
set -Eeuo pipefail
[[ "${APERTURE_PI_USERSPACE_COMPARISON:-}" == exact-2026-11-05 ]] || { echo 'Exact Pi userspace comparison not selected'; exit 2; }
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SETUP="${APERTURE_RPT3_SETUP:-/tmp/labwc-rpt3-setup}"
bash "$ROOT/tools/install_labwc_rpt3_ci.sh"
exec > >(tee "$SETUP/pi-userspace-install.log") 2>&1
printf '{"status":"harness_failure","stage":"pi_userspace_setup","reason":"Userspace comparison setup did not finish"}\n' > "$SETUP/result.json"
trap 'rc=$?; printf "{\"status\":\"harness_failure\",\"stage\":\"pi_userspace_setup\",\"reason\":\"See pi-userspace-install.log\",\"exit_code\":%s,\"line\":%s}\n" "$rc" "$LINENO" > "$SETUP/result.json"' ERR
[[ "$EUID" == 0 && "$(dpkg --print-architecture)" == arm64 ]] || exit 2
[[ ! -e /dev/dri && ! -e /dev/input ]] || { echo 'Unexpected hardware device tree'; exit 2; }
cp "$SETUP/all-packages.tsv" "$SETUP/baseline-packages.tsv"
# No broad distribution upgrade. Every requested Pi package is exact; normal
# signed APT handles dependencies, then the simulation is checked before install.
mapfile -t PACKAGES < <(python3 - "$ROOT" <<'PY'
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(sys.argv[1]) / 'tools'))
from labwc_pi_userspace_verify import EXPECTED
for package, version in EXPECTED.items():
    if not package.startswith('kodi'):
        print(package + '=' + version)
PY
)
(( ${#PACKAGES[@]} >= 10 )) || { echo 'Missing exact package pins'; exit 2; }
apt-cache policy "${PACKAGES[@]%%=*}" > "$SETUP/pi-userspace-policy.txt"
apt-get --simulate --no-install-recommends install "${PACKAGES[@]}" > "$SETUP/pi-userspace-install-plan.txt"
cat "$SETUP/pi-userspace-install-plan.txt"
python3 - "$ROOT" "$SETUP" <<'PY'
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(sys.argv[1]) / 'tools'))
from labwc_pi_userspace_verify import validate_plan
setup = pathlib.Path(sys.argv[2])
changed = validate_plan((setup / 'pi-userspace-install-plan.txt').read_text())
(setup / 'pi-userspace-plan-check.json').write_text(json.dumps(dict(status='passed', changed=changed), indent=2) + '\n')
PY
# --no-remove adds a second guard if the solver outcome changes after simulation.
apt-get --yes --no-remove --no-install-recommends install "${PACKAGES[@]}"
dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' > "$SETUP/all-packages.tsv"
ldd "$(command -v labwc)" > "$SETUP/pi-userspace-labwc-bindings.txt"
grep -q 'libwlroots-0.20.so' "$SETUP/pi-userspace-labwc-bindings.txt"
python3 - "$ROOT" "$SETUP" <<'PY'
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(sys.argv[1]) / 'tools'))
from labwc_pi_userspace_verify import package_evidence
setup = pathlib.Path(sys.argv[2])
packages = package_evidence((setup / 'all-packages.tsv').read_text())
(setup / 'result.json').write_text(json.dumps(dict(status='passed', stage='pi_userspace_setup', packages=packages,
    signature_verification='APT signed-by; no insecure overrides', no_device_service_changes=True), indent=2) + '\n')
PY

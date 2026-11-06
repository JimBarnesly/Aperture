"""Exact official Pi userspace comparison; reject device/service dependency changes."""
import json
from pathlib import Path
import re
import sys
from labwc_rpt3_verify import gles_evidence, KODI_VERSION

MESA_VERSION = '26.2.2-1~bpo13+0~rpt1'
EXPECTED = {
    'kodi': KODI_VERSION, 'kodi-bin': KODI_VERSION, 'kodi-data': KODI_VERSION,
    'labwc': '0.20.2-1~bpo13+1', 'libwlroots-0.20': '0.20.2-1+rpt4',
    **{p: MESA_VERSION for p in ('libegl-mesa0', 'libgl1-mesa-dri', 'libgbm1', 'libglx-mesa0', 'mesa-libgallium')},
    **{p: '1.24.0-2~bpo13+1~rpt1' for p in ('libwayland-client0', 'libwayland-server0', 'libwayland-cursor0', 'libwayland-egl1')},
    **{p: '2.4.134-3~bpo13+1+rpt1' for p in ('libdrm2', 'libdrm-common', 'libdrm-amdgpu1')},
    **{p: '1.28.1-1+rpt1+deb13u1' for p in ('libinput10', 'libinput-bin')},
    **{p: '1.13.1-1~bpo13+1+rpt1' for p in ('libxkbcommon0', 'libxkbcommon-x11-0')},
    **{p: '8:7.1.5-0+deb13u1+rpt2' for p in ('libavcodec61', 'libavfilter10', 'libavformat61',
                                           'libavutil59', 'libpostproc58', 'libswresample5', 'libswscale8')},
}


def validate_plan(text):
    """Only the opted-in compositor and userspace libraries may change.

    This validates the upgrade from the unchanged baseline installation, not
    an empty system. No kernel/firmware, device daemon, service or removal is
    permitted. The exact version pins are verified again after installation.
    """
    changed = []
    for line in text.splitlines():
        if line.startswith(('Remv ', 'Purg ')):
            raise ValueError('Package removal is outside isolated comparison scope: ' + line)
        if not line.startswith('Inst '):
            continue
        package = line.split()[1].split(':')[0]
        if not (package.startswith('lib') or package in ('labwc', 'mesa-libgallium', 'xkb-data')):
            raise ValueError('Non-userspace-library package change is outside scope: ' + line)
        changed.append(package)
    if not changed or 'labwc' not in changed:
        raise ValueError('Simulation did not contain the expected compositor change')
    return changed


def package_evidence(text):
    rows = {f[0]: f[1:] for line in text.splitlines() if len(f := line.split('\t')) == 3}
    for name, version in EXPECTED.items():
        if rows.get(name, [None])[0] != version:
            raise ValueError('Unexpected exact userspace package: ' + name + ' ' + str(rows.get(name)))
        if rows[name][1] not in ('arm64', 'all'):
            raise ValueError('Unexpected userspace architecture: ' + name)
    if rows['kodi-bin'][1] != 'arm64':
        raise ValueError('Kodi binary is not ARM64')
    return {name: rows[name] for name in EXPECTED}


def main(out, setup):
    out, setup = Path(out), Path(setup)
    path = out / 'result.json'
    result = json.loads(path.read_text())
    original = result['status']
    try:
        packages = package_evidence((setup / 'all-packages.tsv').read_text())
        changed = validate_plan((setup / 'pi-userspace-install-plan.txt').read_text())
        bindings = (setup / 'pi-userspace-labwc-bindings.txt').read_text()
        if 'libwlroots-0.20.so' not in bindings:
            raise ValueError('Labwc is not linked to the requested wlroots 0.20 runtime')
        observed = {}
        for folder in sorted(out.glob('launch-*')):
            if (folder / 'kodi.log').exists():
                evidence = gles_evidence((folder / 'kodi.log').read_text(errors='replace'))
                if 'Mesa 26.2.2' not in evidence['version']:
                    raise ValueError('Runtime Mesa is not the requested userspace version')
                observed[folder.name] = evidence
        if original == 'passed' and set(observed) != {'launch-1', 'launch-2', 'launch-3', 'launch-4'}:
            raise ValueError('Missing verified GLES launch')
        result['pi_userspace_runtime'] = dict(packages=packages, launches=observed,
            changed_packages=changed, signature_verification='APT signed-by with pinned official Raspberry Pi fingerprint',
            no_device_service_changes=True)
        result['scope'] = 'Exact Pi rpt3 ARM64 Kodi and Pi Labwc 0.20.2/wlroots 0.20.2/Mesa 26.2.2 userspace, native Wayland llvmpipe GLES'
    except Exception as error:
        result.update(status='harness_runtime_verification_failure', base_diagnostic_status=original, reason=str(error))
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main(*sys.argv[1:]))

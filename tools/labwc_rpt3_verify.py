"""Require exact downstream ARM64 packages and actual GLES on every launch."""
import json
from pathlib import Path
import re
import sys

KODI_VERSION = '3:21.3+dfsg-1+rpt3'


def package_evidence(text):
    rows = {fields[0]: fields[1:] for line in text.splitlines() if len(fields := line.split('\t')) == 3}
    expected = {'kodi': KODI_VERSION, 'kodi-bin': KODI_VERSION, 'kodi-data': KODI_VERSION,
                'labwc': '0.8.3-1', 'libegl-mesa0': '25.0.7-2+deb13u1', 'libgl1-mesa-dri': '25.0.7-2+deb13u1'}
    for package, version in expected.items():
        if rows.get(package, [None])[0] != version:
            raise ValueError('Unexpected package: ' + package + ' ' + str(rows.get(package)))
    if rows['kodi-bin'][1] != 'arm64':
        raise ValueError('Kodi binary is not ARM64')
    return {key: rows[key] for key in expected}


def gles_evidence(log):
    renderer = re.findall(r'\bGL_RENDERER\s*=\s*(.+)', log)
    version = re.findall(r'\bGL_VERSION\s*=\s*(.+)', log)
    if len(renderer) != 1 or 'llvmpipe' not in renderer[0].lower():
        raise ValueError('Exactly one llvmpipe renderer must be established')
    if len(version) != 1 or not version[0].startswith('OpenGL ES '):
        raise ValueError('Actual runtime is not GLES: ' + str(version))
    if 'Binding Wayland protocol' not in log:
        raise ValueError('Native Wayland runtime was not established')
    return {'renderer': renderer[0].strip(), 'version': version[0].strip(), 'native_wayland': True}


def main(out, setup):
    out, setup = Path(out), Path(setup)
    path = out / 'result.json'
    result = json.loads(path.read_text())
    original = result['status']
    try:
        packages = package_evidence((setup / 'all-packages.tsv').read_text())
        observed = {}
        for folder in sorted(out.glob('launch-*')):
            log = folder / 'kodi.log'
            if log.exists():
                observed[folder.name] = gles_evidence(log.read_text(errors='replace'))
        if original == 'passed' and set(observed) != {'launch-1', 'launch-2', 'launch-3', 'launch-4'}:
            raise ValueError('Missing verified GLES launch')
        result['downstream_runtime'] = {'packages': packages, 'launches': observed,
            'signature_verification': 'APT signed-by with pinned official Raspberry Pi fingerprint'}
        result['scope'] = 'Exact Raspberry Pi rpt3 ARM64 Kodi package, native Wayland llvmpipe GLES, Debian trixie headless Labwc'
    except Exception as error:
        result.update(status='harness_runtime_verification_failure', base_diagnostic_status=original, reason=str(error))
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main(*sys.argv[1:]))

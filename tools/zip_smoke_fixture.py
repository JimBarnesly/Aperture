"""Prepare a fresh disposable profile; subjects enter only through Kodi's ZIP UI."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import xml.etree.ElementTree as ET
import zipfile

SUBJECTS = ('plugin.games.apeture', 'script.apeture.music', 'skin.apeture')
OBSERVER = 'service.apeture.zipsmoke'


def packages(dist):
    dist = Path(dist)
    rows = json.loads((dist / 'checksums.json').read_text(encoding='utf-8'))
    if len(rows) != 3 or {row['addon'] for row in rows} != set(SUBJECTS):
        raise ValueError('Only the three exact built Apeture ZIPs are allowed')
    result = []
    for addon in SUBJECTS:
        row = next(row for row in rows if row['addon'] == addon)
        filename = row['file']
        if PurePosixPath(filename).name != filename or not filename.endswith('.zip'):
            raise ValueError('Unsafe package filename')
        path = dist / filename
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Built ZIP checksum mismatch')
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                name = PurePosixPath(member.filename)
                if name.is_absolute() or '..' in name.parts or not name.parts or name.parts[0] != addon:
                    raise ValueError('Unsafe/nonmatching ZIP member')
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('ZIP symlinks are not accepted')
            metadata = ET.fromstring(archive.read(addon + '/addon.xml'))
            if metadata.get('id') != addon or metadata.get('version') != row['version']:
                raise ValueError('ZIP metadata differs from checksum manifest')
        result.append(row)
    return result


def verify_installed(package_dir, data, rows):
    """Compare every packaged byte with files Kodi installed in its user tree."""
    checked = []
    for row in rows:
        count = 0
        with zipfile.ZipFile(Path(package_dir) / row['file']) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                target = Path(data) / 'addons' / member.filename
                if target.is_symlink() or not target.is_file() or target.read_bytes() != archive.read(member):
                    raise AssertionError('Kodi-installed bytes differ: ' + member.filename)
                count += 1
        checked.append({'addon': row['addon'], 'version': row['version'], 'sha256': row['sha256'], 'files_verified': count})
    return checked


def prepare(root, runtime, base_system, out):
    root, runtime, base_system, out = map(lambda p: Path(p).resolve(), (root, runtime, base_system, out))
    if not runtime.name.startswith('apeture-kodi-smoke.') or base_system != runtime / 'system':
        raise ValueError('Not the existing disposable CI runtime')
    target = runtime / 'fresh-zip'
    if target.exists():
        raise ValueError('Refusing to replace an existing ZIP-test profile')
    rows = packages(root / 'dist')
    target.mkdir(mode=0o700)
    system, data, home = target / 'system', target / 'data', target / 'home'
    # Reuse only already materialized distro data/fonts, never subject add-ons.
    def exclude(directory, names):
        return [name for name in names if name in SUBJECTS or name.startswith('service.apeture.')]
    shutil.copytree(base_system, system, ignore=exclude)
    manifest = ET.parse(system / 'system/addon-manifest.xml')
    for item in list(manifest.getroot()):
        if item.text in SUBJECTS or (item.text or '').startswith('service.apeture.'):
            manifest.getroot().remove(item)
    userdata = data / 'userdata'
    (userdata / 'keymaps').mkdir(parents=True)
    home.mkdir()
    (home / '.config').mkdir()
    (home / '.cache').mkdir()
    (home / '.local/share').mkdir(parents=True)
    (target / 'packages').mkdir()
    out.mkdir(parents=True, exist_ok=True)
    for row in rows:
        shutil.copy2(root / 'dist' / row['file'], target / 'packages' / row['file'])
    settings = ET.Element('settings', version='2')
    values = {'lookandfeel.skin': 'skin.estuary', 'general.addonupdates': '2',
              'addons.unknownsources': 'false', 'lookandfeel.enablerssfeeds': 'false',
              'input.enablemouse': 'false', 'screensaver.mode': '',
              'musiclibrary.downloadinfo': 'false', 'audiooutput.audiodevice': 'PULSE:apeture_qa'}
    for name in ('webserver', 'esenabled', 'esallinterfaces', 'zeroconf', 'wsdiscovery', 'airplay',
                 'upnp', 'upnpserver', 'upnprenderer'):
        values['services.' + name] = 'false'
    for name, value in values.items():
        ET.SubElement(settings, 'setting', id=name).text = value
    for name in ('resolutions', 'viewstates', 'skinsettings'):
        ET.SubElement(settings, name)
    ET.ElementTree(settings).write(userdata / 'guisettings.xml', encoding='utf-8', xml_declaration=True)
    (userdata / 'advancedsettings.xml').write_text('<advancedsettings><loglevel hide="false">1</loglevel></advancedsettings>', encoding='utf-8')
    sources = ET.Element('sources')
    files = ET.SubElement(sources, 'files')
    ET.SubElement(files, 'default', pathversion='1')
    source = ET.SubElement(files, 'source')
    ET.SubElement(source, 'name').text = 'Apeture CI packages'
    ET.SubElement(source, 'path', pathversion='1').text = str(target / 'packages') + '/'
    ET.SubElement(source, 'allowsharing').text = 'false'
    ET.ElementTree(sources).write(userdata / 'sources.xml', encoding='utf-8', xml_declaration=True)
    # Test entry shortcuts only. Install/confirm/toggle operations remain real UI.
    (userdata / 'keymaps/zip-smoke.xml').write_text('''<keymap><global><keyboard>
<f8 mod="ctrl">ActivateWindow(addonbrowser)</f8>
<f9 mod="ctrl">ActivateWindow(interfacesettings,lookandfeel.skin)</f9>
<f10 mod="ctrl">ActivateWindow(systemsettings,addons.unknownsources)</f10>
<f11 mod="ctrl">ActivateWindow(home)</f11>
</keyboard></global></keymap>''', encoding='utf-8')
    observer = system / 'addons' / OBSERVER
    observer.mkdir()
    shutil.copy2(root / 'tools/zip_smoke_observer.py', observer / 'service.py')
    (observer / 'addon.xml').write_text('''<addon id="service.apeture.zipsmoke" name="Apeture ZIP test observer" version="1.0.0" provider-name="Apeture CI">
<requires><import addon="xbmc.python" version="3.0.1"/></requires>
<extension point="xbmc.service" library="service.py"/>
<extension point="xbmc.addon.metadata"><summary lang="en_GB">Read-only disposable ZIP-test observer</summary><platform>all</platform><license>GPL-3.0-or-later</license></extension>
</addon>''', encoding='utf-8')
    ET.SubElement(manifest.getroot(), 'addon').text = OBSERVER
    manifest.write(system / 'system/addon-manifest.xml', encoding='utf-8', xml_declaration=True)
    assert not (data / 'addons').exists() and not (userdata / 'Database').exists()
    assert not any((system / 'addons' / addon).exists() for addon in SUBJECTS)
    (out / 'package-checksums.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
    (out / 'fixture.json').write_text(json.dumps({'fresh_subjects_absent': True, 'initial_skin': 'skin.estuary',
        'initial_unknown_sources': False, 'subjects': list(SUBJECTS), 'keymap_entry_shortcuts': True,
        'runtime': str(target), 'scope': 'Only our three verified local ZIPs; no user profile or network RPC'}, indent=2) + '\n', encoding='utf-8')
    return target, rows

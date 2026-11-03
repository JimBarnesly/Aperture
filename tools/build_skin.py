#!/usr/bin/env python3
"""Assemble a complete Kodi 21 Aperture ZIP from the installed official Estuary.

No profile, database, settings, system files or source skin are modified.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '4.0.1~rc1'
ADDON_ID = 'skin.aperture'


def copy_skin(source: Path, destination: Path, font_roots=()):
    """Materialize distro resource links. Fail closed on missing non-font assets."""
    if not source.is_dir() or destination.exists():
        raise ValueError('Source must exist and destination must be new')
    shutil.copytree(source, destination, symlinks=True)
    for original in source.rglob('*'):
        if not original.is_symlink():
            continue
        target = original.resolve()
        if not target.is_file() and original.suffix.lower() in ('.ttf', '.otf'):
            matches = sorted({p.resolve() for root in font_roots for p in Path(root).rglob(original.name) if p.is_file()})
            if len(matches) == 1:
                target = matches[0]
        if not target.is_file():
            raise ValueError(f'Unresolved distribution resource: {original}')
        copied = destination / original.relative_to(source)
        copied.unlink()
        shutil.copy2(target, copied)


def validate_skin(skin: Path):
    manifest = ET.parse(skin / 'addon.xml').getroot()
    if manifest.get('id') != ADDON_ID:
        raise ValueError('Wrong add-on ID')
    gui = manifest.find('./requires/import[@addon="xbmc.gui"]')
    if gui is None or gui.get('version') != '5.17.0':
        raise ValueError('Only Kodi 21 Omega GUI 5.17.0 is supported')
    for name in ('Home.xml', 'Font.xml', 'Settings.xml', 'SettingsCategory.xml', 'DialogConfirm.xml'):
        if not (skin / 'xml' / name).is_file():
            raise ValueError(f'Incomplete skin: {name}')
    for xml in skin.rglob('*.xml'):
        ET.parse(xml)
    fonts = ET.parse(skin / 'xml/Font.xml').getroot()
    font_names = {f.findtext('name') for f in fonts.iter('font')}
    for font in fonts.iter('font'):
        filename = font.findtext('filename')
        # Kodi supplies arial.ttf globally for the built-in Arial fallback fontset.
        if filename and filename != 'arial.ttf' and not (skin / 'fonts' / filename).is_file():
            raise ValueError(f'Missing font resource: {filename}')
    home = ET.parse(skin / 'xml/Home.xml').getroot()
    for font in home.iter('font'):
        if font.text not in font_names:
            raise ValueError(f'Home uses undefined font: {font.text}')
    ids = [c.get('id') for c in home.iter('control') if c.get('id')]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate Home control IDs')
    for node in home.iter():
        if node.tag in ('onup', 'ondown', 'onleft', 'onright') and (node.text or '').isdigit() and node.text not in ids:
            raise ValueError(f'Navigation points at missing Home control: {node.text}')
    if home.findtext('defaultcontrol') not in ids:
        raise ValueError('Home default control is missing')
    if any(p.is_symlink() for p in skin.rglob('*')):
        raise ValueError('Installable skin must contain resource bytes, not symlinks')


def assemble(source: Path, output: Path, home: Path, font_roots=()):
    if output.exists():
        if not (output / 'APERTURE_BUILD.json').is_file():
            raise ValueError(f'Refusing to replace unmarked output: {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='aperture-build-', dir=output.parent) as tmp:
        staged = Path(tmp) / ADDON_ID
        copy_skin(source, staged, font_roots)
        tree = ET.parse(staged / 'addon.xml')
        manifest = tree.getroot()
        if manifest.get('id') != 'skin.estuary':
            raise ValueError('Expected official Estuary source')
        upstream_version = manifest.get('version')
        manifest.set('id', ADDON_ID)
        manifest.set('name', 'Aperture')
        manifest.set('version', VERSION)
        manifest.set('provider-name', 'Aperture; Estuary by phil65 and contributors')
        metadata = manifest.find('./extension[@point="xbmc.addon.metadata"]')
        if metadata is not None:
            for node in list(metadata):
                if node.tag in ('summary', 'description', 'disclaimer', 'assets'):
                    metadata.remove(node)
            ET.SubElement(metadata, 'summary', {'lang': 'en_GB'}).text = 'Aperture: a controller-friendly Kodi home'
            ET.SubElement(metadata, 'description', {'lang': 'en_GB'}).text = 'Native media navigation and Format music on a complete Kodi Omega Estuary foundation.'
        tree.write(staged / 'addon.xml', encoding='utf-8', xml_declaration=True)
        shutil.copy2(home, staged / 'xml/Home.xml')
        notice = ROOT / 'docs/UPSTREAM.md'
        if notice.exists():
            shutil.copy2(notice, staged / 'APERTURE_NOTICE.md')
        info = {'addon': ADDON_ID, 'version': VERSION, 'source': 'installed official Kodi Estuary', 'upstream_version': upstream_version,
                'home_sha256': hashlib.sha256(home.read_bytes()).hexdigest()}
        (staged / 'APERTURE_BUILD.json').write_text(json.dumps(info, indent=2) + '\n')
        validate_skin(staged)
        if output.exists():
            shutil.rmtree(output)
        shutil.move(str(staged), str(output))
    return output


def package(skin: Path, output: Path):
    validate_skin(skin)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(skin.rglob('*')):
            if path.is_file():
                entry = zipfile.ZipInfo(f'{ADDON_ID}/{path.relative_to(skin).as_posix()}', (2026, 1, 1, 0, 0, 0))
                entry.external_attr = 0o100644 << 16
                entry.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entry, path.read_bytes())
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('/usr/share/kodi/addons/skin.estuary'))
    parser.add_argument('--font-root', action='append', type=Path, default=[Path('/usr/share/fonts')])
    parser.add_argument('--output', type=Path, default=ROOT / 'build' / ADDON_ID)
    args = parser.parse_args()
    assemble(args.source, args.output, ROOT / 'skin/xml/Home.xml', args.font_root)
    archive = ROOT / 'dist' / f'{ADDON_ID}-{VERSION}.zip'
    digest = package(args.output, archive)
    (archive.parent / 'checksums.json').write_text(json.dumps({archive.name: digest}, indent=2) + '\n')
    print(f'{digest}  {archive}')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Install opt-in PSX settings definitions only. Kodi must be closed.

No user preferences, save games, BIOS, core binary or ROM files are changed.
"""
import argparse
from pathlib import Path
import shutil
import tempfile
import time
import xml.etree.ElementTree as ET
from setup_gaming import ROOT, PREFIX, SetupError, require_stopped, atomic_install


def update(kodi_home):
    require_stopped()
    home = Path(kodi_home)
    addon = home/'addons'/(PREFIX+'pcsxrearmed')
    # Refuse redirected profile/addon paths, including a symlinked ancestor.
    for path in (home, *home.parents):
        if path.is_symlink(): raise SetupError('Refusing symlinked Kodi profile')
    for path in (home/'addons', addon):
        if path.is_symlink(): raise SetupError('Refusing symlinked add-on path')
    if not addon.is_dir(): raise SetupError('Aperture PCSX core is not installed in this profile')
    for path in addon.rglob('*'):
        if path.is_symlink(): raise SetupError('Refusing symlink inside existing core add-on')
    try:
        manifest = ET.parse(addon/'addon.xml').getroot()
    except (OSError, ET.ParseError) as exc:
        raise SetupError('Cannot read core manifest: '+str(exc)) from exc
    if manifest.get('id') != PREFIX+'pcsxrearmed': raise SetupError('Unexpected core add-on ID')
    if not (addon/'pcsx_rearmed_libretro.so').is_file(): raise SetupError('Existing core binary is missing')
    # Reuse the installer's tested transactional replacement, preserving all files
    # other than these shipped UI definitions, including the exact core binary.
    with tempfile.TemporaryDirectory(prefix='aperture-psx-settings-') as tmp:
        stage = Path(tmp)
        target = stage/addon.name
        shutil.copytree(addon,target)
        shutil.copytree(ROOT/'pcsx-settings/resources', target/'resources',dirs_exist_ok=True)
        backup = atomic_install(stage,home)
    print('PSX video settings installed. Native resolution remains the default.')
    print('Backup:', backup)
    print('Open Kodi → Add-ons → My add-ons → Game add-ons → Emulators → Aperture PlayStation → Configure.')
    print('Stop/restart a game after changing Enhanced resolution. Return to Native if slower or visually incorrect.')
    return backup

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install',action='store_true',required=True)
    parser.add_argument('--kodi-home',type=Path,default=Path.home()/'.kodi')
    args=parser.parse_args()
    try: update(args.kodi_home)
    except (SetupError,OSError) as exc: parser.exit(1,'ERROR: '+str(exc)+'\n')

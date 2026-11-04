#!/usr/bin/env python3
"""Update only the game browser while preserving cores, settings and saves."""
import argparse
import os
from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET
from setup_gaming import ROOT, LIBRARY_ID, SetupError, require_stopped, safe_profile_path, atomic_install


def update(kodi_home):
    kodi_home=Path(kodi_home)
    if not kodi_home.is_absolute() or kodi_home==Path("/"):
        raise SetupError("Select an absolute Kodi profile directory, not the filesystem root.")
    if os.geteuid()==0: raise SetupError('Run as the Kodi desktop user, not sudo.')
    require_stopped()
    target=kodi_home/'addons'/LIBRARY_ID
    for path in (target,kodi_home/'aperture-backups'):
        safe_profile_path(kodi_home,path)
    if not (target/'addon.xml').is_file():
        raise SetupError('Existing Aperture Game Library not found in this profile; use the full installer first.')
    source=ROOT/'games-kodi'
    for manifest in (source/'addon.xml',target/'addon.xml'):
        if ET.parse(manifest).getroot().get('id')!=LIBRARY_ID: raise SetupError('Unexpected game add-on identity')
    for script in source.rglob('*.py'):
        compile(script.read_text(),str(script),'exec')
    lock=kodi_home/'.aperture-gaming-install.lock'
    try: lock.mkdir()
    except FileExistsError: raise SetupError('Another gaming installation is active or its lock remains.')
    try:
        with tempfile.TemporaryDirectory(prefix='.aperture-game-update.',dir=kodi_home) as tmp:
            stage=Path(tmp)/LIBRARY_ID
            shutil.copytree(source,stage,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            require_stopped()
            backup=atomic_install(Path(tmp),kodi_home)
        print('Game browser updated. Existing ROM folder, cores, BIOS and saves are unchanged.')
        if backup: print('Previous browser backup:',backup)
        return backup
    finally:
        lock.rmdir()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kodi-home',default=os.environ.get('APERTURE_KODI_HOME',str(Path.home()/'.kodi')))
    args=parser.parse_args()
    try: update(args.kodi_home)
    except (SetupError,OSError,ET.ParseError,SyntaxError) as exc:
        parser.exit(1,'ERROR: '+str(exc)+'\n')

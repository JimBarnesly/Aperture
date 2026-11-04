#!/usr/bin/env python3
"""Install/update only Aperture Movies; preserve sources, settings and media."""
import argparse
import os
from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET
from setup_gaming import ROOT, SetupError, require_stopped, safe_profile_path, atomic_install
ID='plugin.video.aperture.movies'

def install(kodi_home):
    kodi_home=Path(kodi_home)
    if not kodi_home.is_absolute() or kodi_home==Path('/'):
        raise SetupError('Use an absolute Kodi profile directory, not filesystem root.')
    if os.geteuid()==0: raise SetupError('Run as the Kodi desktop user, not sudo.')
    require_stopped()
    target=kodi_home/'addons'/ID
    for path in (target,kodi_home/'aperture-backups'): safe_profile_path(kodi_home,path)
    source=ROOT/'movies-kodi'
    if ET.parse(source/'addon.xml').getroot().get('id')!=ID: raise SetupError('Unexpected source add-on')
    if target.exists() and ET.parse(target/'addon.xml').getroot().get('id')!=ID: raise SetupError('Unexpected installed add-on')
    for script in source.rglob('*.py'): compile(script.read_text(),str(script),'exec')
    kodi_home.mkdir(parents=True,exist_ok=True)
    lock=kodi_home/'.aperture-movies-install.lock'
    try: lock.mkdir()
    except FileExistsError: raise SetupError('Another movie installation is active or its lock remains.')
    try:
        with tempfile.TemporaryDirectory(prefix='.aperture-movies.',dir=kodi_home) as tmp:
            shutil.copytree(source,Path(tmp)/ID,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            require_stopped()
            backup=atomic_install(Path(tmp),kodi_home)
        print('Aperture Movies installed. Existing sources and media are unchanged.')
        if backup: print('Previous add-on backup:',backup)
        print('Restart Kodi and enable Aperture Movies in My add-ons if prompted.')
        return backup
    finally: lock.rmdir()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kodi-home',default=os.environ.get('APERTURE_KODI_HOME',str(Path.home()/'.kodi')))
    a=p.parse_args()
    try: install(a.kodi_home)
    except (SetupError,OSError,ET.ParseError,SyntaxError) as exc: p.exit(1,'ERROR: '+str(exc)+'\n')

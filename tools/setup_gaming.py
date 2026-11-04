#!/usr/bin/env python3
"""Aperture's conservative Kodi 21 gaming installer for Debian/Pi OS.

No ROM downloads, source mutations, mounting, database edits or remote-control
services. --check is read-only; --install is the explicit local install action.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
import json
import hashlib
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_ID = 'plugin.games.aperture'
PREFIX = 'game.libretro.aperture.'
FOLDERS = {'nes','snes','gb','gbc','gba','n64','megadrive','genesis','mastersystem','sms','gamegear','gg','pcengine','pce','atari2600','psx','ps1','arcade'}

@dataclass(frozen=True)
class Core:
    key: str
    title: str
    package: str
    library: str
    extensions: str
    license: str
    systems: tuple[str, ...]

CORES = (
 Core('nestopia','NES / Famicom','libretro-nestopia','nestopia_libretro.so','nes|fds|unf|unif','GPL-2.0-or-later',('nes',)),
 Core('snes9x','Super Nintendo','libretro-snes9x','snes9x_libretro.so','smc|sfc|swc|fig','Snes9x',('snes',)),
 Core('gambatte','Game Boy / Color','libretro-gambatte','gambatte_libretro.so','gb|gbc','GPL-2.0-or-later',('gb','gbc')),
 Core('mgba','Game Boy Advance','libretro-mgba','mgba_libretro.so','gba','MPL-2.0',('gba',)),
 Core('genesisplusgx','Mega Drive / Master System / Game Gear','libretro-genesisplusgx','genesis_plus_gx_libretro.so','md|gen|smd|bin|sms|gg','Non-commercial',('megadrive','genesis','mastersystem','sms','gamegear','gg')),
 Core('pcsxrearmed','PlayStation (PCSX ReARMed)','', 'pcsx_rearmed_libretro.so','cue|chd|iso|pbp|img|mdf|exe','GPL-2.0-or-later',('psx','ps1')),
)

class SetupError(RuntimeError): pass

def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)

def command_output(args):
    result = subprocess.run(args, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else ''

def kodi_running():
    # Check process names, not command lines (an installer may contain kodi).
    result = run(['ps','-eo','comm='], capture_output=True)
    return any(x.strip() in {'kodi','kodi.bin','kodi-wayland','kodi-x11','kodi-gbm'} for x in result.stdout.splitlines())

def require_stopped():
    if kodi_running():
        raise SetupError('Exit Kodi from its power menu, then rerun this same command. No live profile changes were made.')

def system_folders(root):
    try:
        return sorted(p.name for p in root.iterdir() if p.is_dir() and not p.is_symlink() and p.name.lower() in FOLDERS)
    except OSError:
        return []

def discover_roots(bases):
    """At most 3 directory levels / 1024 entries, no symlinks, no ROM scan."""
    found = []
    queue = [(Path(p),0) for p in bases]
    seen = set()
    count = 0
    while queue:
        path, depth = queue.pop(0)
        if path.is_symlink() or not path.is_dir(): continue
        resolved = str(path.resolve())
        if resolved in seen: continue
        seen.add(resolved)
        if system_folders(path):
            found.append(path)
            continue
        if depth >= 3: continue
        try:
            children = sorted(path.iterdir(), key=lambda p:p.name)
        except OSError: continue
        for child in children:
            count += 1
            if count > 1024:
                raise SetupError('Too many folders for automatic discovery. Supply --rom-root with the exact ROM folder.')
            if child.is_dir() and not child.is_symlink() and not child.name.startswith('.'):
                queue.append((child,depth+1))
    return sorted(found, key=str)

def select_root(explicit, candidates, interactive):
    if explicit:
        root = Path(explicit).expanduser()
        if not root.is_absolute() or root.is_symlink() or not system_folders(root):
            raise SetupError('ROM root must be an existing absolute directory containing system folders such as nes/ and psx/.')
        return root.resolve()
    if len(candidates)==1: return candidates[0].resolve()
    if not candidates:
        raise SetupError('No mounted ROM folder was found. Connect/mount the HDD normally, then rerun with --rom-root "/exact/path/to/roms". No disk was mounted or changed.')
    if not interactive:
        raise SetupError('Multiple ROM folders found; supply --rom-root. Candidates: '+', '.join(map(str,candidates)))
    print('Choose your ROM folder (nothing on this drive will be changed):')
    for i,p in enumerate(candidates,1): print(f'  {i}. {p}')
    answer=input('Number, or Enter to cancel: ').strip()
    if not answer.isdigit() or not 1 <= int(answer) <= len(candidates): raise SetupError('Cancelled before installation.')
    return candidates[int(answer)-1].resolve()

def package_candidate(package):
    text=command_output(['apt-cache','policy',package])
    match=re.search(r'^\s*Candidate:\s*(\S+)', text,re.M)
    return bool(match and match.group(1)!='(none)')

def installed_core(core):
    if not core.package: return None
    paths=command_output(['dpkg-query','-L',core.package]).splitlines()
    matches=[Path(p) for p in paths if Path(p).name==core.library and Path(p).is_file()]
    if len(matches)>1: raise SetupError(f'Ambiguous installed library for {core.package}')
    return matches[0] if matches else None

def write_xml(path, tree):
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree, space='  ')
    ET.ElementTree(tree).write(path, encoding='utf-8',xml_declaration=True)

def make_core_addon(core, library, destination):
    """Libretro cores are loaded through distro game.libretro, never as Kodi ABI libraries."""
    destination.mkdir(parents=True)
    shutil.copy2(library,destination/core.library)
    addon=ET.Element('addon',id=PREFIX+core.key,name='Aperture · '+core.title,version='0.1.0',**{'provider-name':'Aperture contributors'})
    requires=ET.SubElement(addon,'requires')
    ET.SubElement(requires,'import',addon='game.libretro',version='1.0.0')
    ET.SubElement(requires,'import',addon='game.controller.default',version='1.0.0')
    ext=ET.SubElement(addon,'extension',point='kodi.gameclient',library_linux=core.library)
    for k,v in {'platforms':core.title,'extensions':core.extensions,'supports_vfs':'false','supports_standalone':'false','supports_disc_control':'true' if core.key=='pcsxrearmed' else 'false','libretro_core':core.library.removesuffix('.so')}.items():
        ET.SubElement(ext,k).text=v
    meta=ET.SubElement(addon,'extension',point='xbmc.addon.metadata')
    for k,v in {'platform':'linux','license':core.license,'summary':'Local '+core.title+' core for Aperture','description':'Uses a separately sourced emulator library. No games or BIOS are included.'}.items():
        ET.SubElement(meta,k).text=v
    write_xml(destination/'addon.xml',addon)
    buttonmap=ET.Element('buttonmap',version='2')
    attrs={'id':'game.controller.default','type':'RETRO_DEVICE_ANALOG' if core.key=='pcsxrearmed' else 'RETRO_DEVICE_JOYPAD'}
    if core.key=='pcsxrearmed': attrs['subclass']='1'
    controller=ET.SubElement(buttonmap,'controller',attrs)
    names={'a':'B','b':'A','x':'Y','y':'X','start':'START','back':'SELECT','up':'UP','down':'DOWN','left':'LEFT','right':'RIGHT','leftbumper':'L','rightbumper':'R','lefttrigger':'L2','righttrigger':'R2','leftthumb':'L3','rightthumb':'R3'}
    for name,value in names.items(): ET.SubElement(controller,'feature',name=name,mapto='RETRO_DEVICE_ID_JOYPAD_'+value)
    if core.key=='pcsxrearmed':
        for name,value in {'leftstick':'RETRO_DEVICE_INDEX_ANALOG_LEFT','rightstick':'RETRO_DEVICE_INDEX_ANALOG_RIGHT','leftmotor':'RETRO_RUMBLE_STRONG','rightmotor':'RETRO_RUMBLE_WEAK'}.items():
            ET.SubElement(controller,'feature',name=name,mapto=value)
    write_xml(destination/'resources/buttonmap.xml',buttonmap)
    topology=ET.Element('logicaltopology')
    for number in ('1','2'):
        ET.SubElement(ET.SubElement(topology,'port',id=number,type='controller'),'accepts',controller='game.controller.default')
    write_xml(destination/'resources/topology.xml',topology)
    # Preserve the installed package's attribution/license without redistributing it remotely.
    if core.package:
        copyright=Path('/usr/share/doc')/core.package/'copyright'
        if copyright.is_file(): shutil.copy2(copyright,destination/'CORE_COPYRIGHT')
    else:
        for filename in ('COPYRIGHT.txt','provenance.json'):
            source=library.parent/filename
            if source.is_file(): shutil.copy2(source,destination/filename)
    (destination/'APERTURE_CORE.json').write_text(json.dumps({'package':core.package or 'official libretro/pcsx_rearmed pinned source','library':core.library,'systems':core.systems},indent=2)+'\n')

def safe_profile_path(kodi_home, path):
    """Reject redirecting symlink components; this is not a hostile-race sandbox."""
    if '..' in Path(kodi_home).parts or '..' in Path(path).parts:
        raise SetupError('Parent traversal is not accepted in profile paths')
    home=Path(kodi_home).absolute(); path=Path(path).absolute()
    for ancestor in (home,*home.parents):
        if ancestor.is_symlink(): raise SetupError('Refusing symlinked profile ancestor: '+str(ancestor))
    try: relative=path.relative_to(home)
    except ValueError: raise SetupError('Path is outside selected Kodi profile')
    current=home
    for part in (None,*relative.parts):
        if part is not None: current=current/part
        if current.is_symlink(): raise SetupError('Refusing symlinked profile path: '+str(current))
    return path

def atomic_apply(items, kodi_home):
    """Preflight all targets, then commit file/directory replacements with rollback."""
    backup_root=kodi_home/'aperture-backups'/('gaming-'+str(time.time_ns()))
    safe_profile_path(kodi_home,backup_root)
    if len({str(t.absolute()) for _,t in items}) != len(items):
        raise SetupError('Duplicate transaction targets are not allowed')
    for source,target in items:
        safe_profile_path(kodi_home,target)
        if target.exists() and source.is_dir()!=target.is_dir():
            raise SetupError('Target type differs from staged item: '+str(target))
        if target.exists() and not (target.is_file() or target.is_dir()):
            raise SetupError('Unsupported profile target: '+str(target))
    replaced=[]
    try:
        for source,target in items:
            target.parent.mkdir(parents=True,exist_ok=True)
            backup=None
            if target.exists():
                backup=backup_root/target.relative_to(kodi_home)
                backup.parent.mkdir(parents=True,exist_ok=True)
                target.rename(backup)
            try: source.rename(target)
            except BaseException:
                if backup: backup.rename(target)
                raise
            replaced.append((target,backup))
    except BaseException:
        for target,backup in reversed(replaced):
            if target.is_dir(): shutil.rmtree(target)
            else: target.unlink()
            if backup: backup.rename(target)
        raise
    return backup_root if backup_root.exists() else None

def atomic_install(staged,kodi_home):
    # Legacy helper retained for isolated add-on installation tests.
    backup=atomic_apply([(source,kodi_home/'addons'/source.name) for source in sorted(staged.iterdir())],kodi_home)
    return backup/'addons' if backup else None

def rom_settings_tree(path, root):
    if path.exists():
        tree=ET.parse(path).getroot()
        if tree.tag!='settings': raise SetupError('Invalid existing game settings; not overwritten')
    else: tree=ET.Element('settings',version='2')
    # Convert legacy value attributes throughout, preserving each unrelated value.
    tree.set('version','2')
    for node in tree.findall('setting'):
        if 'value' in node.attrib:
            node.text=node.attrib.pop('value')
    matches=tree.findall("setting[@id='rom_root']")
    for node in matches: tree.remove(node)
    ET.SubElement(tree,'setting',id='rom_root').text=str(root)
    return tree

def set_rom_root(kodi_home, root):
    path=kodi_home/'userdata/addon_data'/LIBRARY_ID/'settings.xml'
    safe_profile_path(kodi_home,path)
    tree=rom_settings_tree(path,root)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists(): shutil.copy2(path,path.with_name('settings.xml.before-aperture-'+str(time.time_ns())))
    fd,name=tempfile.mkstemp(prefix='.aperture-settings.',dir=path.parent)
    os.close(fd); temporary=Path(name)
    try:
        write_xml(temporary,tree)
        temporary.replace(path)
    finally: temporary.unlink(missing_ok=True)

def bios_status(root):
    candidates=[root/'bios',root/'BIOS',root.parent/'bios',root.parent/'BIOS']
    known={'scph5500.bin','scph5501.bin','scph5502.bin','scph1001.bin','scph101.bin','scph7001.bin','psxonpsp660.bin'}
    found=[]
    for folder in candidates:
        if folder.is_symlink() or not folder.is_dir(): continue
        for path in sorted(folder.iterdir()):
            if path.is_file() and not path.is_symlink() and path.name.lower() in known and path.stat().st_size==524288:
                found.append(path)
    grouped={}
    for path in found: grouped.setdefault(path.name.lower(),[]).append(path)
    result=[]
    for name,paths in grouped.items():
        digests={hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        if len(digests)>1:
            raise SetupError('Conflicting BIOS files named '+name+'; choose one source manually before installation')
        result.append(paths[0])
    return result

def install_bios(files, kodi_home):
    folder=kodi_home/'userdata/addon_data'/(PREFIX+'pcsxrearmed')/'resources/system'
    safe_profile_path(kodi_home,folder)
    folder.mkdir(parents=True,exist_ok=True)
    copied=[]
    for source in files:
        target=folder/source.name.lower()
        safe_profile_path(kodi_home,target)
        if not target.exists() and not target.is_symlink():
            shutil.copy2(source,target); copied.append(target.name)
    return copied

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check',action='store_true')
    mode.add_argument('--install',action='store_true')
    parser.add_argument('--rom-root')
    parser.add_argument('--kodi-home',default=str(Path.home()/'.kodi'))
    parser.add_argument('--skip-psx-build',action='store_true',help='Install cartridge cores only; PSX remains unavailable')
    args=parser.parse_args(argv)
    kodi_home=Path(args.kodi_home).expanduser()
    if not kodi_home.is_absolute() or kodi_home.is_symlink(): raise SetupError('Kodi home must be an absolute, non-symlink directory')
    version=command_output(['dpkg-query','-W','-f=${Version}','kodi-bin'])
    arch=command_output(['dpkg','--print-architecture'])
    print('Kodi package:', version or 'not found', '| architecture:', arch)
    print('Kodi running:',kodi_running())
    bases=[Path('/media')/os.environ.get('USER',''),Path('/run/media')/os.environ.get('USER',''),Path('/mnt')]
    candidates=discover_roots(bases) if not args.rom_root else []
    available={c.key:package_candidate(c.package) for c in CORES if c.package}
    print('Available distribution cores:', ', '.join(k for k,v in available.items() if v) or 'none')
    print('Unavailable distribution cores:', ', '.join(k for k,v in available.items() if not v) or 'none')
    for p in candidates: print('ROM root candidate:',p)
    if args.check: return 0
    if os.geteuid()==0: raise SetupError('Run as the Kodi desktop user, not sudo. Only package installation uses sudo.')
    if not re.match(r'^(?:\d+:)?21\.',version): raise SetupError('This candidate requires distro Kodi 21. No Kodi upgrade or repository change will be attempted.')
    if arch not in ('arm64','amd64'): raise SetupError('This tested build route supports 64-bit arm64 or amd64 only; no OS conversion is attempted.')
    require_stopped()
    for relative in ('addons','aperture-backups','userdata/addon_data/'+LIBRARY_ID+'/settings.xml','userdata/addon_data/'+PREFIX+'pcsxrearmed/resources/system'):
        safe_profile_path(kodi_home,kodi_home/relative)
    root=select_root(args.rom_root,candidates,sys.stdin.isatty())
    rom_settings_tree(kodi_home/'userdata/addon_data'/LIBRARY_ID/'settings.xml',root)
    bios_status(root)  # Detect ambiguity before package/profile changes.
    print('ROM folder:',root,'| systems:',', '.join(system_folders(root)))
    packages=['kodi-game-libretro','kodi-peripheral-joystick']+[c.package for c in CORES if c.package and available[c.key]]
    if not args.skip_psx_build: packages += ['build-essential','binutils','ca-certificates']
    unavailable=[p for p in packages if not package_candidate(p)]
    if unavailable: raise SetupError('Required packages are unavailable from your configured repositories: '+', '.join(unavailable))
    if not any(available.values()): raise SetupError('No cartridge core packages found. Run sudo apt-get update normally and retry; no repositories are changed here.')
    # No auto-upgrades/removals, no new repositories and no accepted package prompts.
    # APT still presents its normal package list and confirmation to the user.
    run(['apt-get','--simulate','--no-remove','--no-install-recommends','--no-upgrade','install',*packages])
    print('Installing the listed packages from your existing signed OS repositories.')
    run(['sudo','apt-get','--no-remove','--no-install-recommends','--no-upgrade','install',*packages])
    require_stopped()
    libraries={c.key:installed_core(c) for c in CORES if c.package and available[c.key]}
    if not args.skip_psx_build:
        from build_pcsx_core import build_core
        result=build_core(Path.home()/'.cache/aperture/pcsx-rearmed')
        libraries['pcsxrearmed']=Path(result)
    missing=[k for k,v in libraries.items() if not v or not v.is_file()]
    if missing: raise SetupError('Installed package did not provide expected core: '+', '.join(missing))
    require_stopped()
    kodi_home.mkdir(parents=True,exist_ok=True)
    lock=kodi_home/'.aperture-gaming-install.lock'
    try: lock.mkdir()
    except FileExistsError: raise SetupError('Another gaming install is active, or its lock remains: '+str(lock))
    try:
        with tempfile.TemporaryDirectory(prefix='.aperture-gaming.',dir=kodi_home) as tmp:
            stage=Path(tmp)/'addons'; stage.mkdir()
            shutil.copytree(ROOT/'games-kodi',stage/LIBRARY_ID,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            for c in CORES:
                if c.key in libraries: make_core_addon(c,libraries[c.key],stage/(PREFIX+c.key))
            settings=kodi_home/'userdata/addon_data'/LIBRARY_ID/'settings.xml'
            safe_profile_path(kodi_home,settings)
            staged_settings=Path(tmp)/'settings.xml'
            write_xml(staged_settings,rom_settings_tree(settings,root))
            items=[(source,kodi_home/'addons'/source.name) for source in sorted(stage.iterdir())]
            items.append((staged_settings,settings))
            copied=[]
            bios_folder=kodi_home/'userdata/addon_data'/(PREFIX+'pcsxrearmed')/'resources/system'
            safe_profile_path(kodi_home,bios_folder)
            for source in bios_status(root):
                target=bios_folder/source.name.lower()
                safe_profile_path(kodi_home,target)
                if target.exists():
                    if not target.is_file(): raise SetupError('BIOS destination is not a file: '+str(target))
                    continue
                if target.name in copied: continue
                prepared=Path(tmp)/target.name; shutil.copy2(source,prepared)
                items.append((prepared,target)); copied.append(target.name)
            require_stopped()
            backup=atomic_apply(items,kodi_home)
        print('\nInstalled game library and cores:', ', '.join(libraries))
        if backup: print('Previous add-ons backed up:',backup)
        print('PSX BIOS copied:',', '.join(copied) or 'none (existing BIOS preserved; HLE is not guaranteed compatible)')
        supported={system for c in CORES if c.key in libraries for system in c.systems}
        uncovered=[system for system in system_folders(root) if system.lower() not in supported]
        if uncovered: print('Detected systems not provisioned by this installer:',', '.join(uncovered))
        print('Restart Kodi. Enable Aperture Game Library and its game cores in Add-ons > My add-ons if prompted.')
        print('Pair your controller, then Settings > System > Input > Configure attached controllers if automatic mapping is wrong.')
        print('Open Games > Game add-ons > Aperture Game Library. Use the controller guide button for the game menu/exit.')
        print('No ROM, music or movie files were modified. No actual Pi gameplay/controller/audio test has been performed by this installer.')
        return 0
    finally: lock.rmdir()

if __name__=='__main__':
    try: sys.exit(main())
    except (SetupError,subprocess.CalledProcessError,OSError,ET.ParseError) as exc:
        print('ERROR:',exc,file=sys.stderr); sys.exit(1)

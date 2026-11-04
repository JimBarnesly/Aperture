#!/usr/bin/env python3
"""Original tiny hardware-test ROMs and isolated Kodi fixture (no commercial data)."""
import argparse
import os
from pathlib import Path
import shutil
import struct
import sys
import xml.etree.ElementTree as ET
from setup_gaming import CORES, PREFIX, LIBRARY_ID, make_core_addon, set_rom_root

def make_nes(path):
    # NROM: rendering disabled, universal backdrop set to green. Infinite CPU loop.
    code=bytes.fromhex('78 d8 a2 ff 9a e8 8e 00 20 8e 01 20 2c 02 20 10 fb a9 3f 8d 06 20 a9 00 8d 06 20 a9 2a 8d 07 20 4c 20 80')
    prg=bytearray(16384); prg[:len(code)]=code
    prg[-6:]=struct.pack('<HHH',0x8020,0x8000,0x8020)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(b'NES\x1a'+bytes([1,1])+bytes(10)+prg+bytes(8192))

def make_psx(path):
    # Original PS-X EXE: GPU reset, display parameters, green rectangle, loop.
    words=[0x3c081f80,0x35081814,0xad000000,0x3c090300,0xad090000,
           0x3c090800,0x35290001,0xad090000,0x3c0906c6,0x35290260,0xad090000,
           0x3c090704,0x35292018,0xad090000,0x2508fffc,
           0x3c090200,0x3529ff00,0xad090000,0xad000000,0x3c0900f0,0x35290140,0xad090000,
           0x1000ffff,0x00000000]
    payload=b''.join(struct.pack('<I',x) for x in words).ljust(2048,b'\0')
    header=bytearray(2048); header[:8]=b'PS-X EXE'
    for offset,value in [(0x10,0x80010000),(0x18,0x80010000),(0x1c,len(payload)),(0x30,0x801fff00)]:
        struct.pack_into('<I',header,offset,value)
    path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(header+payload)

def prepare(root,runtime,out,pcsx):
    from build_skin import copy_skin
    copy_skin(Path('/usr/share/kodi'),runtime/'system',font_roots=(Path('/usr/share/fonts'),))
    addons=runtime/'system/addons'
    nestopia=CORES[0]
    # The exact installed signed-package library is discovered by dpkg.
    from setup_gaming import installed_core
    lib=installed_core(nestopia)
    if lib is None: raise RuntimeError('NES core not installed')
    make_core_addon(nestopia,lib,addons/(PREFIX+nestopia.key))
    make_core_addon(CORES[-1],pcsx,addons/(PREFIX+CORES[-1].key))
    shutil.copytree(root/'games-kodi',addons/LIBRARY_ID,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    service=addons/'service.aperture.gamingqa'; service.mkdir()
    (service/'addon.xml').write_text('<addon id="service.aperture.gamingqa" name="Gaming QA" version="1.0.0" provider-name="Aperture"><requires><import addon="xbmc.python" version="3.0.1"/></requires><extension point="xbmc.service" library="service.py"/><extension point="xbmc.addon.metadata"><platform>all</platform><license>GPL-3.0-or-later</license></extension></addon>')
    shutil.copy2(root/'tools/gaming_qa_service.py',service/'service.py')
    manifest=runtime/'system/system/addon-manifest.xml'; tree=ET.parse(manifest)
    for name in ('game.libretro','peripheral.joystick',PREFIX+'nestopia',PREFIX+'pcsxrearmed',LIBRARY_ID,'service.aperture.gamingqa'):
        if not any(e.text==name for e in tree.getroot().findall('addon')):
            attrs={'optional':'true'} if name.startswith(('game.libretro','peripheral.')) else {}
            ET.SubElement(tree.getroot(),'addon',attrs).text=name
    tree.write(manifest,encoding='utf-8',xml_declaration=True)
    roms=runtime/'roms'; make_nes(roms/'nes/Aperture Palette Probe.nes'); make_psx(roms/'psx/Aperture GPU Probe.exe')
    set_rom_root(runtime/'data',roms)
    userdata=runtime/'data/userdata'
    (userdata/'guisettings.xml').write_text('''<settings version="2">
<setting id="lookandfeel.skin">skin.estuary</setting>
<setting id="services.webserver">false</setting><setting id="services.esenabled">false</setting>
<setting id="services.zeroconf">false</setting><setting id="services.airplay">false</setting>
<setting id="services.upnpserver">false</setting><setting id="addons.unknownsources">false</setting>
<setting id="audiooutput.audiodevice">PULSE:Default</setting><setting id="screensaver.mode"></setting>
<setting id="gamesgeneral.showosdhelp">false</setting>
<setting id="gamesgeneral.enableautosave">false</setting>
<resolutions/><viewstates/><skinsettings/>
</settings>''')
    (userdata/'advancedsettings.xml').write_text('<advancedsettings><loglevel hide="false">1</loglevel></advancedsettings>')
    (out/'fixture.json').write_text(__import__('json').dumps({'runtime':str(runtime),'roms':str(roms),'commercial_data':False}))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,required=True); p.add_argument('--runtime',type=Path,required=True); p.add_argument('--out',type=Path,required=True); p.add_argument('--pcsx',type=Path,required=True); a=p.parse_args()
    prepare(a.root,a.runtime,a.out,a.pcsx)

#!/usr/bin/env python3
"""Disposable movie QA fixture. Every frame and artwork pixel is generated locally."""
import argparse
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

PLUGIN = 'plugin.video.aperture.movies'
SERVICE = 'service.aperture.moviesqa'


def artwork(path, title, poster=False, blue=False):
    from PIL import Image, ImageDraw, ImageFont
    width, height = (600, 900) if poster else (1280, 720)
    image = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / height
        rgb = (int(10 + 18*t), int(27 + 60*t), int(46 + 95*t)) if blue else (int(28 + 120*t), int(18 + 52*t), int(31 + 20*t))
        draw.line((0, y, width, y), fill=rgb)
    sun = (width*.7, height*.32)
    radius = width*.16
    draw.ellipse((sun[0]-radius,sun[1]-radius,sun[0]+radius,sun[1]+radius), fill='#b4dbe4' if blue else '#f1b471')
    for i in range(4):
        y = int(height * (.57+i*.1))
        draw.polygon([(0,y),(width*.3,y-height*.12),(width*.65,y+height*.04),(width,y-height*.09),(width,height),(0,height)], fill=(10+i*4, 18+i*5, 26+i*5))
    font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    if not Path(font_path).is_file():
        fonts=list(Path('/usr/share/fonts').rglob('NotoSans-Regular.ttf'))
        font_path=str(fonts[0]) if fonts else None
    font=ImageFont.truetype(font_path, 42 if poster else 34) if font_path else ImageFont.load_default()
    small=ImageFont.truetype(font_path, 16) if font_path else font
    draw.text((width*.08,height*.79),title,fill='#fff5e7',font=font)
    draw.text((width*.08,height*.88),'APERTURE / ORIGINAL QA FIXTURE',fill='#bed0da',font=small)
    image.save(path, quality=95)


def movie(folder, title, blue=False):
    folder.mkdir(parents=True, exist_ok=True)
    path=folder/(title+'.mkv')
    # 45 seconds gives the actual GUI time to select, play, capture and stop.
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i',
                    'color=c=0x146b3a:s=640x360:r=24','-f','lavfi','-i',
                    'sine=frequency=440:sample_rate=48000','-t','45','-c:v','mpeg4',
                    '-q:v','4','-c:a','aac','-b:a','64k','-shortest',str(path)],check=True)
    artwork(folder/(title+'-poster.jpg'),title,poster=True,blue=blue)
    artwork(folder/(title+'-fanart.jpg'),title,blue=blue)
    nfo=ET.Element('movie')
    for key,value in {'title':title,'year':'2026','plot':'An original, locally generated picture and sound fixture. No public or personal media.','genre':'Adventure','runtime':'1'}.items():
        ET.SubElement(nfo,key).text=value
    ET.ElementTree(nfo).write(folder/(title+'.nfo'),encoding='utf-8',xml_declaration=True)
    return path


def prepare(root, runtime, out, scenario):
    from build_skin import copy_skin, assemble
    if not runtime.name.startswith('aperture-movies-qa.'):
        raise ValueError('A disposable movies runtime is required')
    copy_skin(Path('/usr/share/kodi'),runtime/'system',font_roots=(Path('/usr/share/fonts'),))
    addons=runtime/'system/addons'
    assemble(addons/'skin.estuary',addons/'skin.aperture',root/'skin/xml/Home.xml')
    video_view=addons/'skin.aperture/xml/MyVideoNav.xml'
    if not video_view.is_file() or ET.parse(video_view).find('.//control[@id="61"]') is None:
        raise RuntimeError('Built cinematic video window 61 missing')
    shutil.copytree(root/'movies-kodi',addons/PLUGIN,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    service=addons/SERVICE; service.mkdir()
    (service/'addon.xml').write_text('<addon id="'+SERVICE+'" name="Movies QA" version="1.0.0" provider-name="Aperture"><requires><import addon="xbmc.python" version="3.0.1"/></requires><extension point="xbmc.service" library="service.py"/><extension point="xbmc.addon.metadata"><platform>all</platform><license>GPL-3.0-or-later</license></extension></addon>')
    shutil.copy2(root/('tools/movies_online_qa_service.py' if scenario == 'online' else 'tools/movies_qa_service.py'),service/'service.py')
    if scenario == 'online':
        # Alter only the disposable copied add-on, never the production package.
        lib = addons/PLUGIN/'resources/lib'
        shutil.copy2(root/'tools/movies_online_mocks.py', lib/'qa_provider.py')
        with (lib/'catalog.py').open('a') as stream:
            stream.write('\nfrom resources.lib.qa_provider import catalogue as _qa_catalogue\nbrowse.__defaults__ = (_qa_catalogue,)\ndetails.__defaults__ = (_qa_catalogue,)\n')
        with (lib/'debrid.py').open('a') as stream:
            stream.write('\nfrom resources.lib.qa_provider import debrid as _qa_debrid\nClient.__init__.__defaults__ = (_qa_debrid, time.time)\n')
    manifest=runtime/'system/system/addon-manifest.xml'; tree=ET.parse(manifest)
    for name in (PLUGIN,SERVICE,'skin.aperture'):
        if not any(e.text==name for e in tree.getroot().findall('addon')):
            ET.SubElement(tree.getroot(),'addon').text=name
    tree.write(manifest,encoding='utf-8',xml_declaration=True)
    media=runtime/'movies'; movie(media,'Amber Horizon'); movie(media/'Collections','Blue Meridian',True)
    other=runtime/'other-movies'; other.mkdir()
    userdata=runtime/'data/userdata'; userdata.mkdir(parents=True,exist_ok=True)
    sources=ET.Element('sources'); video=ET.SubElement(sources,'video')
    ET.SubElement(video,'default',{'pathversion':'1'}).text=str(media)+'/' if scenario=='default' else ''
    if scenario!='empty':
        for name,path in [('Cinema',media)]+([('Archive',other)] if scenario in ('default','multiple') else []):
            source=ET.SubElement(video,'source'); ET.SubElement(source,'name').text=name
            ET.SubElement(source,'path',{'pathversion':'1'}).text=str(path)+'/'
            ET.SubElement(source,'allowsharing').text='false'
    ET.ElementTree(sources).write(userdata/'sources.xml',encoding='utf-8',xml_declaration=True)
    shutil.copy2(userdata/'sources.xml',out/'sources.xml')
    (userdata/'guisettings.xml').write_text('''<settings version="2">
<setting id="lookandfeel.skin">skin.aperture</setting>
<setting id="services.webserver">false</setting><setting id="services.esenabled">false</setting>
<setting id="services.zeroconf">false</setting><setting id="services.airplay">false</setting>
<setting id="services.upnpserver">false</setting><setting id="addons.unknownsources">false</setting>
<setting id="audiooutput.audiodevice">PULSE:Default</setting><setting id="screensaver.mode"></setting>
<setting id="videoplayer.adjustrefreshrate">0</setting>
<resolutions/><viewstates/><skinsettings/></settings>''')
    (userdata/'advancedsettings.xml').write_text('<advancedsettings><loglevel hide="false">1</loglevel></advancedsettings>')
    (out/'fixture.json').write_text(json.dumps({'runtime':str(runtime),'media':str(media),'scenario':scenario,'personal_or_public_media':False,'generated_video_seconds':45,'plugin':PLUGIN,'video_window_sha256':hashlib.sha256(video_view.read_bytes()).hexdigest(),'plugin_sha256':hashlib.sha256((addons/PLUGIN/'addon.py').read_bytes()).hexdigest()},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,required=True); p.add_argument('--runtime',type=Path,required=True); p.add_argument('--out',type=Path,required=True); p.add_argument('--scenario',choices=('single','default','multiple','empty','online'),required=True); a=p.parse_args()
    prepare(a.root,a.runtime,a.out,a.scenario)


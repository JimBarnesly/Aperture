#!/usr/bin/env python3
"""Render labelled design previews from the Games XML. This is NOT Kodi QA.

Uses only original local artwork and synthetic item data. It does not start
Kodi, connect to a library, or certify navigation, scaling or input behavior.
"""
from pathlib import Path
import argparse
import re
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]

def render(destination,selected='psx',width=1920,font_path=None):
 font_path=font_path or Path('/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf')
 if not Path(font_path).is_file(): raise ValueError('Provide --font pointing to NotoSans-Regular.ttf from the built Kodi skin')
 tree=ET.parse(ROOT/'skin/xml/MyGames.xml')
 group=next(e for e in tree.findall('./controls/control') if e.findtext('visible')=='Control.IsVisible(59)')
 out=Image.new('RGBA',(1920,1080),(16,29,38,255))
 names={'nes':'Nintendo Entertainment System','snes':'Super Nintendo','gb':'Game Boy','gbc':'Game Boy Color','gba':'Game Boy Advance','n64':'Nintendo 64','megadrive':'Sega Mega Drive / Genesis','mastersystem':'Sega Master System','gamegear':'Sega Game Gear','pcengine':'PC Engine / TurboGrafx-16','atari2600':'Atari 2600','psx':'Sony PlayStation','arcade':'Arcade'}
 ids=list(names); center=ids.index(selected); data=[ids[(center+i)%len(ids)] for i in (-1,0,1)]
 def value(text,ident):
  return (text or '').replace('$INFO[ListItem.Property(Aperture.System),aperture/games/systems/,.png]','aperture/games/systems/'+ident+'.png').replace('$INFO[ListItem.Label]',names[ident]).replace('$INFO[System.Time]','19:42').replace('$INFO[ListItem.Property(Aperture.GameCount),, games]','12 games').replace('$INFO[Container(59).CurrentItem]',str(center+1)).replace('$INFO[Container(59).NumItems]',str(len(ids)))
 def paint(c,ident,ox=0,oy=0):
  typ=c.get('type'); vis=c.findtext('visible','')
  if 'String.IsEqual(ListItem.Property(Aperture.Action)' in vis or vis=='ListItem.IsParentFolder' or vis=='String.IsEqual(ListItem.Property(Aperture.GameCount),1)': return
  x=int(c.findtext('left','0'))+ox; y=int(c.findtext('top','0'))+oy; w=int(c.findtext('width','0')); h=int(c.findtext('height','0'))
  if typ=='image':
   tex=c.find('texture'); p=ROOT/'skin/media'/value(tex.text,ident)
   im=Image.open(p).convert('RGBA').resize((w,h),Image.Resampling.LANCZOS)
   diffuse=c.findtext('colordiffuse','FFFFFFFF'); alpha=int(diffuse[:2],16)
   if alpha!=255: im.putalpha(im.getchannel('A').point(lambda n:n*alpha//255))
   out.alpha_composite(im,(x,y)); return
  if typ not in ('label','textbox'): return
  text=value(c.findtext('label'),ident); size=int(re.findall(r'\d+',c.findtext('font','font27'))[0]); font=ImageFont.truetype(str(font_path),size)
  draw=ImageDraw.Draw(out); color='#'+c.findtext('textcolor','FFFFFFFF')[2:]
  words=text.split(); lines=[]; current=''
  for word in words:
   candidate=(current+' '+word).strip()
   if draw.textlength(candidate,font=font)>w and current: lines.append(current); current=word
   else: current=candidate
  if current: lines.append(current)
  if typ=='label': lines=[text]
  lh=size*1.28; y+=(h-lh*len(lines))/2
  for line in lines:
   tx=x; length=draw.textlength(line,font=font); align=c.findtext('align')
   if align=='center': tx+=(w-length)/2
   if align=='right': tx+=w-length
   draw.text((tx,y),line,font=font,fill=color); y+=lh
 for c in group.findall('control'):
  if c.get('id')=='59':
   for i,ident in enumerate(data):
    layout=c.find('focusedlayout' if i==1 else 'itemlayout')
    for child in layout.findall('control'): paint(child,ident,int(c.findtext('left'))+i*620,int(c.findtext('top')))
  else: paint(c,selected)
 out=out.convert('RGB').resize((width,width*1080//1920),Image.Resampling.LANCZOS)
 marked=Image.new('RGB',(width,out.height+36),'#e5e7e6'); marked.paste(out,(0,0))
 ImageDraw.Draw(marked).text((18,out.height+8),'DESIGN PREVIEW  |  Final XML + original artwork. Synthetic library. Not a Kodi capture.',font=ImageFont.truetype(str(font_path),max(12,width//110)),fill='#34424a')
 Path(destination).parent.mkdir(parents=True,exist_ok=True); marked.save(destination)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--system',default='psx');p.add_argument('--width',type=int,default=1920);p.add_argument('--font',type=Path);a=p.parse_args();render(a.output,a.system,a.width,a.font)

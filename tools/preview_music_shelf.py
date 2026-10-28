#!/usr/bin/env python3
"""XML-derived layout preview with synthetic art, NOT native Kodi evidence.

Perspective is an approximate static projection. Actual Kodi rendering, focus,
animations and playback must be verified separately. All metadata is mock data.
"""
from __future__ import annotations
import argparse
import io
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "addons/script.apeture.music"
LAYOUT = ADDON / "resources/skins/Default/1080i/script-apeture-music.xml"
MEDIA = ADDON / "resources/skins/Default/media"


def preview(destination: Path):
    skin = ROOT / "build/skin.apeture"
    font_specs = {node.findtext('name'): (node.findtext('filename'), int(node.findtext('size')))
                  for node in ET.parse(skin / 'xml/Font.xml').getroot()[0]}
    outlines, fonts = {}, {}
    def font(name):
        if name not in fonts:
            filename, size = font_specs[name]
            if filename not in outlines:
                data = TTFont(skin / 'fonts' / filename)
                for table in ('fpgm', 'prep', 'cvt '):
                    if table in data: del data[table]
                if 'glyf' in data:
                    for glyph in data['glyf'].glyphs.values(): glyph.removeHinting()
                buffer = io.BytesIO(); data.save(buffer); outlines[filename] = buffer.getvalue()
            fonts[name] = ImageFont.truetype(io.BytesIO(outlines[filename]), size)
        return fonts[name]
    properties = {'Shelf.Backdrop': 'special://skin/media/apeture/misty-stone-bridge.png',
                  'Shelf.Title': 'Mock record — layout only', 'Shelf.Artist': 'Synthetic preview artist',
                  'Shelf.Year': '2003', 'Shelf.Position': '4 / 7', 'Shelf.Primary': 'Play album',
                  'Shelf.Ready': 'true'}
    for i in range(7):
        properties['Shelf.Cover%d.Art' % i] = 'shelf/placeholder.png'
        properties['Shelf.Cover%d.Visible' % i] = 'true'
    def resolve(value):
        if value == '$INFO[System.Time]': return '20:26'
        match = re.fullmatch(r'\$INFO\[Window.Property\(([^)]+)\)\]', value or '')
        return properties.get(match[1], '') if match else (value or '')
    def visible(value):
        if not value: return True
        if ' + ' in value: return all(visible(part) for part in value.split(' + '))
        if value.startswith('!'): return not visible(value[1:])
        match = re.fullmatch(r'String.IsEqual\(Window.Property\(([^)]+)\),([^)]*)\)', value)
        if match: return properties.get(match[1], '') == match[2]
        raise ValueError('Unknown preview condition: ' + value)
    canvas = Image.new('RGBA', (1920, 1080), (12, 20, 22, 255))
    for control in ET.parse(LAYOUT).getroot().find('controls'):
        if not visible(control.findtext('visible')): continue
        x,y,w,h = [int(control.findtext(k, '0')) for k in ('left', 'top', 'width', 'height')]
        kind = control.get('type')
        if kind == 'image':
            tex = control.find('texture'); filename = resolve(tex.text)
            path = skin / filename.removeprefix('special://skin/') if filename.startswith('special://skin/') else MEDIA / filename
            image = Image.open(path).convert('RGBA').resize((w,h), Image.Resampling.LANCZOS)
            if filename == 'shelf/placeholder.png':
                draw = ImageDraw.Draw(image)
                draw.text((w/2, h*0.84), 'MOCK COVER', font=font('font13'), anchor='mm', fill=(208,228,230,255))
            color = tex.get('colordiffuse', 'FFFFFFFF')
            alpha,red,green,blue = [int(color[i:i+2],16) for i in range(0,8,2)]
            channels = image.split()
            image = Image.merge('RGBA', tuple(channel.point(lambda v, f=factor: v*f//255)
                                               for channel,factor in zip(channels,(red,green,blue,alpha))))
            animation = control.find("animation[@effect='rotatey']")
            if animation is not None:
                angle = float(animation.get('end')); narrow = max(1, round(w*math.cos(math.radians(angle))))
                image = image.resize((narrow,h),Image.Resampling.LANCZOS)
                # Approximate a fixed perspective tilt, not Kodi's projection matrix.
                inset = round(h*0.075)
                if angle > 0: quad = (0,inset,0,h-inset,narrow,h,narrow,0)
                else: quad = (0,0,0,h,narrow,h-inset,narrow,inset)
                image = image.transform((narrow,h),Image.Transform.QUAD,quad,Image.Resampling.BICUBIC)
                x += (w-narrow)//2
            canvas.alpha_composite(image,(x,y))
        elif kind in ('button','label'):
            draw = ImageDraw.Draw(canvas)
            if kind == 'button':
                selected = control.get('id') == '100'
                layer = Image.new('RGBA', canvas.size)
                ImageDraw.Draw(layer).rounded_rectangle((x,y,x+w,y+h),radius=6,
                    fill=(154,220,221,210) if selected else (220,238,238,30))
                canvas.alpha_composite(layer)
                draw = ImageDraw.Draw(canvas)
                color = control.findtext('focusedcolor' if selected else 'textcolor','FFFFFFFF')
            else: color = control.findtext('textcolor','FFFFFFFF')
            rgba = tuple(int(color[i:i+2],16) for i in (2,4,6,0))
            content = resolve(control.findtext('label',''));face=font(control.findtext('font'))
            # Kodi truncates long labels; never silently overflow the XML rectangle.
            while content and draw.textlength(content,font=face)>w:
                content = content[:-2].rstrip()+'…'
            align=control.findtext('align','left')
            tx = x+w/2 if align=='center' else x+w if align=='right' else x
            anchor = 'mm' if align=='center' else 'rm' if align=='right' else 'lm'
            draw.text((tx,y+h/2),content,font=face,fill=rgba,anchor=anchor)
    draw=ImageDraw.Draw(canvas)
    draw.rectangle((0,1048,1920,1080),fill=(6,12,14,255))
    draw.text((960,1064),'DESIGN PREVIEW · MOCK DATA · approximate perspective · NOT A KODI RUNTIME SCREENSHOT',
              anchor='mm',font=font('font13').font_variant(size=20),fill=(200,220,222,255))
    destination.parent.mkdir(parents=True,exist_ok=True)
    canvas.convert('RGB').save(destination)
    print(destination)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/apeture-music-shelf-design-preview.png')
    preview(parser.parse_args().output)

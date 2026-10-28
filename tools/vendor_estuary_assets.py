#!/usr/bin/env python3
"""Original Apeture assets and an XML-derived design preview, not a Kodi capture.

The original AI-generated scenic PNG is shipped byte-for-byte from assets/.
Only UI textures and the existing original mark are generated procedurally.
Artwork: CC-BY-SA-4.0 where applicable. Generator: GPL-3.0-or-later.
"""
from __future__ import annotations
import argparse
import io
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SCENIC_SOURCE = ROOT / 'assets' / 'misty-stone-bridge-v1.png'
INK = (17, 25, 27)
CYAN = (182, 229, 229)
WHITE = (244, 248, 248)
SECTIONS = ('games', 'movies', 'tv', 'music', 'files', 'settings')


def generate(output: Path):
    media = output/'media'/'apeture'
    media.mkdir(parents=True, exist_ok=True)
    resources = output/'resources'
    resources.mkdir(exist_ok=True)
    # Asset provenance is checked into the repository. No transient paths,
    # download URLs, photograph retouching, or procedural scene substitutes.
    with Image.open(SCENIC_SOURCE) as source:
        source.verify()
    shutil.copyfile(SCENIC_SOURCE, media/'misty-stone-bridge.png')
    shutil.copyfile(SCENIC_SOURCE, resources/'fanart.png')
    (resources/'fanart.jpg').unlink(missing_ok=True)

    # Separate UI scrim: keep most of the bridge untouched and darken only
    # behind the header and lower navigation. Never bake UI into the source art.
    scrim = Image.new('RGBA', (16, 1080))
    draw = ImageDraw.Draw(scrim)
    for y in range(1080):
        top = 120 * max(0, 1-y/270) ** 1.5
        lower = 178 * min(1, max(0, (y-500)/540)) ** 1.1
        draw.line((0,y,15,y), fill=(7,15,18,round(max(top,lower))))
    scrim.save(media/'home-scrim.png', optimize=True)

    band = Image.new('RGBA', (16,116))
    draw = ImageDraw.Draw(band)
    for y in range(116):
        draw.line((0,y,15,y), fill=(12,22,25,120+int(24*y/115)))
    draw.line((0,0,15,0),fill=(229,247,249,35))
    draw.line((0,115,15,115),fill=(229,247,249,30))
    band.save(media/'nav-band.png',optimize=True)

    Image.new('RGBA',(16,16)).save(media/'clear.png',optimize=True)
    focus=Image.new('RGBA',(64,64),(155,222,226,21));d=ImageDraw.Draw(focus)
    d.line((0,0,63,0),fill=CYAN+(65,),width=1)
    d.rectangle((0,61,63,63),fill=CYAN+(240,))
    focus.save(media/'nav-focus.png',optimize=True)
    for name,fill,border in [('glass-focus',(103,151,160,88),CYAN+(210,)),
                             ('glass-quiet',(15,25,28,45),(226,244,247,38))]:
        im=Image.new('RGBA',(64,64));d=ImageDraw.Draw(im)
        d.rounded_rectangle((0,0,63,63),radius=5,fill=fill,outline=border,width=1)
        im.save(media/f'{name}.png',optimize=True)
    # Existing setup dialog uses a brighter focus texture with dark focus text.
    for name,color,border in [('focus',(229,248,247,255),CYAN+(255,)),
                              ('quiet',(220,244,255,5),(220,244,255,25))]:
        im=Image.new('RGBA',(128,128));d=ImageDraw.Draw(im)
        d.rounded_rectangle((1,1,126,126),radius=24,fill=color,outline=border,width=2)
        im.save(media/f'{name}.png',optimize=True)
    mark=Image.new('RGBA',(192,192));d=ImageDraw.Draw(mark)
    d.rounded_rectangle((8,8,184,184),radius=48,outline=CYAN+(255,),width=11)
    d.arc((45,45,146,146),190,351,fill=WHITE+(255,),width=11)
    d.line((143,78,143,145),fill=WHITE+(255,),width=11)
    mark.save(media/'mark.png',optimize=True)
    icon=Image.new('RGB',(512,512),INK)
    resized=mark.resize((320,320),Image.Resampling.LANCZOS)
    icon.paste(resized,(96,96),resized)
    icon.save(resources/'icon.png',optimize=True)


def preview(skin: Path, destination: Path, selection='games', focus_action=False):
    """Evaluate this Home's actual textures, geometry, fonts and empty states.

    A static, explicitly labelled design preview, NOT a Kodi focus engine test.
    Unknown visibility expressions fail rather than inventing populated content.
    """
    from fontTools.ttLib import TTFont  # Optional preview dependency only.
    selected_id = 9100 + SECTIONS.index(selection)
    focused_id = selected_id + 200 if focus_action else selected_id
    preview_fonts = {}
    def load_font(filename, size):
        # In-memory preview-only workaround: preserve distributed font bytes.
        # Kodi uses FT_LOAD_TARGET_LIGHT; Pillow otherwise mis-hints merged Noto.
        if filename not in preview_fonts:
            font=TTFont(skin/'fonts'/filename)
            for table in ('fpgm','prep','cvt '):
                if table in font: del font[table]
            if 'glyf' in font:
                for glyph in font['glyf'].glyphs.values(): glyph.removeHinting()
            buffer=io.BytesIO();font.save(buffer)
            preview_fonts[filename]=buffer.getvalue()
        return ImageFont.truetype(io.BytesIO(preview_fonts[filename]),size)
    fonts={e.findtext('name'):(e.findtext('filename'),int(e.findtext('size')),e.findtext('style'))
           for e in ET.parse(skin/'xml/Font.xml').getroot()[0]}
    im=Image.new('RGBA',(1920,1080),INK+(255,))
    def visible(expr):
        if not expr: return True
        if '|' in expr:return any(visible(part.strip()) for part in expr.split('|'))
        if '+' in expr:return all(visible(part.strip()) for part in expr.split('+'))
        if expr.startswith('!'):return not visible(expr[1:])
        match=re.fullmatch(r'Control.HasFocus\((\d+)\)',expr)
        if match:return int(match[1])==focused_id
        if expr in ('Player.HasMedia','System.AddonIsEnabled(plugin.games.apeture)',
                    'Library.HasContent(music)','Library.HasContent(movies)',
                    'Library.HasContent(tvshows)'):return False
        raise ValueError(f'Preview does not evaluate Kodi condition: {expr}')
    def texture(node,w,h):
        asset=Image.open(skin/'media'/node.text).convert('RGBA')
        border=int(node.get('border','0'))
        if not border:return asset.resize((w,h),Image.Resampling.LANCZOS)
        # Kodi's border attribute is nine-slice, not a stretched stroke.
        result=Image.new('RGBA',(w,h))
        sx=(0,border,asset.width-border,asset.width)
        sy=(0,border,asset.height-border,asset.height)
        dx=(0,border,w-border,w);dy=(0,border,h-border,h)
        for row in range(3):
            for col in range(3):
                part=asset.crop((sx[col],sy[row],sx[col+1],sy[row+1]))
                part=part.resize((dx[col+1]-dx[col],dy[row+1]-dy[row]),Image.Resampling.LANCZOS)
                result.paste(part,(dx[col],dy[row]))
        return result
    def draw_control(c):
        if not visible(c.findtext('visible')):return
        kind=c.get('type')
        if kind=='group':
            for child in c.findall('control'):draw_control(child)
            return
        x,y,w,h=[int(c.findtext(k,'0')) for k in ('left','top','width','height')]
        if kind=='image':
            im.alpha_composite(texture(c.find('texture'),w,h),(x,y));return
        if kind not in ('label','textbox','button'):return
        focused=c.get('id')==str(focused_id)
        if kind=='button':
            im.alpha_composite(texture(c.find('texturefocus' if focused else 'texturenofocus'),w,h),(x,y))
        value=c.findtext('label','').replace('[CR]','\n')
        if '$INFO[System.Time]' in value:value='20:48'
        if '$INFO[System.Date]' in value:value='Wednesday, 28 October'
        if '$INFO[' in value:return
        color=c.findtext('focusedcolor') if focused else c.findtext('textcolor','FFF4F8F8')
        color=tuple(int(color[i:i+2],16) for i in (2,4,6))+(int(color[:2],16),)
        file,size,style=fonts.get(c.findtext('font'),('NotoSans-Regular.ttf',28,None))
        font=load_font(file,size);draw=ImageDraw.Draw(im)
        bbox=draw.multiline_textbbox((0,0),value,font=font,spacing=7)
        tx=x+int(c.findtext('textoffsetx','0'))
        if c.findtext('align')=='right':tx=x+w-(bbox[2]-bbox[0])
        elif c.findtext('align')=='center':tx=x+(w-(bbox[2]-bbox[0]))/2
        ty=y+(h-(bbox[3]-bbox[1]))/2-bbox[1] if kind!='textbox' else y
        shadow=c.findtext('shadowcolor','00000000')
        if shadow!='00000000':
            # Shadow strength is from the actual XML (not additional mockup UI).
            layer=Image.new('RGBA',im.size);ld=ImageDraw.Draw(layer)
            ld.multiline_text((tx+1,ty+2),value,font=font,fill=(0,0,0,int(shadow[:2],16)),spacing=7)
            im.alpha_composite(layer);draw=ImageDraw.Draw(im)
        draw.multiline_text((tx,ty),value,font=font,fill=color,spacing=7,stroke_width=1 if style=='bold' else 0)
    for c in ET.parse(skin/'xml/Home.xml').getroot().findall('./controls/control'):draw_control(c)
    draw=ImageDraw.Draw(im)
    draw.rectangle((0,1040,1920,1080),fill=(7,15,18,255))
    font=load_font('NotoSans-Regular.ttf',19)
    draw.text((96,1047),'APETURE  /  DESIGN PREVIEW — actual XML and assets; empty-library state; not a Kodi runtime screenshot',font=font,fill=(174,191,193,255))
    destination.parent.mkdir(parents=True,exist_ok=True)
    im.convert('RGB').save(destination,optimize=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='Full materialized skin directory')
    parser.add_argument('--preview',type=Path,help='Also render a labelled layout design preview')
    parser.add_argument('--selection',choices=SECTIONS,default='games',help='Preview selected section (empty libraries, no companion)')
    parser.add_argument('--focus-action',action='store_true',help='Preview focus on the selected section action')
    args=parser.parse_args();generate(args.output)
    if args.preview:preview(args.output,args.preview,args.selection,args.focus_action)

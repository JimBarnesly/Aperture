#!/usr/bin/env python3
"""Original Apeture artwork and a layout-derived design preview (not a Kodi capture).

Requires Pillow. No third-party images, device photos or proprietary logo art.
Artwork: CC-BY-SA-4.0. Generator code: GPL-3.0-or-later.
"""
from __future__ import annotations
import argparse
import io
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFilter, ImageFont

INK = (6, 21, 34)
CYAN = (154, 248, 234)
WHITE = (231, 239, 245)


def ambient():
    """Low frequency illumination, supersampled to a modest full-HD texture."""
    w, h = 960, 540
    im = Image.new('RGB', (w, h))
    data = []
    for y in range(h):
        for x in range(w):
            a = math.exp(-((x-750)/300)**2-((y-190)/215)**2)
            b = math.exp(-((x-360)/400)**2-((y-510)/200)**2)
            rim = math.exp(-((x-940)/140)**2-((y-490)/160)**2)
            data.append((int(6+4*a+2*b), int(16+24*a+8*b+9*rim), int(28+36*a+12*b+10*rim)))
    im.putdata(data)
    im = im.resize((1920, 1080), Image.Resampling.BICUBIC)
    # Delicate architectural light arcs: original geometry, no scanlines or pixel art.
    layer = Image.new('RGBA', im.size)
    d = ImageDraw.Draw(layer)
    for i in range(5):
        d.arc((1090+i*24, 125-i*30, 2110+i*24, 1145-i*30), 135, 258, fill=(106, 214, 225, 7-i), width=2)
    return Image.alpha_composite(im.convert('RGBA'), layer).convert('RGB')


def emblem(kind):
    """A family of soft luminous pictograms on the same transparent artboard."""
    s = 2
    im = Image.new('RGBA', (520*s, 420*s))
    glow = Image.new('RGBA', im.size)
    d = ImageDraw.Draw(glow)
    d.ellipse((95*s, 80*s, 460*s, 370*s), fill=(54, 194, 217, 30))
    im = Image.alpha_composite(im, glow.filter(ImageFilter.GaussianBlur(35*s)))
    d = ImageDraw.Draw(im)
    def box(b): return tuple(int(v*s) for v in b)
    def line(p, fill=CYAN+(230,), width=3): d.line([(int(x*s),int(y*s)) for x,y in p], fill=fill, width=width*s, joint='curve')
    def ell(b, fill=None, outline=CYAN+(220,), width=3): d.ellipse(box(b), fill=fill, outline=outline, width=width*s)
    def rect(b, radius=18, fill=(17,53,70,255), outline=CYAN+(210,), width=3): d.rounded_rectangle(box(b),radius*s,fill,outline,width*s)
    # Shared quiet orbital ring, intentionally secondary to the artwork.
    d.arc(box((86,59,474,383)), 212, 336, fill=(101,185,207,48), width=2*s)
    d.arc(box((68,43,490,399)), 28, 114, fill=(101,185,207,42), width=2*s)
    if kind == 'gamepad':
        # Original stylised controller silhouette, with no branded button layout labels.
        points=[(150,144),(183,125),(368,125),(401,144),(432,279),(418,307),(391,313),(343,262),(214,262),(164,313),(136,307),(123,280)]
        d.polygon([(x*s,y*s) for x,y in points], fill=(16,48,65,255))
        line(points+[points[0]], width=3)
        line([(177,161),(177,214)],width=10);line([(151,187),(204,187)],width=10)
        for x,y in [(354,168),(380,193),(329,193),(354,219)]:
            ell((x-8,y-8,x+8,y+8), fill=(124,232,228,190),outline=None)
        ell((224,221,263,260),fill=(9,28,43,255));ell((290,221,329,260),fill=(9,28,43,255))
        line([(265,174),(281,174)],fill=(197,233,239,170),width=3)
        line([(188,132),(363,132)],fill=(228,255,253,100),width=2)
    elif kind == 'film':
        rect((140,120,424,298),12)
        for x in range(157,410,42):
            rect((x,132,x+22,147),3,fill=(91,177,196,100),outline=None)
            rect((x,271,x+22,286),3,fill=(91,177,196,100),outline=None)
        d.polygon([(251*s,173*s),(251*s,245*s),(312*s,209*s)],fill=CYAN+(215,))
    elif kind == 'tv':
        rect((131,121,430,291),20);rect((148,137,413,274),12,fill=(8,28,44,255),outline=(99,175,197,130),width=1)
        line([(258,292),(258,316),(307,316),(307,292)],width=3)
        line([(227,318),(337,318)],width=4)
        line([(203,211),(233,211),(248,187),(268,237),(289,174),(314,221),(355,221)],width=4)
    elif kind == 'music':
        ell((134,73,432,371),fill=(11,35,51,255))
        for inset in (12,21,31,45,61):
            ell((134+inset,73+inset,432-inset,371-inset),outline=(91,166,186,70),width=1)
        ell((234,173,332,271),fill=(42,118,137,255),outline=(174,249,238,230),width=2)
        ell((273,212,293,232),fill=(4,20,31,255),outline=None)
        d.arc(box((153,91,413,352)),223,294,fill=(220,252,251,160),width=3*s)
    elif kind == 'folder':
        rect((133,139,426,305),18,fill=(15,45,61,255))
        rect((139,116,264,160),12,fill=(28,75,91,255))
        rect((123,156,438,314),18,fill=(18,57,74,255))
        line([(149,185),(411,185)],fill=(190,247,242,150),width=2)
        line([(253,234),(278,258),(319,218)],width=5)
    else:
        ell((161,100,409,348),fill=(13,42,58,255),width=3)
        ell((235,174,335,274),fill=(6,25,40,255),width=4)
        for i in range(8):
            a=math.pi*i/4
            x,y=285+124*math.cos(a),224+124*math.sin(a)
            line([(x-13*math.cos(a),y-13*math.sin(a)),(x+15*math.cos(a),y+15*math.sin(a))],width=7)
    return im.resize((520,420), Image.Resampling.LANCZOS)


def generate(output: Path):
    media = output/'media'/'apeture'
    media.mkdir(parents=True,exist_ok=True)
    ambient().save(media/'ambient.png',optimize=True)
    for kind in ('gamepad','film','tv','music','folder','settings'):
        emblem(kind).save(media/f'{kind}.png',optimize=True)
    for name,color,border in [('focus',(229,248,247,255),(154,248,234,255)),('quiet',(220,244,255,5),(220,244,255,10))]:
        im=Image.new('RGBA',(128,128));d=ImageDraw.Draw(im)
        d.rounded_rectangle((1,1,126,126),radius=24,fill=color,outline=border,width=2)
        im.save(media/f'{name}.png',optimize=True)
    mark=Image.new('RGBA',(192,192));d=ImageDraw.Draw(mark)
    d.rounded_rectangle((8,8,184,184),radius=48,outline=CYAN+(255,),width=11)
    d.arc((45,45,146,146),190,351,fill=WHITE+(255,),width=11)
    d.line((143,78,143,145),fill=WHITE+(255,),width=11)
    mark.save(media/'mark.png',optimize=True)
    resources=output/'resources';resources.mkdir(exist_ok=True)
    icon=Image.new('RGB',(512,512),INK)
    icon.paste(mark.resize((320,320),Image.Resampling.LANCZOS),(96,96),mark.resize((320,320),Image.Resampling.LANCZOS))
    icon.save(resources/'icon.png',optimize=True)
    bg=Image.open(media/'ambient.png').resize((1280,720))
    bg.paste(emblem('gamepad').resize((700,565)),(580,70),emblem('gamepad').resize((700,565)))
    # Fanart is original background art, not a screenshot of the product.
    bg.convert('RGB').save(resources/'fanart.jpg',quality=90)


def preview(skin: Path, destination: Path):
    """Small static XML evaluator: validates actual art, geometry and fonts.

    It does not simulate Kodi's focus engine, conditional includes or animation.
    Those must be validated on Kodi. This explicit label survives every export.
    """
    from fontTools.ttLib import TTFont  # Optional preview dependency only.
    preview_fonts = {}
    def load_font(filename, size):
        # Kodi uses FT_LOAD_TARGET_LIGHT, while Pillow's default bytecode hinting
        # distorts this upstream merged Noto font. Use identical outlines with
        # hints disabled in memory; never modify the distributed font bytes.
        if filename not in preview_fonts:
            font = TTFont(skin/'fonts'/filename)
            for table in ('fpgm', 'prep', 'cvt '):
                if table in font: del font[table]
            if 'glyf' in font:
                for glyph in font['glyf'].glyphs.values(): glyph.removeHinting()
            buffer = io.BytesIO(); font.save(buffer)
            preview_fonts[filename] = buffer.getvalue()
        return ImageFont.truetype(io.BytesIO(preview_fonts[filename]), size)
    fonts={e.findtext('name'):(e.findtext('filename'),int(e.findtext('size')),e.findtext('style')) for e in ET.parse(skin/'xml/Font.xml').getroot()[0]}
    im=Image.new('RGBA',(1920,1080),INK+(255,));draw=ImageDraw.Draw(im)
    def visible(expr):
        if not expr: return True
        if 'Player.HasMedia' in expr: return False
        if 'System.AddonIsEnabled' in expr: return expr.startswith('!')
        if 'Control.HasFocus' in expr: return 'Control.HasFocus(9100)' in expr
        return True
    def draw_control(c):
        nonlocal draw,im
        if not visible(c.findtext('visible')): return
        kind=c.get('type')
        if kind=='group':
            for child in c.findall('control'):draw_control(child)
            return
        x,y,w,h=[int(c.findtext(k,'0')) for k in ('left','top','width','height')]
        if kind=='image':
            source=skin/'media'/c.findtext('texture')
            asset=Image.open(source).convert('RGBA').resize((w,h),Image.Resampling.LANCZOS)
            im.alpha_composite(asset,(x,y));draw=ImageDraw.Draw(im);return
        if kind not in ('label','textbox','button'):return
        focused=c.get('id')=='9100'
        if kind=='button':
            fill=(229,248,247,255) if focused else (10,30,46,130)
            outline=CYAN+(255,) if focused else (44,74,93,100)
            draw.rounded_rectangle((x,y,x+w,y+h),radius=24,fill=fill,outline=outline,width=2 if focused else 1)
        value=c.findtext('label','').replace('[CR]', '\n')
        if '$INFO[System.Time]' in value:value='20:48'
        if '$INFO[System.Date]' in value:value='Wednesday, 28 October'
        if '$INFO[' in value:return
        color=c.findtext('focusedcolor') if focused else c.findtext('textcolor','FFE7EFF5')
        color=tuple(int(color[i:i+2],16) for i in (2,4,6))+(255,)
        file,size,style=fonts.get(c.findtext('font'),('NotoSans-Regular.ttf',28,None))
        font=load_font(file,size)
        tx=x+int(c.findtext('textoffsetx','0'))
        ty=y+(h-size*1.35)/2 if kind!='textbox' else y
        if c.findtext('align')=='right':tx=x+w-draw.textlength(value,font=font)
        # Kodi's Noto font uses synthetic bold; Pillow's stroke approximates its weight.
        draw.multiline_text((tx,ty),value,font=font,fill=color,spacing=7,stroke_width=1 if style=='bold' else 0)
    for c in ET.parse(skin/'xml/Home.xml').getroot().findall('./controls/control'):draw_control(c)
    draw.rectangle((0,1040,1920,1080),fill=(3,12,20,255))
    f=load_font('NotoSans-Regular.ttf',19)
    draw.text((96,1047),'APETURE 0.1  /  DESIGN PREVIEW — XML layout and original assets, not a Kodi runtime screenshot',font=f,fill=(142,173,192,255))
    destination.parent.mkdir(parents=True,exist_ok=True)
    im.convert('RGB').save(destination,optimize=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='Full materialized skin directory')
    parser.add_argument('--preview',type=Path,help='Also render a labelled layout design preview')
    args=parser.parse_args();generate(args.output)
    if args.preview:preview(args.output,args.preview)

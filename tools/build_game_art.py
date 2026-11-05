#!/usr/bin/env python3
"""Build original console illustrations for the Aperture system carousel.

SPDX-License-Identifier: GPL-3.0-or-later
The geometry is original, not traced or copied from a theme or product photo.
SVG sources are generated alongside runtime PNGs. Inkscape is only required to
regenerate artwork; Kodi loads the checked-in PNG files without dependencies.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'skin/media/aperture/games/systems'
SOURCE = ROOT / 'skin/artwork/games'
COLORS = {
 'nes':('#cf5847','#643b41'), 'snes':('#9e8bdd','#4c436b'),
 'gb':('#b4c782','#4a6252'), 'gbc':('#56b3b2','#335861'),
 'gba':('#8f93ea','#4d4b79'), 'n64':('#5ba9b0','#254c58'),
 'megadrive':('#5989ce','#293e66'), 'mastersystem':('#c85a57','#56353f'),
 'gamegear':('#5b92c9','#324e68'), 'pcengine':('#dfaf74','#655343'),
 'atari2600':('#d7a76c','#695044'), 'psx':('#6db8b6','#36545d'),
 'arcade':('#bc7ca9','#5e3b60'), 'default':('#708d9b','#344951'),
 'utility-back':('#708d9b','#344951'), 'utility-settings':('#708d9b','#344951'),
 'utility-help':('#708d9b','#344951'), 'utility-refresh':('#708d9b','#344951'),
}

def rect(x,y,w,h,fill,rx=0,**kw):
 return '<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s" %s/>'%(x,y,w,h,rx,fill,' '.join('%s="%s"'%(k.replace('_','-'),v) for k,v in kw.items()))
def path(d,fill,stroke=None,width=1):
 return '<path d="%s" fill="%s"%s/>'%(d,fill,(' stroke="%s" stroke-width="%s" stroke-linejoin="round" stroke-linecap="round"'%(stroke,width)) if stroke else '')
def circle(x,y,r,fill,stroke=None,width=1):
 return '<circle cx="%s" cy="%s" r="%s" fill="%s"%s/>'%(x,y,r,fill,(' stroke="%s" stroke-width="%s"'%(stroke,width)) if stroke else '')
def line(x1,y1,x2,y2,color,width=2):
 return path('M %s %s L %s %s'%(x1,y1,x2,y2),'none',color,width)
def group(body,transform): return '<g transform="%s">%s</g>'%(transform,body)
def dpad(x,y,size=18):
 return path(f'M {x-size} {y-3*size} h {size*2} v {size*2} h {size*2} v {size*2} h {-size*2} v {size*2} h {-size*2} v {-size*2} h {-size*2} v {-size*2} h {size*2} z','#202930','#59636a',2)+circle(x,y,size*.55,'#313a42')
def small_buttons(x,y,c1='#ac284e',c2='#ac284e'):
 return circle(x,y,16,c1,'#31333b',4)+circle(x+44,y-23,16,c2,'#31333b',4)
def controller(kind='snes'):
 # Controller drawings use their own characteristic silhouettes and layouts.
 if kind=='nes':
  return rect(0,0,230,94,'#b9bfbe',10)+rect(9,12,212,70,'#242d32',6)+dpad(47,47,8)+small_buttons(170,54,'#db4245','#db4245')+rect(88,54,27,8,'#747d7e',4)+rect(121,54,27,8,'#747d7e',4)
 if kind=='psx':
  body=path('M 26 10 Q 2 12 0 44 L -14 103 Q -12 126 11 114 L 53 77 H 142 L 184 114 Q 209 126 205 103 L 192 44 Q 190 12 168 10 Z','#c8cecb','#737d80',3)
  return body+circle(40,45,32,'#a1aaac')+dpad(40,45,7)+circle(150,45,31,'#a1aaac')+circle(150,29,7,'#69a5a8')+circle(166,45,7,'#ce777f')+circle(150,61,7,'#98a7d6')+circle(134,45,7,'#b88ba7')+rect(78,43,16,6,'#687278',3)+path('M 109 40 l 12 6 -12 6 z','#687278')
 if kind=='n64':
  body=path('M 4 12 Q 30 -8 61 4 L 105 16 L 151 4 Q 183 -8 205 12 L 230 100 Q 236 127 213 131 Q 193 133 179 82 L 133 88 L 125 145 Q 109 171 90 145 L 80 88 L 36 82 Q 19 133 0 131 Q -20 127 -17 100 Z','#8b9398','#3b4850',3)
  return body+dpad(35,38,7)+circle(105,51,21,'#56636b')+circle(105,51,12,'#c2c9ca')+circle(164,63,10,'#4a9d6d')+circle(186,47,10,'#5578bc')+''.join(circle(x,y,5,'#d5b552') for x,y in [(160,26),(173,14),(185,26),(173,38)])+circle(105,16,5,'#c05b62')
 if kind=='megadrive':
  return path('M 21 3 Q -3 13 1 49 L 13 92 Q 20 108 35 93 L 65 69 H 155 L 181 93 Q 195 108 204 92 L 216 49 Q 220 13 193 3 Z','#29333c','#65727c',3)+dpad(48,40,8)+''.join(circle(x,y,10,'#222a32','#6b7884',2) for x,y in [(146,52),(173,40),(195,27)])+rect(100,27,27,8,'#a39b8a',4)
 return path('M 46 0 H 176 A 48 48 0 0 1 176 96 H 46 A 48 48 0 0 1 46 0 Z','#c9cecc','#7f8a8b',3)+circle(41,48,32,'#b1babb')+dpad(41,48,8)+small_buttons(167,59,'#7b70a8','#a9a0d2')+small_buttons(144,36,'#8276b6','#9c91cc')+rect(88,49,22,7,'#636e76',3)+rect(116,49,22,7,'#636e76',3)

def console(identifier):
 if identifier=='nes':
  vents=''.join(rect(404+i*8,166,3,95,'#6d777d',1) for i in range(8))
  body=path('M 105 198 L 166 121 H 446 L 503 198 Z','#dde0d7')+path('M 105 198 H 503 V 338 H 105 Z','#a7b0af')+rect(105,198,398,76,'#d3d7cd')+rect(250,160,147,74,'#b2bbb9',4)+line(259,226,388,226,'#69797d',4)+rect(395,198,108,140,'#28333a')+vents+rect(133,296,52,17,'#5c686c',2)+rect(194,296,46,17,'#5c686c',2)+rect(131,299,7,9,'#dd695d')+rect(415,299,31,16,'#121c23',3)+rect(458,299,31,16,'#121c23',3)
  return body+group(controller('nes'),'translate(209 388) rotate(-10)')+path('M 435 313 C 545 357 124 355 249 385','none','#18232b',5)
 if identifier=='snes':
  return path('M 139 194 L 182 126 H 451 L 487 194 V 327 Q 481 354 452 358 H 168 Q 139 354 139 327 Z','#bbc5c5','#dce2df',3)+rect(181,143,265,135,'#d4dad4',22)+path('M 238 174 Q 310 152 385 174 L 385 192 H 238 Z','#26333b')+rect(177,262,88,26,'#8a79b7',7)+rect(358,262,88,26,'#a89ccf',7)+rect(283,263,56,24,'#9aa7ad',4)+rect(182,316,72,23,'#24313a',8)+rect(368,316,72,23,'#24313a',8)+group(controller(),'translate(192 407) rotate(-12)')
 if identifier in ('gb','gbc'):
  color='#c5c9bc' if identifier=='gb' else '#50a5ad'
  body=path('M 209 84 H 421 Q 446 84 446 112 V 434 Q 444 484 393 484 H 209 Q 185 484 185 460 V 111 Q 185 84 209 84 Z',color,'#d5ded4' if identifier=='gb' else '#81c5c9',3)+path('M 214 115 H 416 V 295 H 214 Z','#727d80')+rect(240,141,150,126,'#8fa36d',3)+rect(251,151,128,104,'#a7b779',2)+line(226,128,404,128,'#b9c4bd',3)+circle(225,192,4,'#c86c68')+dpad(242,348,11)+small_buttons(365,352)+rect(278,417,37,9,'#65737b',5)+rect(330,417,37,9,'#65737b',5)+''.join(line(369+i*11,442,369+i*11,465,'#667b7f',4) for i in range(5))
  if identifier=='gbc': body+=circle(317,88,5,'#448c98')
  return group(body,'rotate(9 320 280)')
 if identifier in ('gba','gamegear'):
  gba=identifier=='gba'
  color='#8078bb' if gba else '#2d3948'
  body=path('M 134 158 Q 100 151 94 198 L 86 336 Q 94 385 139 388 L 466 388 Q 513 385 522 336 L 516 198 Q 508 151 478 158 Z',color,'#aaa6d7' if gba else '#667b8e',3)+rect(189,181,229,182,'#242f3a',12)+rect(211,200,185,140,'#719ea4',5)+rect(221,210,165,120,'#96c4c4',3)+dpad(143,265,10)+small_buttons(461,269,'#bbb5d8' if gba else '#5d7085','#bbb5d8' if gba else '#5d7085')+rect(132,325,25,7,'#c1bbdb',4)+rect(456,325,25,7,'#c1bbdb',4)+circle(430,200,4,'#76cfaf')
  if not gba: body+=''.join(line(263+i*16,369,271+i*16,381,'#172630',4) for i in range(6))
  return group(body,'rotate(-9 310 280)')
 if identifier=='n64':
  return path('M 126 201 Q 149 139 220 137 H 420 Q 487 140 505 201 L 515 323 Q 506 357 465 361 H 166 Q 121 354 116 323 Z','#303f46','#637780',3)+path('M 181 183 Q 320 146 451 183 L 447 216 H 184 Z','#131f29')+path('M 205 188 Q 320 172 429 188','none','#75828a',5)+rect(148,245,36,13,'#63737b',4)+rect(437,245,36,13,'#6c7c83',4)+rect(279,255,68,40,'#172630',8)+''.join(rect(x,322,52,23,'#13222a',8)+circle(x+26,333,6,'#65747b') for x in [150,240,330,420])+group(controller('n64'),'translate(229 386) scale(.91) rotate(-8)')
 if identifier=='psx':
  vents=''.join(rect(144+i*8,185,3,115,'#919d9f',1) for i in range(8))+''.join(rect(417+i*8,185,3,115,'#919d9f',1) for i in range(8))
  return path('M 141 156 H 461 Q 480 156 484 177 L 499 321 Q 502 348 476 352 H 127 Q 105 348 109 321 L 122 177 Q 125 156 141 156 Z','#c6cecb','#edf0e5',3)+vents+circle(302,239,102,'#d6dcd7','#98a4a7',4)+circle(302,239,92,'#cad3cf','#bac4c0',2)+rect(266,168,73,9,'#9ca9a8',3)+circle(171,304,16,'#b7c3bf','#758887',2)+circle(436,304,16,'#b7c3bf','#758887',2)+rect(159,333,111,26,'#7e8d91',4)+rect(337,333,111,26,'#7e8d91',4)+rect(168,339,94,11,'#35434a',3)+rect(345,339,94,11,'#35434a',3)+group(controller('psx'),'translate(230 399) rotate(-10)')
 if identifier=='megadrive':
  return path('M 148 176 Q 179 140 219 143 H 436 L 494 189 V 320 Q 491 346 466 351 H 140 Q 111 345 111 320 V 210 Z','#29343e','#627481',3)+circle(312,221,96,'#162731','#71808b',5)+circle(312,221,76,'#24333d','#374d5b',3)+rect(230,198,162,19,'#131e28',5)+rect(139,277,51,17,'#3c4f5a',5)+rect(420,277,51,17,'#49708b',5)+rect(163,326,72,20,'#111f29',7)+rect(362,326,72,20,'#111f29',7)+group(controller('megadrive'),'translate(223 401) rotate(-10)')
 if identifier=='mastersystem':
  return path('M 122 185 L 159 145 H 475 L 507 185 V 321 H 122 Z','#263039','#5a6872',3)+rect(122,221,385,24,'#c15052')+path('M 167 185 H 394 L 365 218 H 167 Z','#4c5a63')+rect(198,162,207,15,'#14242d',3)+rect(146,274,76,21,'#55626a',4)+rect(430,277,23,14,'#b05b54')+rect(466,277,23,14,'#a5adb0')+group(rect(0,0,179,96,'#343f47',7)+rect(11,10,157,75,'#29343a',5)+dpad(43,47,8)+small_buttons(115,59,'#b45159','#b45159'),'translate(235 395) rotate(-9)')
 if identifier=='pcengine':
  return path('M 167 163 H 424 L 461 207 V 335 H 132 V 207 Z','#e8e1c9','#f7eed8',3)+rect(153,208,286,104,'#c8cbbd',6)+rect(198,175,198,22,'#413e3a',5)+rect(205,228,183,54,'#e2dcca',3)+line(223,260,367,260,'#bd9271',3)+rect(157,318,63,12,'#bc664e',3)+rect(385,318,55,12,'#535d5c',3)+group(rect(0,0,226,94,'#ded9c6',8)+rect(8,8,210,76,'#3a403f',5)+dpad(45,44,8)+small_buttons(165,55,'#dca057','#dca057')+rect(90,51,20,7,'#b1b3a5',3)+rect(119,51,20,7,'#b1b3a5',3),'translate(193 405) rotate(-9)')
 if identifier=='atari2600':
  vents=''.join(rect(148+i*10,183,4,102,'#0f2027',1) for i in range(31))
  return path('M 148 180 L 182 136 H 451 L 487 180 V 330 H 116 V 206 Z','#303c41','#687778',3)+rect(116,289,371,42,'#9c714c')+''.join(line(123,y,483,y,'#6d4c36',2) for y in range(296,329,6))+vents+rect(232,155,151,25,'#111f28',4)+''.join(rect(x,259,11,20,'#b5c0b8',2) for x in [158,196,413,451])+group(path('M 8 46 H 132 L 153 96 H -7 Z','#26343c','#697b81',2)+rect(63,0,18,67,'#25333c',7)+circle(72,0,25,'#344650','#75868c',2)+circle(25,66,12,'#ca6655'),'translate(240 407) rotate(-9)')
 if identifier=='arcade':
  return path('M 191 80 H 397 L 435 146 L 414 307 L 454 345 L 433 504 H 177 L 154 345 L 191 307 L 168 146 Z','#394552','#75828c',3)+path('M 397 80 L 451 112 L 479 179 L 459 323 L 494 362 L 475 504 H 433 L 454 345 L 414 307 L 435 146 Z','#252f3d')+path('M 184 110 H 414 L 427 144 H 173 Z','#b16f9b')+rect(194,169,209,135,'#111f2b',10)+rect(209,184,180,105,'#53828f',4)+path('M 209 270 L 249 230 L 283 252 L 334 202 L 389 250 V 289 H 209 Z','#80b2ab')+path('M 191 309 H 413 L 446 347 H 162 Z','#d0b3c4')+circle(234,328,16,'#444958')+rect(230,300,8,28,'#ccd2cb',2)+circle(234,297,12,'#b45b7c')+''.join(circle(x,y,8,c) for x,y,c in [(343,326,'#c26b88'),(369,320,'#8e9dca'),(395,326,'#d9b86f')])+rect(271,378,74,55,'#192b38',4)+rect(287,390,42,5,'#bac4c2',2)+rect(181,478,248,12,'#172835')
 if identifier.startswith('utility-'):
  name=identifier.removeprefix('utility-')
  if name=='back': icon=path('M 368 171 L 256 280 L 368 389 M 263 280 H 448','none','#d6e4df',22)
  elif name=='help': icon=circle(320,280,112,'none','#d6e4df',11)+path('M 279 235 C 279 184 364 184 366 235 C 366 274 320 267 320 310','none','#d6e4df',14)+circle(320,346,9,'#d6e4df')
  elif name=='refresh': icon=path('M 226 226 A 110 110 0 1 1 213 316 M 226 226 V 164 M 226 226 H 288','none','#d6e4df',16)
  else: icon=path('M 224 191 H 416 M 224 280 H 416 M 224 369 H 416','none','#d6e4df',12)+circle(281,191,22,'#829ea8','#d6e4df',8)+circle(371,280,22,'#829ea8','#d6e4df',8)+circle(300,369,22,'#829ea8','#d6e4df',8)
  return icon
 return group(controller('snes'),'translate(152 225) scale(1.5)')

def svg(identifier):
 accent,shade=COLORS[identifier]
 return f'''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="560" viewBox="0 0 640 560">
<defs><linearGradient id="back" x2=".9" y2="1"><stop stop-color="{shade}"/><stop offset="1" stop-color="#14222c"/></linearGradient><radialGradient id="glow"><stop stop-color="{accent}" stop-opacity=".35"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient><linearGradient id="fade" x2="0" y2="1"><stop offset="0" stop-color="#14212a" stop-opacity="0"/><stop offset="1" stop-color="#14212a" stop-opacity=".8"/></linearGradient></defs>
<path d="M 0 0 H 640 V 514 L 590 560 H 0 Z" fill="url(#back)"/>
<circle cx="352" cy="259" r="300" fill="url(#glow)"/>
<g fill="none" stroke="{accent}" stroke-opacity=".17"><circle cx="322" cy="268" r="223" stroke-width="1"/><circle cx="322" cy="268" r="198" stroke-width="1"/><path d="M 0 444 L 640 65 M 0 485 L 640 106" stroke-width="1"/></g>
<path d="M 0 0 H 640 V 5 H 0 Z" fill="{accent}"/>
<ellipse cx="321" cy="499" rx="184" ry="18" fill="#0a151c" opacity=".38"/>
{console(identifier)}
<path d="M 0 500 H 640 V 560 H 0 Z" fill="url(#fade)"/>
</svg>'''

def build(render=True):
 OUT.mkdir(parents=True,exist_ok=True); SOURCE.mkdir(parents=True,exist_ok=True)
 for name in COLORS:
  file=SOURCE/(name+'.svg'); file.write_text(svg(name)+'\n')
  if render:
   subprocess.run(['inkscape',str(file),'--export-type=png','--export-filename='+str(OUT/(name+'.png'))],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 # Original tiny UI textures are separate from the device illustration assets.
 for name,body in {
  'carousel-line': '<rect width="640" height="560" fill="#8de3d4"/>',
  'carousel-backdrop':'<rect width="640" height="560" fill="#101d26"/>',
 }.items():
  file=SOURCE/(name+'.svg'); file.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="640" height="560" viewBox="0 0 640 560">'+body+'</svg>\n')
  if render: subprocess.run(['inkscape',str(file),'--export-type=png','--export-filename='+str(OUT/(name+'.png'))],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--svg-only',action='store_true'); args=parser.parse_args(); build(not args.svg_only)

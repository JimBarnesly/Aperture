"""Generate original code-native UI textures and the Aperture Home layout."""
from pathlib import Path
from PIL import Image, ImageDraw
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1]
MEDIA=ROOT/'skin/media/aperture';MEDIA.mkdir(parents=True,exist_ok=True)
# These are original UI primitives, not edits of the reference photograph.
for name,fill,outline in [('card',(247,250,248,226),(255,255,255,155)),('card-focus',(252,255,254,249),(82,211,228,255)),('power',(17,36,40,200),(213,236,237,70)),('power-focus',(241,254,255,250),(82,211,228,255))]:
 im=Image.new('RGBA',(360,156),(0,0,0,0));d=ImageDraw.Draw(im)
 d.rounded_rectangle((3,4,356,151),radius=22,fill=fill,outline=outline,width=4 if 'focus' in name else 2)
 im.save(MEDIA/(name+'.png'))
im=Image.new('RGBA',(920,1080),(0,0,0,0));d=ImageDraw.Draw(im)
for x in range(920):
 alpha=235 if x<635 else max(0,round(235*(1-(x-635)/285)**1.5))
 d.line((x,0,x,1080),fill=(13,27,31,alpha))
im.save(MEDIA/'blade.png')
for name in ('music','movies','tv','games','files','settings'):
 im=Image.new('RGBA',(96,96),(0,0,0,0));d=ImageDraw.Draw(im);c=(30,85,100,255);w=5
 if name=='music':
  d.line((40,64,40,24,70,17,70,57),fill=c,width=w);d.line((41,34,69,27),fill=c,width=w);d.ellipse((21,58,41,74),fill=c);d.ellipse((51,51,71,67),fill=c)
 elif name=='movies':
  d.rounded_rectangle((18,22,78,76),radius=5,outline=c,width=w)
  for y in (30,47,64):d.rectangle((24,y,29,y+5),fill=c);d.rectangle((67,y,72,y+5),fill=c)
  d.polygon((41,35,41,62,61,48),fill=c)
 elif name=='tv':
  d.rounded_rectangle((14,25,82,69),radius=8,outline=c,width=w);d.line((35,79,61,79),fill=c,width=w);d.line((48,70,48,79),fill=c,width=w)
 elif name=='games':
  d.rounded_rectangle((11,29,85,67),radius=17,outline=c,width=w);d.line((29,38,29,57),fill=c,width=w);d.line((20,47,38,47),fill=c,width=w);d.ellipse((61,38,68,45),fill=c);d.ellipse((71,49,78,56),fill=c)
 elif name=='files':
  d.polygon((16,28,40,28,47,36,80,36,80,73,16,73),outline=c,width=w);d.line((17,43,79,43),fill=c,width=w)
 else:
  d.ellipse((26,26,70,70),outline=c,width=7);d.ellipse((40,40,56,56),outline=c,width=4)
  for a,b in [((45,14),(51,28)),((45,68),(51,82)),((14,45),(28,51)),((68,45),(82,51))]:d.rectangle((*a,*b),fill=c)
 im.save(MEDIA/(name+'.png'))

def node(tag,text=None,**attrs):
 e=E.Element(tag,{k:str(v) for k,v in attrs.items()});e.text=text;return e

def control(parent,typ,id=None,**props):
 e=E.SubElement(parent,'control',{'type':typ,**({'id':str(id)} if id else {})})
 for k,v in props.items():E.SubElement(e,k).text=str(v)
 return e

def animation(parent,effect,start,end,time,delay=0):
 E.SubElement(parent,'animation',{'effect':effect,'start':str(start),'end':str(end),'time':str(time),'delay':str(delay),'tween':'cubic','easing':'out'}).text='WindowOpen'
win=node('window');E.SubElement(win,'defaultcontrol',{'always':'false'}).text='103';E.SubElement(win,'backgroundcolor').text='FF14252C';cs=E.SubElement(win,'controls')
control(cs,'image',left=0,top=0,width=1920,height=1080,texture='aperture/bridge.png',aspectratio='scale')
blade=control(cs,'group');animation(blade,'slide','-920,0','0,0',540,190)
control(blade,'image',left=0,top=0,width=920,height=1080,texture='aperture/blade.png')
menu=control(cs,'group');animation(menu,'fade',0,100,380,320)
control(menu,'label',left=76,top=72,width=550,height=70,font='font32',textcolor='FFF4FBFC',label='Aperture')
control(menu,'label',left=80,top=152,width=520,height=42,font='font13',textcolor='FF9BB5BB',label='A little space for everything you love')
control(menu,'label',left=1510,top=64,width=328,height=80,font='font_clock',textcolor='FFFFFFFF',shadowcolor='80000000',align='right',label='$INFO[System.Time]')
items=[(103,'Music','music','Albums, artwork and your next good listen.',(810,665)),(100,'Movies','movies','Your film library, on the big screen.',(1154,665)),(101,'TV shows','tv','Pick up your favourite series.',(1498,665)),(102,'Games','games','Explore your Kodi game collection.',(810,835)),(104,'Sources','files','Browse videos and connected media.',(1154,835)),(105,'Settings','settings','Make yourself at home.',(1498,835))]
actions={100:'ActivateWindow(Videos,videodb://movies/titles/,return)',101:'ActivateWindow(Videos,videodb://tvshows/titles/,return)',102:'ActivateWindow(Games)',104:'ActivateWindow(Videos)',105:'ActivateWindow(Settings)'}
edges={103:(101,100,106,102),100:(103,101,106,104),101:(100,103,106,105),102:(105,104,103,106),104:(102,105,100,106),105:(104,102,101,106)}
for ident,label,icon,description,(x,y) in items:
 title=control(menu,'group',visible=f'Control.HasFocus({ident})');E.SubElement(title,'animation',{'effect':'fade','time':'160'}).text='VisibleChange'
 control(title,'label',left=74,top=372,width=600,height=110,font='font60',textcolor='FFF6FCFC',label=label)
 control(title,'textbox',left=80,top=490,width=510,height=128,font='font13',textcolor='FFD0DEE0',label=description)
 b=control(menu,'button',ident,left=x,top=y,width=320,height=148,label=label,font='font32',textcolor='FF224C59',focusedcolor='FF103D48',align='center',aligny='top',textoffsety=88,texturefocus='aperture/card-focus.png',texturenofocus='aperture/card.png')
 l,r,u,d=edges[ident]
 for k,v in [('onleft',l),('onright',r),('onup',u),('ondown',d)]:E.SubElement(b,k).text=str(v)
 if ident==103:
  E.SubElement(b,'onclick',{'condition':'System.AddonIsEnabled(plugin.audio.aperture.format)'}).text='ActivateWindow(Music,plugin://plugin.audio.aperture.format/,return)'
  E.SubElement(b,'onclick',{'condition':'!System.AddonIsEnabled(plugin.audio.aperture.format)'}).text='ActivateWindow(Music)'
 else:E.SubElement(b,'onclick').text=actions[ident]
 control(menu,'image',left=x+124,top=y+12,width=72,height=72,texture='aperture/'+icon+'.png')
power=control(menu,'button',106,left=76,top=922,width=214,height=70,label='Power',font='font13',align='center',aligny='center',textcolor='FFE0EFF1',focusedcolor='FF103D48',texturefocus='aperture/power-focus.png',texturenofocus='aperture/power.png',onleft=105,onright=103,onup=102,ondown=103,onclick='ActivateWindow(ShutdownMenu)')
control(menu,'label',left=80,top=1013,width=530,height=34,font='font10',textcolor='FF91AEB5',label='Choose a channel. Make the evening yours.')
E.indent(win,space='  ');E.ElementTree(win).write(ROOT/'skin/xml/Home.xml',encoding='utf-8',xml_declaration=True)

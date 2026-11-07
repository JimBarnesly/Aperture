"""Generate original UI primitives and a single MediaStream-inspired Home menu."""
from pathlib import Path
from PIL import Image, ImageDraw
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1]
MEDIA=ROOT/'skin/media/aperture'; MEDIA.mkdir(parents=True,exist_ok=True)
# Original UI primitive: a dark blade that gradually reveals the landscape edge.
im=Image.new('RGBA',(760,1080),(0,0,0,0)); d=ImageDraw.Draw(im)
for x in range(760):
    alpha=232 if x<540 else max(0,round(232*(1-(x-540)/220)**1.5))
    d.line((x,0,x,1080),fill=(13,27,31,alpha))
im.save(MEDIA/'blade.png')
im=Image.new('RGBA',(5,58),(0,0,0,0))
ImageDraw.Draw(im).rounded_rectangle((0,0,4,57),radius=2,fill=(146,225,235,220))
im.save(MEDIA/'focus-marker.png')
# Retire the duplicate channel-card presentation from the assembled skin.
for name in ('card','card-focus','power','power-focus','music','movies','tv','games','files','settings'):
    (MEDIA/(name+'.png')).unlink(missing_ok=True)

def control(parent,typ,ident=None,**props):
    e=E.SubElement(parent,'control',{'type':typ,**({'id':str(ident)} if ident else {})})
    for key,value in props.items(): E.SubElement(e,key).text=str(value)
    return e

def animation(parent,effect,start,end,time,delay=0):
    E.SubElement(parent,'animation',{'effect':effect,'start':str(start),'end':str(end),'time':str(time),'delay':str(delay),'tween':'cubic','easing':'out'}).text='WindowOpen'

win=E.Element('window'); E.SubElement(win,'defaultcontrol',{'always':'false'}).text='103'
E.SubElement(win,'backgroundcolor').text='FF14252C'; cs=E.SubElement(win,'controls')
control(cs,'image',left=0,top=0,width=1920,height=1080,texture='aperture/bridge.png',aspectratio='scale')
blade=control(cs,'group'); animation(blade,'slide','-760,0','0,0',540,190)
control(blade,'image',left=0,top=0,width=760,height=1080,texture='aperture/blade.png')
menu=control(cs,'group'); animation(menu,'fade',0,100,380,320)
control(menu,'label',left=1480,top=64,width=358,height=80,font='font_clock',textcolor='FFFFFFFF',shadowcolor='80000000',align='right',label='$INFO[System.Time]')
items=[(100,'Movies'),(101,'TV shows'),(103,'Music'),(102,'Games'),(104,'Sources'),(105,'Settings')]
actions={104:'ActivateWindow(Videos,sources://video/,return)',105:'ActivateWindow(Settings)'}
ids=[ident for ident,_ in items]
for index,(ident,label) in enumerate(items):
    y=300+index*88
    # One visible label per destination. The button retains its accessible name;
    # separate conditional labels allow the original large active-title rhythm.
    b=control(menu,'button',ident,left=80,top=y,width=550,height=86,label=label,font='font32',textcolor='00000000',focusedcolor='00000000',texturefocus='',texturenofocus='',onleft=106,onright=ident,onup=ids[index-1] if index else 106,ondown=ids[index+1] if index+1<len(ids) else 106)
    if ident==103:
        # Music is one integrated Format library, not a local/streaming choice.
        enabled='System.AddonIsEnabled(plugin.audio.aperture.format)'
        E.SubElement(b,'onclick',{'condition':enabled}).text='ActivateWindow(Music,plugin://plugin.audio.aperture.format/?action=albums,return)'
        E.SubElement(b,'onclick',{'condition':f'!{enabled}'}).text='ActivateWindow(AddonBrowser)'
        E.SubElement(b,'onclick',{'condition':f'!{enabled}'}).text='Notification(Music needs Format,Install or enable Aperture Format in Add-ons.,8000)'
    elif ident==100:
        enabled='System.AddonIsEnabled(plugin.video.aperture.movies)'
        E.SubElement(b,'onclick',{'condition':enabled}).text='ActivateWindow(Videos,plugin://plugin.video.aperture.movies/,return)'
        E.SubElement(b,'onclick',{'condition':f'!{enabled} + Library.HasContent(Movies)'}).text='ActivateWindow(Videos,videodb://movies/titles/,return)'
        E.SubElement(b,'onclick',{'condition':f'!{enabled} + !Library.HasContent(Movies)'}).text='ActivateWindow(Videos,sources://video/,return)'
    elif ident==101:
        E.SubElement(b,'onclick',{'condition':'Library.HasContent(TVShows)'}).text='ActivateWindow(Videos,videodb://tvshows/titles/,return)'
        E.SubElement(b,'onclick',{'condition':'!Library.HasContent(TVShows)'}).text='ActivateWindow(Videos,sources://video/,return)'
    elif ident==102:
        E.SubElement(b,'onclick',{'condition':'System.AddonIsEnabled(plugin.games.aperture)'}).text='ActivateWindow(Games,plugin://plugin.games.aperture/,return)'
        E.SubElement(b,'onclick',{'condition':'!System.AddonIsEnabled(plugin.games.aperture)'}).text='ActivateWindow(Games)'
    else: E.SubElement(b,'onclick').text=actions[ident]
    focused=f'Control.HasFocus({ident})'
    control(menu,'label',left=50,top=y,width=565,height=86,font='font32',align='right',aligny='center',textcolor='FF9DB2B9',shadowcolor='40000000',label=label,visible=f'![{focused}]')
    active=control(menu,'group',visible=focused)
    E.SubElement(active,'animation',{'effect':'fade','time':'130'}).text='VisibleChange'
    control(active,'label',left=25,top=y,width=590,height=86,font='font60',align='right',aligny='center',textcolor='FFF4FCFD',shadowcolor='60000000',label=label)
    control(active,'image',left=638,top=y+14,width=5,height=58,texture='aperture/focus-marker.png')
control(menu,'button',106,left=365,top=942,width=250,height=70,label='Power',font='font13',align='right',aligny='center',textcolor='FF8FA9B0',focusedcolor='FFDFFBFF',texturefocus='',texturenofocus='',onleft=105,onright=103,onup=105,ondown=100,onclick='ActivateWindow(ShutdownMenu)')
import copy
r=win; controls=cs; active='Player.HasAudio | Player.HasVideo'
for b in r.findall('.//control[@type="button"]'):
 old=b.find('onright');target=old.text;old.set('condition',active);old.text='120';new=E.Element('onright',condition='!['+active+']');new.text=target;b.insert(list(b).index(old)+1,new)
g=E.SubElement(controls,'control',type='group',id='119')
def node(parent,typ,**vals):
 c=E.SubElement(parent,'control',type=typ)
 for k,v in vals.items():E.SubElement(c,k).text=str(v)
 return c
b=node(g,'button',left=780,top=872,width=1060,height=148,label='Now playing',font='font13',textcolor='00000000',focusedcolor='00000000',texturefocus='colors/white.png',texturenofocus='colors/white.png',onleft=103,onright=103,onup=103,ondown=103,onback='SetFocus(103)');b.set('id','120');b.find('texturefocus').set('colordiffuse','E02B5868');b.find('texturenofocus').set('colordiffuse','DC14252C')
# Return to the active native player without replacing or restarting media.
E.SubElement(b,'onclick',condition='Player.HasVideo').text='ActivateWindow(fullscreenvideo)'
E.SubElement(b,'onclick',condition='Player.HasAudio + !Player.HasVideo').text='ActivateWindow(visualisation)'
node(g,'label',left=810,top=884,width=760,height=30,font='font13',textcolor='FF9DB2B9',label='NOW PLAYING',visible='!Player.Paused')
node(g,'label',left=810,top=884,width=760,height=30,font='font13',textcolor='FF9DB2B9',label='PAUSED',visible='Player.Paused')
node(g,'label',left=810,top=918,width=990,height=44,font='font32',textcolor='FFFFFFFF',label='$INFO[Player.Title]',scroll='true',visible='!String.IsEmpty(Player.Title)')
node(g,'label',left=810,top=918,width=990,height=44,font='font32',textcolor='FFFFFFFF',label='Current media',visible='String.IsEmpty(Player.Title)')
for pred,label in [('Player.HasAudio','$INFO[MusicPlayer.Artist,, · ]Show record  ›'),('Player.HasVideo + !String.IsEmpty(VideoPlayer.TVShowTitle)','$INFO[VideoPlayer.TVShowTitle,, · ]Return to video  ›'),('Player.HasVideo + String.IsEmpty(VideoPlayer.TVShowTitle)','Return to video  ›')]:
 node(g,'label',left=810,top=972,width=770,height=30,font='font13',textcolor='FFDFFBFF',label=label,visible=pred)
node(g,'label',left=1590,top=972,width=210,height=30,font='font13',textcolor='FF9DB2B9',align='right',label='$INFO[Player.Time]')

# Keep the focused shortcut navigable when playback ends between remote presses.
# Each visual control is hidden independently; the group itself remains focusable.
for child in g.findall('control'):
    visible=child.find('visible')
    if visible is None: visible=E.SubElement(child,'visible'); visible.text=active
    else: visible.text='['+active+'] + ['+visible.text+']'
    if child.get('id')=='120': visible.set('allowhiddenfocus','true')
E.indent(win,space='  '); E.ElementTree(win).write(ROOT/'skin/xml/Home.xml',encoding='utf-8',xml_declaration=True)

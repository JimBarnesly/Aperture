"""Real Kodi dialog visual/navigation checks; never selects a power operation."""
import json, os, time, traceback, threading
from pathlib import Path
import xbmc, xbmcgui
OUT=Path(os.environ['APERTURE_MOVIES_OUT']); monitor=xbmc.Monitor();checks=[]
def rpc(method,params=None):
 d={'jsonrpc':'2.0','id':1,'method':method}
 if params is not None:d['params']=params
 r=json.loads(xbmc.executeJSONRPC(json.dumps(d)))
 if 'error' in r:raise RuntimeError(r['error'])
 return r['result']
def until(label,pred):
 end=time.monotonic()+20
 while time.monotonic()<end:
  if pred():return
  if monitor.waitForAbort(.1):raise RuntimeError('Aborted '+label)
 raise RuntimeError('Timed out '+label)
def shot(name):
 monitor.waitForAbort(1.2);p=OUT/(name+'.png');xbmc.executebuiltin('TakeScreenshot('+str(p)+',sync)');until(name,lambda:p.exists())
try:
 until('Home',lambda:xbmcgui.getCurrentWindowId()==10000);shot('home-without-title')
 for attempt in range(2):
  xbmc.executebuiltin('ActivateWindow(shutdownmenu)');until('power menu',lambda:xbmcgui.getCurrentWindowDialogId()==10111)
  before=xbmc.getInfoLabel('Container(9000).ListItem.Label');rpc('Input.Down');monitor.waitForAbort(.3)
  after=xbmc.getInfoLabel('Container(9000).ListItem.Label')
  if before==after:raise RuntimeError('Power selection did not move')
  shot('power-menu' if attempt==0 else 'power-menu-reopened')
  rpc('Input.Back');until('power cancelled',lambda:not xbmc.getCondVisibility('System.HasModalDialog'))
  checks.append({'check':'power-open-navigate-cancel','attempt':attempt,'actions_executed':False})
 result=[]
 thread=threading.Thread(target=lambda:result.append(xbmcgui.Dialog().select('Choose a source',['Local collection','Another collection'])))
 thread.start();until('select',lambda:xbmcgui.getCurrentWindowDialogId()==12000);shot('selection-dialog');rpc('Input.Down');rpc('Input.Back');thread.join(5)
 if result!=[-1]:raise RuntimeError('Selection cancel failed '+str(result))
 checks.append({'check':'selection-cancel','result':result})
 result=[]
 thread=threading.Thread(target=lambda:result.append(xbmcgui.Dialog().yesno('Confirm','Harmless QA prompt. No system action is attached.')))
 thread.start();until('confirm',lambda:xbmcgui.getCurrentWindowDialogId()==10100);shot('confirmation-dialog');rpc('Input.Back');thread.join(5)
 if result!=[False]:raise RuntimeError('Confirmation cancel failed '+str(result))
 checks.append({'check':'confirmation-cancel','result':result})
 # Native playback state and D-pad bar acceptance, including stop while focused.
 home=xbmcgui.Window(10000)
 def bar_visible():return xbmc.getCondVisibility('Control.IsVisible(119) + Control.IsVisible(120)')
 if bar_visible():raise RuntimeError('Idle Home shows a playback bar')
 player=xbmc.Player()
 for kind,title in [('audio','Synthetic audio title'),('video','Synthetic movie title'),('episode','Synthetic episode title')]:
  path=str(Path(os.environ['APERTURE_MOVIES_RUNTIME'])/('home-bar.wav' if kind=='audio' else 'home-bar.mp4'))
  item=xbmcgui.ListItem(label=title,path=path)
  item.setInfo('music' if kind=='audio' else 'video',dict(title=title,**({'artist':['Synthetic artist']} if kind=='audio' else {'tvshowtitle':'Synthetic series','mediatype':'episode'} if kind=='episode' else {'mediatype':'movie'})))
  player.play(path,item)
  until('playback fullscreen ready',lambda:player.isPlaying() and xbmcgui.getCurrentWindowId() in (12005,12006) and not xbmc.getCondVisibility('System.HasModalDialog'))
  monitor.waitForAbort(.5)
  xbmc.executebuiltin('ActivateWindow(Home)');until('Home playback',lambda:xbmcgui.getCurrentWindowId()==10000 and bar_visible())
  until('player title',lambda:xbmc.getInfoLabel('Player.Title')==title)
  home.setFocusId(103);rpc('Input.Right');until('bar focus',lambda:home.getFocusId()==120)
  shot('home-bar-'+kind)
  player.pause();until('paused',lambda:xbmc.getCondVisibility('Player.Paused'))
  if not bar_visible():raise RuntimeError('Paused bar disappeared')
  shot('home-bar-'+kind+'-paused')
  rpc('Input.Select')
  expected=10502 if kind=='audio' else 10025
  # The fixture has no Format add-on, so audio uses the existing AddonBrowser fallback.
  if kind=='audio' and not xbmc.getCondVisibility('System.AddonIsEnabled(plugin.audio.aperture.format)'):expected=10040
  until('destination',lambda:xbmcgui.getCurrentWindowId()==expected)
  expected_path = ('plugin://plugin.audio.aperture.format/' if kind=='audio' else 'sources://video/' if kind=='episode' else 'plugin://plugin.video.aperture.movies/')
  if expected != 10040:
   until('exact destination path '+expected_path,lambda:xbmc.getInfoLabel('Container.FolderPath').rstrip('/')==expected_path.rstrip('/'))
  destination_path=xbmc.getInfoLabel('Container.FolderPath')
  shot('home-bar-'+kind+'-destination')
  if not player.isPlaying():raise RuntimeError('Bar navigation stopped playback')
  if kind=='video' and xbmcgui.getCurrentWindowDialogId()==10100:
   rpc('Input.Back');until('empty Movies notice closed',lambda:not xbmc.getCondVisibility('System.HasModalDialog'))
   monitor.waitForAbort(.5)
  rpc('Input.Back');until('Back Home',lambda:xbmcgui.getCurrentWindowId()==10000)
  shot('home-bar-'+kind+'-returned')
  home.setFocusId(103);until('Music refocus',lambda:home.getFocusId()==103)
  rpc('Input.Right');until('bar refocus',lambda:home.getFocusId()==120)
  player.stop();until('bar hidden after stop',lambda:not bar_visible())
  monitor.waitForAbort(.7)
  checks.append({'check':'stop-before-left','window':xbmcgui.getCurrentWindowId(),'focus':home.getFocusId()})
  rpc('Input.Left');until('focus recovered',lambda:home.getFocusId() in range(100,107))
  checks.append({'check':'home-now-playing','kind':kind,'pause':True,'remote_select_back_stop':True,'destination_window':expected,'destination_path':destination_path})
 shot('home-after-dialogs')
 (OUT/'result.json').write_text(json.dumps({'status':'passed','checks':checks,'limitations':['Software rendered Kodi 21.3, no physical Pi or controller','No power or reboot actions executed']},indent=2))
except Exception as e:
 try:shot('failure')
 except Exception:pass
 (OUT/'result.json').write_text(json.dumps({'status':'failed','reason':str(e),'traceback':traceback.format_exc(),'checks':checks},indent=2))
finally:xbmc.executebuiltin('Quit')

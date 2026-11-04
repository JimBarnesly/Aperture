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
 shot('home-after-dialogs')
 (OUT/'result.json').write_text(json.dumps({'status':'passed','checks':checks,'limitations':['Software rendered Kodi 21.3, no physical Pi or controller','No power or reboot actions executed']},indent=2))
except Exception as e:
 try:shot('failure')
 except Exception:pass
 (OUT/'result.json').write_text(json.dumps({'status':'failed','reason':str(e),'traceback':traceback.format_exc(),'checks':checks},indent=2))
finally:xbmc.executebuiltin('Quit')

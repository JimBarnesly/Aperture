"""CI-only real Kodi/RetroPlayer exercise; never installed on the user's Pi."""
import json
import os
from pathlib import Path
import time
import traceback
import subprocess
import platform
import xbmc
import xbmcgui

out=Path(os.environ['APERTURE_GAMING_OUT'])
runtime=Path(os.environ['APERTURE_GAMING_RUNTIME'])
assert runtime.name.startswith('aperture-gaming-qa.')
monitor=xbmc.Monitor()
checks=[]
def rpc(method,params=None):
    request={'jsonrpc':'2.0','id':1,'method':method}
    if params is not None: request['params']=params
    response=json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    if 'error' in response: raise RuntimeError(response['error'])
    return response['result']
def until(description,predicate,timeout=35):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate(): return
        if monitor.waitForAbort(.15): raise RuntimeError('Kodi exited during '+description)
    raise RuntimeError('Timed out '+description)
def active(): return [{'type':'game'}] if xbmc.Player().isPlayingGame() else []
def capture(name):
    if platform.machine() in ('x86_64','amd64'):
        xbmc.executebuiltin('TakeScreenshot('+str(out/(name+'.png'))+',sync)')
        until('native screenshot',lambda:(out/(name+'.png')).exists(),timeout=8)
    else:
        subprocess.run(['import', '-window', 'root', str(out/(name+'.png'))], check=True, timeout=10)
try:
    until('Home',lambda:xbmcgui.getCurrentWindowId()==10000)
    for addon in ('game.libretro','peripheral.joystick','game.libretro.aperture.nestopia','game.libretro.aperture.pcsxrearmed'):
        rpc('Addons.SetAddonEnabled',{'addonid':addon,'enabled':True})
    until('core enabled',lambda:xbmc.getCondVisibility('System.AddonIsEnabled(game.libretro.aperture.nestopia)'))
    systems=rpc('Files.GetDirectory',{'directory':'plugin://plugin.games.aperture/','media':'files'})['files']
    if not any('Nintendo' in item['label'] for item in systems): raise RuntimeError('NES system missing from actual plugin root')
    checks.append({'check':'actual-plugin-system-list','labels':[i['label'] for i in systems]})
    for system,core,title in [('nes','nestopia','Aperture Palette Probe'),('psx','pcsxrearmed','Aperture GPU Probe')]:
        folder='plugin://plugin.games.aperture/?action=system&system='+system
        listing=rpc('Files.GetDirectory',{'directory':folder,'media':'files'})['files']
        game=next((x for x in listing if x['label']==title),None)
        if not game: raise RuntimeError('Synthetic game absent from actual plugin list: '+title)
        # Exercise the directory launch action and native core selection, not a direct ROM bypass.
        until('no modal before browsing',lambda:not xbmc.getCondVisibility('System.HasModalDialog'))
        monitor.waitForAbort(.3)
        xbmc.executebuiltin('ActivateWindow(Games,'+folder+',return)')
        until('Games directory',lambda:xbmcgui.getCurrentWindowId()==10821 and xbmc.getInfoLabel('Container.FolderPath')==folder and not xbmc.getCondVisibility('System.HasModalDialog'))
        monitor.waitForAbort(.6)
        for cycle in range(1):
            # Navigate and select the actual listed action as a controller would.
            for _ in range(12):
                if xbmc.getInfoLabel('ListItem.Label') == title: break
                rpc('Input.Down')
                monitor.waitForAbort(.2)
            if xbmc.getInfoLabel('ListItem.Label') != title: raise RuntimeError('Cannot focus game action '+title)
            rpc('Input.Select')
            until('RetroPlayer active '+system,lambda:any(p['type']=='game' for p in active()))
            monitor.waitForAbort(8)
            players=active()
            if not any(p['type']=='game' for p in players): raise RuntimeError('Game stopped prematurely: '+system)
            capture(system+'-playing-'+str(cycle))
            checks.append({'check':'real-game-play-'+system+'-'+str(cycle),'players':players,'window':xbmcgui.getCurrentWindowId()})
            xbmc.Player().stop()
            until('game stopped '+system,lambda:not any(p['type']=='game' for p in active()))
            until('return to Games',lambda:xbmcgui.getCurrentWindowId()==10821 and not xbmc.getCondVisibility('System.HasModalDialog'))
            monitor.waitForAbort(.6)
            checks.append({'check':'exit-back-to-games-'+system+'-'+str(cycle),'window':xbmcgui.getCurrentWindowId()})
    result={'status':'passed','checks':checks,'limitations':['Synthetic original NES/PSX programs only','No physical Pi, 8BitDo, Bluetooth, BIOS or commercial-game testing','No audible hardware-output test']}
    (out/'result.json').write_text(json.dumps(result,indent=2))
except Exception as exc:
    try:
        capture('failure')
    except Exception:
        pass  # Preserve the original failure even if the framebuffer is unavailable.
    (out/'result.json').write_text(json.dumps({'status':'failed','reason':str(exc),'checks':checks,'traceback':traceback.format_exc()},indent=2))
finally:
    xbmc.executebuiltin('Quit')

"""CI-only real Kodi/RetroPlayer exercise; never installed on the user's Pi."""
import json
import os
from pathlib import Path
import time
import traceback
import subprocess
import platform
import hashlib
import sys
import xbmcvfs
import xbmc
import xbmcgui
import xbmcaddon

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
    state={'window':xbmcgui.getCurrentWindowId(),
           'dialog':xbmcgui.getCurrentWindowDialogId(),
           'folder':xbmc.getInfoLabel('Container.FolderPath'),
           'label':xbmc.getInfoLabel('ListItem.Label'),
           'cards_visible':xbmc.getCondVisibility('Control.IsVisible(59)'),
           'games_visible':xbmc.getCondVisibility('Control.IsVisible(60)')}
    raise RuntimeError('Timed out '+description+'; state='+json.dumps(state,sort_keys=True))
def active(): return [{'type':'game'}] if xbmc.Player().isPlayingGame() else []
def open_console_cards():
    root='plugin://plugin.games.aperture/'
    if xbmcgui.getCurrentWindowId()!=10821:
        xbmc.executebuiltin('ActivateWindow(Games,'+root+',return)')
    elif xbmc.getInfoLabel('Container.FolderPath')!=root:
        # Games is already open after Stop. ActivateWindow on that same window
        # does not navigate its directory, so exercise the real Back action.
        rpc('Input.Back')
    until('console cards',lambda:xbmcgui.getCurrentWindowId()==10821
          and xbmc.getInfoLabel('Container.FolderPath')==root
          and xbmc.getCondVisibility('Control.IsVisible(59)')
          and not xbmc.getCondVisibility('System.HasModalDialog'))
def capture(name):
    if platform.machine() in ('x86_64','amd64'):
        xbmc.executebuiltin('TakeScreenshot('+str(out/(name+'.png'))+',sync)')
        until('native screenshot',lambda:(out/(name+'.png')).exists(),timeout=8)
    else:
        subprocess.run(['import', '-window', 'root', str(out/(name+'.png'))], check=True, timeout=10)
def saved_library():
    addon = xbmcaddon.Addon('plugin.games.aperture')
    sys.path.insert(0, os.path.join(addon.getAddonInfo('path'), 'resources', 'lib'))
    from apeture_library.cache import LibraryCache
    return LibraryCache(xbmcvfs.translatePath(addon.getAddonInfo('profile')), addon.getSetting('rom_root'))

def cache_evidence(cache):
    return {'snapshot': hashlib.sha256(cache.path.read_bytes()).hexdigest(),
            'attempt': hashlib.sha256(cache.attempt_path.read_bytes()).hexdigest()}

def verify_cached_navigation(cache):
    before = cache_evidence(cache)
    root = 'plugin://plugin.games.aperture/'
    for cycle in range(3):
        if xbmcgui.getCurrentWindowId() != 10000:
            xbmc.executebuiltin('ActivateWindow(Home)')
            until('Home before cached entry', lambda: xbmcgui.getCurrentWindowId()==10000)
        # Wait for the previous window animation/activation to finish. A state
        # snapshot taken mid-transition is not a completed navigation action.
        monitor.waitForAbort(.6)
        started = time.monotonic()
        xbmc.executebuiltin('ActivateWindow(Games,'+root+',return)')
        until('cached Games entry', lambda: xbmcgui.getCurrentWindowId()==10821
              and xbmc.getInfoLabel('Container.FolderPath')==root
              and xbmc.getInfoLabel('Container.Property(Aperture.LibraryState)')=='ready'
              and not xbmc.getCondVisibility('System.HasModalDialog'))
        elapsed = time.monotonic() - started
        monitor.waitForAbort(.6)
        if os.environ.get('APERTURE_GAMING_SKIN') != 'classic':
            until('selector visible', lambda: xbmc.getCondVisibility('Control.IsVisible(59)'))
            until('initial console focus', lambda: bool(xbmc.getInfoLabel('ListItem.Property(Aperture.System)')), timeout=5)
            initial = xbmc.getInfoLabel('ListItem.Property(Aperture.System)')
            rpc('Input.Right'); monitor.waitForAbort(.5)
            right = xbmc.getInfoLabel('ListItem.Property(Aperture.System)')
            rpc('Input.Left'); monitor.waitForAbort(.5)
            restored = xbmc.getInfoLabel('ListItem.Property(Aperture.System)')
            if not initial or initial == right or restored != initial:
                raise RuntimeError('Horizontal system focus mismatch: initial={!r}, right={!r}, restored={!r}'.format(initial, right, restored))
            checks.append({'check':'horizontal-system-selection-'+str(cycle), 'initial':initial, 'right':right, 'restored':restored})
        if cache_evidence(cache) != before:
            raise RuntimeError('Games reentry unexpectedly rewrote cache or started another scan')
        checks.append({'check':'cached-root-entry-'+str(cycle), 'seconds':round(elapsed,3), 'no_new_scan':True})
    capture('persistent-games-selector')

def verify_library_dialogs(cache):
    before = cache_evidence(cache)
    root = 'plugin://plugin.games.aperture/'
    selected = xbmc.getInfoLabel('ListItem.Property(Aperture.System)')
    for name, command, dialog in (
            ('settings', 'Addon.OpenSettings(plugin.games.aperture)', 10140),
            ('help', 'RunPlugin('+root+'?action=help)', 12002)):
        xbmc.executebuiltin(command)
        until('library '+name+' dialog opens', lambda: xbmcgui.getCurrentWindowDialogId()==dialog)
        monitor.waitForAbort(.5)
        capture('library-'+name)
        rpc('Input.Back')
        until('library '+name+' dialog closes', lambda: not xbmc.getCondVisibility('System.HasModalDialog'))
        monitor.waitForAbort(.5)
        if xbmc.getInfoLabel('Container.FolderPath') != root:
            raise RuntimeError('Library '+name+' dismissal changed the directory')
        if selected and xbmc.getInfoLabel('ListItem.Property(Aperture.System)') != selected:
            raise RuntimeError('Library '+name+' dismissal lost the selected system')
        if cache_evidence(cache) != before:
            raise RuntimeError('Library '+name+' dismissal caused a scan')
        checks.append({'check':'library-'+name+'-dismissal-preserves-selection-and-cache'})

try:
    until('Home',lambda:xbmcgui.getCurrentWindowId()==10000)
    cache = saved_library()
    until('background library service publishes snapshot', lambda: cache.load() is not None and cache.status() == 'ready', timeout=45)
    if os.environ.get('APERTURE_GAMING_PHASE') == 'restart':
        prior = json.loads((out/'restart-request.json').read_text())
        checks.extend(prior['checks'])
        if cache_evidence(cache) != prior['cache']:
            raise RuntimeError('Native Kodi restart rescanned or replaced the fresh saved library')
        verify_cached_navigation(cache)
        checks.append({'check':'native-restart-preserves-library-without-scan', 'cache':cache_evidence(cache)})
        (out/'result.json').write_text(json.dumps({'status':'passed','checks':checks,
            'limitations':['Isolated native Kodi restart, not a physical Pi power cycle',
                           'Synthetic original games only; no physical controllers or audible hardware acceptance']},indent=2))
        raise SystemExit(0)
    verify_cached_navigation(cache)
    verify_library_dialogs(cache)
    for addon in ('game.libretro','peripheral.joystick','game.libretro.aperture.nestopia','game.libretro.aperture.pcsxrearmed'):
        rpc('Addons.SetAddonEnabled',{'addonid':addon,'enabled':True})
    until('core enabled',lambda:xbmc.getCondVisibility('System.AddonIsEnabled(game.libretro.aperture.nestopia)'))
    psx_addon=xbmcaddon.Addon('game.libretro.aperture.pcsxrearmed')
    if psx_addon.getSetting('pcsx_rearmed_neon_enhancement_enable') != 'disabled':
        raise RuntimeError('Enhanced resolution must default to disabled')
    xbmc.executebuiltin('Addon.OpenSettings(game.libretro.aperture.pcsxrearmed)')
    until('PSX settings UI',lambda:xbmcgui.getCurrentWindowDialogId()==10140)
    monitor.waitForAbort(.5)
    capture('psx-video-settings')
    checks.append({'check':'psx-settings-ui-opens','dialog':xbmcgui.getCurrentWindowDialogId(),'native_default':True})
    # Exercise the actual spinner, then OK, rather than setting an add-on copy.
    rpc('Input.Select')
    monitor.waitForAbort(.4)
    capture('psx-video-settings-enhanced')
    xbmc.executebuiltin('SetFocus(28)')
    monitor.waitForAbort(.2)
    rpc('Input.Select')
    until('settings closed',lambda:not xbmc.getCondVisibility('System.HasModalDialog'))
    monitor.waitForAbort(.5)
    psx_addon=xbmcaddon.Addon('game.libretro.aperture.pcsxrearmed')
    if psx_addon.getSetting('pcsx_rearmed_neon_enhancement_enable') != 'enabled':
        raise RuntimeError('GUI did not save enhanced-resolution choice')
    checks.append({'check':'psx-settings-ui-saves-enabled'})
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
        if system=='psx':
            rpc('Settings.SetSettingValue',{'setting':'gamesgeneral.enableautosave','value':True})
        if os.environ.get('APERTURE_GAMING_SKIN')=='classic':
            xbmc.executebuiltin('ActivateWindow(Games,'+folder+',return)')
            until('classic Games directory',lambda:xbmcgui.getCurrentWindowId()==10821 and xbmc.getInfoLabel('Container.FolderPath')==folder and not xbmc.getCondVisibility('System.HasModalDialog'))
            monitor.waitForAbort(.6)
        else:
            open_console_cards()
            monitor.waitForAbort(.4)
            for _ in range(12):
                if xbmc.getInfoLabel('ListItem.Property(Aperture.System)')==system: break
                rpc('Input.Right'); monitor.waitForAbort(.2)
            if xbmc.getInfoLabel('ListItem.Property(Aperture.System)')!=system: raise RuntimeError('Cannot focus console '+system)
            monitor.waitForAbort(.5)
            capture(system+'-console-cards')
            rpc('Input.Select')
            until('Games directory',lambda:xbmcgui.getCurrentWindowId()==10821 and xbmc.getInfoLabel('Container.FolderPath')==folder and xbmc.getCondVisibility('Control.IsVisible(60)') and not xbmc.getCondVisibility('System.HasModalDialog'))
            monitor.waitForAbort(.6)
        for cycle in range(1):
            # Navigate and select the actual listed action as a controller would.
            for _ in range(12):
                if xbmc.getInfoLabel('ListItem.Label') == title: break
                rpc('Input.Down')
                monitor.waitForAbort(.2)
            if xbmc.getInfoLabel('ListItem.Label') != title: raise RuntimeError('Cannot focus game action '+title)
            capture(system+'-game-browser')
            rpc('Input.Select')
            until('RetroPlayer active '+system,lambda:any(p['type']=='game' for p in active()))
            monitor.waitForAbort(8)
            players=active()
            if not any(p['type']=='game' for p in players): raise RuntimeError('Game stopped prematurely: '+system)
            shot=system+'-playing-'+str(cycle)
            capture(shot)
            if system=='psx':
                log=(out/'logs/kodi.log').read_text(errors='replace')
                if 'Creating render buffer of size 640x480' not in log:
                    raise RuntimeError('Enhanced PSX did not produce expected 640x480 frame')
                checks.append({'check':'psx-enhanced-resolution-640x480'})
            means=subprocess.check_output(['convert',str(out/(shot+'.png')),'-format','%[fx:mean.r] %[fx:mean.g] %[fx:mean.b]','info:'],text=True,timeout=10)
            red,green,blue=map(float,means.split())
            if not (green>.1 and green>red*1.5 and green>blue*1.5):
                raise RuntimeError('Expected green test framebuffer, captured RGB means '+means)
            checks.append({'check':'visible-green-frame-'+system,'mean_rgb':[red,green,blue]})
            checks.append({'check':'real-game-play-'+system+'-'+str(cycle),'players':players,'window':xbmcgui.getCurrentWindowId()})
            xbmc.Player().stop()
            until('game stopped '+system,lambda:not any(p['type']=='game' for p in active()))
            until('return to Games',lambda:xbmcgui.getCurrentWindowId()==10821 and not xbmc.getCondVisibility('System.HasModalDialog'))
            monitor.waitForAbort(.6)
            checks.append({'check':'exit-back-to-games-'+system+'-'+str(cycle),'window':xbmcgui.getCurrentWindowId()})
            if system=='psx':
                until('PSX autosave written',lambda:any((runtime/'data/userdata').rglob('*.sav')),timeout=20)
                if monitor.waitForAbort(4): raise RuntimeError('Kodi exited after PSX autosave')
                checks.append({'check':'psx-autosave-stop-survives','save_files':len(list((runtime/'data/userdata').rglob('*.sav')))})
            if os.environ.get('APERTURE_GAMING_SKIN')!='classic':
                if xbmc.getInfoLabel('Container.FolderPath')!=folder:
                    raise RuntimeError('Stop did not preserve the '+system+' game directory')
                open_console_cards()
                monitor.waitForAbort(.7)
                until('Back restores selected console '+system,
                      lambda: xbmc.getInfoLabel('ListItem.Property(Aperture.System)') == system)
                capture(system+'-back-to-console-cards')
                checks.append({'check':'back-to-console-cards-'+system,
                               'folder':xbmc.getInfoLabel('Container.FolderPath'),
                               'view':59, 'selected_system':xbmc.getInfoLabel('ListItem.Property(Aperture.System)')})
    result={'status':'passed','checks':checks,'limitations':['Synthetic original NES/PSX programs only','No physical Pi, 8BitDo, Bluetooth, BIOS or commercial-game testing','No audible hardware-output test']}
    (out/'restart-request.json').write_text(json.dumps({'checks':checks,'cache':cache_evidence(cache)},indent=2))
except Exception as exc:
    try:
        capture('failure')
    except Exception:
        pass  # Preserve the original failure even if the framebuffer is unavailable.
    (out/'result.json').write_text(json.dumps({'status':'failed','reason':str(exc),'checks':checks,'traceback':traceback.format_exc()},indent=2))
finally:
    xbmc.executebuiltin('Quit')

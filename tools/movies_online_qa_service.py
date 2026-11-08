"""Runs inside real Kodi only, in the disposable cinematic movie CI profile."""
import json
import os
from pathlib import Path
import time
import traceback
import xbmc
import xbmcgui

OUT=Path(os.environ['APERTURE_MOVIES_OUT'])
RUNTIME=Path(os.environ['APERTURE_MOVIES_RUNTIME'])
SCENARIO=os.environ['APERTURE_MOVIES_SCENARIO']
assert RUNTIME.name.startswith('aperture-movies-qa.')
ROOT='plugin://plugin.video.aperture.movies/'
monitor=xbmc.Monitor()
checks=[]


def rpc(method, params=None):
    request={'jsonrpc':'2.0','id':1,'method':method}
    if params is not None:
        request['params']=params
    response=json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    if 'error' in response:
        raise RuntimeError(response['error'])
    return response['result']


def until(description,predicate,timeout=35):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate():
            return
        if monitor.waitForAbort(.15):
            raise RuntimeError('Kodi exited during '+description)
    state={'window':xbmcgui.getCurrentWindowId(),'dialog':xbmcgui.getCurrentWindowDialogId(),'folder':xbmc.getInfoLabel('Container.FolderPath'),'plugin':xbmc.getInfoLabel('Container.PluginName'),'label':xbmc.getInfoLabel('ListItem.Label'),'view61':xbmc.getCondVisibility('Control.IsVisible(61)'),'view50':xbmc.getCondVisibility('Control.IsVisible(50)')}
    raise RuntimeError('Timed out '+description+'; state='+json.dumps(state))


def capture(name):
    # Let focus, artwork crossfade and scrolling labels settle before visual QA.
    if monitor.waitForAbort(1.0):
        raise RuntimeError('Kodi exited before screenshot '+name)
    target=OUT/(name+'.png')
    xbmc.executebuiltin('TakeScreenshot('+str(target)+',sync)')
    until('screenshot '+name,lambda:target.exists() and target.stat().st_size>0,8)


def settled():
    return xbmcgui.getCurrentWindowId()==10025 and not xbmc.getCondVisibility('System.HasModalDialog')


def cinematic():
    return (settled() and xbmc.getCondVisibility('Control.IsVisible(61)')
            and not xbmc.getCondVisibility('Container.IsUpdating')
            and not xbmc.getCondVisibility('Window.IsActive(busydialog)')
            and not xbmc.getCondVisibility('Window.IsActive(busydialognocancel)'))


def wait_for_movie_idle(description, folder_path, stable_for=1.0):
    # Closing a context menu/picker does not mean its RunPlugin action and
    # queued Container.Refresh have completed. Require a continuous quiet
    # interval before sending more native input; restart it on refresh, focus
    # changes or a changed listing. This is a UI settling guard, not a plugin
    # completion signal. Keep the normal timeout and never retry Select.
    stable_since = None
    previous = None

    def ready():
        nonlocal stable_since, previous
        state = tuple(xbmc.getInfoLabel(label) for label in (
            'Container.FolderPath', 'ListItem.Label', 'Container.NumItems'))
        if not cinematic() or state[0] != folder_path:
            stable_since = None
            previous = None
            return False
        now = time.monotonic()
        if stable_since is None or state != previous:
            stable_since = now
            previous = state
        return now - stable_since >= stable_for

    until(description, ready)


def focus(label):
    # Native D-pad actions, never directly synthesize a selected item's URL.
    for forward in (True, False):
        for _ in range(12):
            if xbmc.getInfoLabel('ListItem.Label')==label:
                return
            horizontal=xbmc.getCondVisibility('Control.IsVisible(61)')
            action=('Input.Right' if forward else 'Input.Left') if horizontal else ('Input.Down' if forward else 'Input.Up')
            rpc(action)
            monitor.waitForAbort(.15)
    raise RuntimeError('Could not focus '+label+'; current='+xbmc.getInfoLabel('ListItem.Label'))


def assert_art(title):
    poster=xbmc.getInfoLabel('ListItem.Art(poster)')
    fanart=xbmc.getInfoLabel('ListItem.Art(fanart)')
    if not poster or not fanart or title not in (poster+fanart):
        raise RuntimeError('Focused movie lacks expected local poster/fanart: '+title)
    checks.append({'check':'local-art-'+title,'poster':poster,'fanart':fanart})


def poster_context_action(label):
    rpc('Input.ContextMenu')
    until('movie context menu', lambda: xbmcgui.getCurrentWindowDialogId() == 10106)
    for _ in range(30):
        if xbmc.getInfoLabel('System.CurrentControl') == label:
            rpc('Input.Select')
            return
        rpc('Input.Down')
        monitor.waitForAbort(.1)
    raise RuntimeError('Movie context action missing: '+label)


def events():
    path = OUT/'mock-events.jsonl'
    return [json.loads(line)['event'] for line in path.read_text().splitlines()] if path.exists() else []


def nav(label):
    # Up from posters enters Discover; left/right exercise the real skin graph.
    if xbmc.getInfoLabel('System.CurrentControl') not in ('Discover','Search','Collections','Genres','Local files','Sources'):
        rpc('Input.Up')
    for _ in range(7):
        if xbmc.getInfoLabel('System.CurrentControl') == label:
            return
        rpc('Input.Right'); monitor.waitForAbort(.2)
    raise RuntimeError('Navigation control not reachable: '+label)


def source_consent():
    nav('Sources'); rpc('Input.Select')
    until('Sources selection',lambda:xbmcgui.getCurrentWindowDialogId()==12000)
    # New disconnected selection opens on its first item; verify before Select.
    until('Connect choice focused',lambda:xbmc.getInfoLabel('System.CurrentControl')=='Connect Real-Debrid')
    rpc('Input.Select')
    until('RD consent',lambda:xbmcgui.getCurrentWindowDialogId()==10100)
    text=xbmc.getInfoLabel('Control.GetLabel(9)')
    for phrase in ('shared open-source app','torrents','not encrypted','backups','Continue?'):
        if phrase not in text:
            raise RuntimeError('Missing RD disclosure: '+phrase)
    return text


def consent_choice(yes):
    expected='Yes' if yes else 'No'
    for _ in range(4):
        if xbmc.getInfoLabel('System.CurrentControl')==expected:
            rpc('Input.Select'); return
        rpc('Input.Right'); monitor.waitForAbort(.2)
    raise RuntimeError('Cannot reach consent choice by D-pad')


try:
    until('Home',lambda:xbmcgui.getCurrentWindowId()==10000)
    version=rpc('Application.GetProperties',{'properties':['version']})['version']
    assert (version['major'],version['minor'])==(21,3)
    rpc('Addons.SetAddonEnabled',{'addonid':'plugin.video.aperture.movies','enabled':True})
    until('plugin enabled',lambda:xbmc.getCondVisibility('System.AddonIsEnabled(plugin.video.aperture.movies)'))
    xbmc.executebuiltin('ActivateWindow(Videos,'+ROOT+',return)')
    until('local cinematic view',cinematic)
    focus('Amber Horizon')
    local_path=xbmc.getInfoLabel('Container.FolderPath')
    nav('Discover'); rpc('Input.Select')
    until('online cinematic listing',lambda:cinematic() and 'mode=online' in xbmc.getInfoLabel('Container.FolderPath'))
    rpc('Input.Down')
    focus('Synthetic Online Horizon'); capture('online-catalogue')
    online_path=xbmc.getInfoLabel('Container.FolderPath')
    assert xbmc.getInfoLabel('ListItem.Property(IsPlayable)').lower()=='false'
    rpc('Input.Select')
    until('online details',lambda:xbmcgui.getCurrentWindowDialogId()==12002)
    text=xbmc.getInfoLabel('Control.GetLabel(9)')
    assert 'Playback availability not checked' in text
    capture('online-details'); rpc('Input.Select')
    wait_for_movie_idle('details dismissed without history change',online_path)
    checks.append({'check':'online-catalogue-and-details','synthetic_provider':True})
    for label,dialog in [('Search','virtualkeyboard'),('Search','virtualkeyboard'),('Collections','selectdialog'),('Genres','selectdialog')]:
        nav(label); rpc('Input.Select')
        until(label+' dialog',lambda:xbmc.getCondVisibility('Window.IsActive('+dialog+')'))
        capture('online-'+label.lower())
        rpc('Input.Back'); wait_for_movie_idle('cancel '+label,online_path)
    checks.append({'check':'online-search-repeat-collection-genre-cancel','history_preserved':True})
    for attempt in range(2):
        text=source_consent()
        capture('rd-consent-'+str(attempt))
        assert 'fake-device-code' not in events()
        if attempt==0:
            consent_choice(False)
        else:
            rpc('Input.Back')
        wait_for_movie_idle('RD decline/back',online_path)
        assert 'fake-device-code' not in events()
    checks.append({'check':'RD-consent-decline-and-back','provider_calls':False,'text':text})
    source_consent(); consent_choice(True)
    until('fake device progress',lambda:xbmcgui.getCurrentWindowDialogId()==10101)
    capture('rd-fake-device-progress')
    assert events().count('fake-device-code')==1
    rpc('Input.Back')
    wait_for_movie_idle('cancel fake device progress',online_path)
    import xbmcvfs
    private=Path(xbmcvfs.translatePath('special://profile/addon_data/plugin.video.aperture.movies/real-debrid-private'))
    assert not (private/'credentials.json').exists()
    assert 'unexpected-provider-operation' not in events()
    checks.append({'check':'RD-fake-device-cancel','real_provider_calls':False,'credentials_saved':False})
    nav('Local files'); rpc('Input.Select')
    until('return to local files',lambda:cinematic() and xbmc.getInfoLabel('Container.FolderPath')==local_path)
    rpc('Input.Down')
    focus('Amber Horizon'); capture('online-return-local')
    checks.append({'check':'controller-navigation-return-local'})
    result={'status':'passed','scenario':'online','checks':checks,'limitations':['Native Kodi 21.3 software-rendered CI only; not physical controller/Pi acceptance','Synthetic catalogue transport; no live service, usable device code, token exchange or grant','Screenshots require visual review for disclosure readability']}
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
except Exception as exc:
    try: capture('failure')
    except Exception: pass
    (OUT/'result.json').write_text(json.dumps({'status':'failed','scenario':'online','reason':str(exc),'checks':checks,'traceback':traceback.format_exc()},indent=2)+'\n')
finally:
    xbmc.executebuiltin('Quit')

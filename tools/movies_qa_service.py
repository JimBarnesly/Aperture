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


try:
    until('Home',lambda:xbmcgui.getCurrentWindowId()==10000)
    version=rpc('Application.GetProperties',{'properties':['version']})['version']
    if version['major']!=21 or version['minor']!=3:
        raise RuntimeError('Expected exact Kodi 21.3, found '+str(version))
    checks.append({'check':'runtime-version','version':version})
    rpc('Addons.SetAddonEnabled',{'addonid':'plugin.video.aperture.movies','enabled':True})
    until('movie plugin enabled',lambda:xbmc.getCondVisibility('System.AddonIsEnabled(plugin.video.aperture.movies)'))
    actual_sources=rpc('Files.GetSources',{'media':'video'}).get('sources',[])
    expected_count={'single':1,'default':2,'multiple':2,'empty':0}[SCENARIO]
    if len(actual_sources)!=expected_count:
        raise RuntimeError('Disposable source fixture was not loaded: '+str(actual_sources))
    checks.append({'check':'source-fixture','scenario':SCENARIO,'count':len(actual_sources)})
    # Diagnostic data is safe only because every source belongs to this disposable fixture.
    diagnostics=[]
    for source in actual_sources:
        directory=source['file']
        if not directory.startswith(str(RUNTIME)+'/'):
            raise RuntimeError('Unexpected non-fixture source; refusing to record it')
        params={'directory':directory,'media':'video','properties':['title','year','plot','runtime','genre','rating','art','thumbnail','playcount','resume'],'sort':{'method':'label','order':'ascending','ignorearticle':True}}
        response=json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc':'2.0','id':1,'method':'Files.GetDirectory','params':params})))
        diagnostics.append({'source':source,'request':params,'response':response})
    (OUT/'directory-rpc.json').write_text(json.dumps(diagnostics,indent=2)+'\n')
    xbmc.executebuiltin('ActivateWindow(Videos,'+ROOT+',return)')
    if SCENARIO=='empty':
        until('no-source guidance',lambda:xbmcgui.getCurrentWindowDialogId()==12002)
        dialog=xbmcgui.Window(12002)
        text=' '.join(xbmc.getInfoLabel('Control.GetLabel('+str(i)+')') for i in (1,9,10))
        # Dialog IDs 12002 and control 9 are native Kodi DialogOK, not a mock.
        try:
            text+=' '+dialog.getControl(9).getText()
        except (RuntimeError,AttributeError):
            pass
        if 'Add your existing movie folder' not in text:
            raise RuntimeError('No-source dialog did not contain setup guidance: '+text)
        capture('empty-sources-guidance')
        checks.append({'check':'no-sources-guidance','dialog':12002,'text':text})
        rpc('Input.Select')
        until('guidance dismissed',lambda:not xbmc.getCondVisibility('System.HasModalDialog'))
    else:
        until('cinematic movie view',cinematic)
        monitor.waitForAbort(.8)
        if SCENARIO=='multiple':
            focus('Archive'); capture('multiple-sources-archive')
            focus('Cinema'); capture('multiple-sources-choice')
            checks.append({'check':'multiple-sources-require-choice','labels':['Archive','Cinema']})
            rpc('Input.Select')
            until('selected source cinematic view',lambda:cinematic() and 'source=' in xbmc.getInfoLabel('Container.FolderPath'))
            monitor.waitForAbort(.6)
        focus('Amber Horizon')
        assert_art('Amber Horizon')
        root_path=xbmc.getInfoLabel('Container.FolderPath')
        capture('movies-cinematic-root')
        checks.append({'check':'source-opened-'+SCENARIO,'folder_path':root_path,'view':61,'label':xbmc.getInfoLabel('ListItem.Label')})
        # Exercise the real native context item and image picker, including Back
        # and repeat cancellation. No library scan or external image is used.
        import xbmcvfs
        choices=Path(xbmcvfs.translatePath('special://profile/addon_data/plugin.video.aperture.movies/posters'))
        for attempt in range(2):
            poster_context_action('Choose local poster...')
            until('native image picker', lambda: xbmc.getCondVisibility('Window.IsActive(filebrowser)'))
            if attempt == 0:
                capture('movies-local-poster-picker')
            rpc('Input.Back')
            wait_for_movie_idle('poster picker cancelled', root_path)
            focus('Amber Horizon')
            assert_art('Amber Horizon')
            if choices.exists() and list(choices.iterdir()):
                raise RuntimeError('Cancelled picker wrote a poster preference')
        poster_context_action('Use automatic poster')
        wait_for_movie_idle('poster reset returns to movies', root_path)
        focus('Amber Horizon'); assert_art('Amber Horizon')
        checks.append({'check':'native-poster-picker-cancel-repeat-and-reset','profile_writes':False})
        # Root entry must already show movie content in sole/default cases.
        if SCENARIO in ('single','default') and root_path.rstrip('/')!=ROOT.rstrip('/'):
            raise RuntimeError('Unexpected root navigation before automatic source listing: '+root_path)
        focus('Collections')
        rpc('Input.Select')
        until('nested folder',lambda:cinematic() and xbmc.getInfoLabel('Container.FolderPath')!=root_path)
        focus('Blue Meridian'); assert_art('Blue Meridian'); capture('movies-nested-folder')
        checks.append({'check':'folder-navigation','label':xbmc.getInfoLabel('ListItem.Label')})
        rpc('Input.Back')
        until('back to source',lambda:cinematic() and xbmc.getInfoLabel('Container.FolderPath')==root_path)
        focus('Amber Horizon'); capture('movies-back-to-source')
        checks.append({'check':'native-back-to-source','folder_path':root_path})
        rpc('Input.Select')
        until('native VideoPlayer playing',lambda:xbmc.Player().isPlayingVideo())
        monitor.waitForAbort(3)
        players=rpc('Player.GetActivePlayers')
        if not any(p['type']=='video' for p in players):
            raise RuntimeError('No native video player')
        playing=xbmc.Player().getPlayingFile()
        if Path(playing)!=RUNTIME/'movies/Amber Horizon.mkv':
            raise RuntimeError('Unexpected playback target '+playing)
        capture('movies-native-playback')
        # Frame evidence distinguishes visible playback from a player flag only.
        from PIL import Image, ImageStat
        rgb=ImageStat.Stat(Image.open(OUT/'movies-native-playback.png').convert('RGB')).mean
        if not (rgb[1]>35 and rgb[1]>rgb[0]*1.5 and rgb[1]>rgb[2]*1.3):
            raise RuntimeError('Expected original green fixture framebuffer, got '+str(rgb))
        checks.append({'check':'native-video-playback','players':players,'file':playing,'mean_rgb':rgb})
        rpc('Player.Stop',{'playerid':next(p['playerid'] for p in players if p['type']=='video')})
        until('native playback stopped',lambda:not xbmc.Player().isPlaying())
        until('return to cinematic view',cinematic)
        focus('Amber Horizon'); capture('movies-after-playback')
        checks.append({'check':'playback-stop-returns-to-source','view':61})
    if SCENARIO != 'empty':
        # Check the navigation strip, then explicitly enter local-library discovery.
        # Discover now opens the public online catalogue; this offline fixture
        # must not call a live provider or claim to test online results.
        # The isolated profile deliberately has no scanned movie catalogue.
        rpc('Input.Up')
        until('Discover navigation focused', lambda: xbmc.getInfoLabel('System.CurrentControl') == 'Discover')
        capture('movies-discovery-navigation')
        xbmc.executebuiltin('Container.Update(plugin://plugin.video.aperture.movies/?mode=discover)')
        until('empty catalogue guidance', lambda: xbmcgui.getCurrentWindowDialogId() == 12002)
        capture('movies-empty-catalogue')
        rpc('Input.Select')
        until('discover directory', lambda: cinematic() and 'mode=discover' in xbmc.getInfoLabel('Container.FolderPath'))
        discovery_path = xbmc.getInfoLabel('Container.FolderPath')
        # Explicit focus selects a control, not a URL or action result.
        for attempt in range(2):
            xbmc.executebuiltin('SetFocus(711)')
            until('Search focused', lambda: xbmc.getInfoLabel('System.CurrentControl') == 'Search')
            rpc('Input.Select')
            until('search keyboard', lambda: xbmc.getCondVisibility('Window.IsActive(virtualkeyboard)'))
            if attempt == 0:
                capture('movies-search-keyboard')
            rpc('Input.Back')
            wait_for_movie_idle('cancel search preserves directory', discovery_path)
        xbmc.executebuiltin('SetFocus(712)')
        rpc('Input.Select')
        until('collection chooser', lambda: xbmc.getCondVisibility('Window.IsActive(selectdialog)'))
        capture('movies-collections')
        rpc('Input.Back')
        wait_for_movie_idle('cancel collection preserves directory', discovery_path)
        # Validate filters against Kodi itself, rather than only the Python mocks.
        for field, operator, value in [('inprogress', 'true', ''), ('playcount', 'is', '0'), ('title', 'contains', 'Amber'), ('genre', 'is', 'Adventure')]:
            rpc('VideoLibrary.GetMovies', {'properties':['file','resume','dateadded'], 'filter':{'field':field,'operator':operator,'value':value}, 'limits':{'start':0,'end':60}})
        rpc('Input.Back')
        until('discovery Back returns to local files', lambda: cinematic() and xbmc.getInfoLabel('Container.FolderPath') == root_path)
        xbmc.executebuiltin('SetFocus(61)')
        focus('Amber Horizon'); assert_art('Amber Horizon')
        checks.append({'check':'local-library-search-cancel-repeat-collection-cancel-and-back','provider_calls':False,'populated_catalogue_tested':False,'online_catalogue_ui_tested':False})
    result={'status':'passed','scenario':SCENARIO,'checks':checks,'limitations':['Disposable x86_64 software-rendered Kodi 21.3 profile only','No physical Pi, remote controller, external drive, SMB or personal media validation','Artwork and video generated locally; no external media downloaded','Online catalogue UI is not exercised by this offline local-library fixture']}
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
except Exception as exc:
    try:
        capture('failure')
    except Exception:
        pass
    (OUT/'result.json').write_text(json.dumps({'status':'failed','scenario':SCENARIO,'reason':str(exc),'checks':checks,'traceback':traceback.format_exc()},indent=2)+'\n')
finally:
    xbmc.executebuiltin('Quit')


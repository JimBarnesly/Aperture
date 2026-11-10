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


def select_choice(label):
    until('selection dialog', lambda: xbmcgui.getCurrentWindowDialogId() == 12000)
    for _ in range(12):
        if xbmc.getInfoLabel('System.CurrentControl') == label:
            rpc('Input.Select')
            return
        rpc('Input.Down')
        monitor.waitForAbort(.15)
    raise RuntimeError('Missing selection choice: ' + label)


def movie_actions(choice):
    # Details now lead to another modal, not directly back to the listing.
    rpc('Input.Select')
    until('Movie actions', lambda: xbmcgui.getCurrentWindowDialogId() == 12000
          and xbmc.getInfoLabel('Control.GetLabel(1)') == 'Movie actions')
    until('Find streams action', lambda: xbmc.getInfoLabel('System.CurrentControl') == 'Find streams (Torrentio)')
    capture('online-movie-actions')
    select_choice(choice)


def source_consent():
    nav('Sources'); rpc('Input.Select')
    until('Sources selection',lambda:xbmcgui.getCurrentWindowDialogId()==12000)
    # New disconnected selection opens on its first item; verify before Select.
    until('Connect choice focused',lambda:xbmc.getInfoLabel('System.CurrentControl')=='Connect Real-Debrid')
    rpc('Input.Select')
    until('RD consent',lambda:xbmcgui.getCurrentWindowDialogId()==10100)
    text=xbmc.getInfoLabel('Control.GetLabel(9)')
    for phrase in ('shared open-source app','torrents','user information','Continue to storage consent?'):
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


def torrentio_journey(online_path):
    import xbmcvfs
    profile = Path(xbmcvfs.translatePath('special://profile/addon_data/plugin.video.aperture.movies'))
    connection = profile/'torrentio-private/connection'
    credentials = profile/'real-debrid-private/credentials.json'
    nav('Sources'); rpc('Input.Select')
    select_choice('Set up online playback (Torrentio)')
    until('Torrentio wizard', lambda: 'Set up online playback' in xbmc.getInfoLabel('Control.GetLabel(1)')
          and xbmcgui.getCurrentWindowDialogId() == 12000)
    capture('torrentio-wizard')
    select_choice('1. Connect with Real-Debrid (no token copying)')
    until('wizard storage consent', lambda: xbmcgui.getCurrentWindowDialogId() == 10100
          and 'Online playback' in xbmc.getInfoLabel('Control.GetLabel(1)'))
    text = xbmc.getInfoLabel('Control.GetLabel(9)')
    assert 'not encrypted' in text and 'No P2P' in text
    for phrase in ('automatically', 'history', 'transfer', 'traffic', 'signed URL', 'Choose source'):
        assert phrase in text
    capture('torrentio-storage-consent'); consent_choice(True)
    until('Share access with Torrentio', lambda: 'Share access with Torrentio' in xbmc.getInfoLabel('Control.GetLabel(1)'))
    text = xbmc.getInfoLabel('Control.GetLabel(9)')
    for phrase in ('torrentio.strem.fun', 'access token', 'movie IDs', 'Never share refresh tokens'):
        assert phrase in text
    assert not connection.exists() and not credentials.exists()
    assert 'fake-token-exchange' not in events()
    capture('torrentio-sharing-consent'); consent_choice(True)
    until('wizard device consent', lambda: xbmcgui.getCurrentWindowDialogId() == 10100
          and xbmc.getInfoLabel('Control.GetLabel(1)') == 'Real-Debrid sign-in')
    assert 'official shared open-source' in xbmc.getInfoLabel('Control.GetLabel(9)')
    consent_choice(True)
    until('wizard synthetic device progress', lambda: xbmcgui.getCurrentWindowDialogId() == 10101)
    capture('torrentio-device-approval')
    # Simulate server approval only, never write credentials or a connection marker.
    # The real wizard/device client must exchange and persist the synthetic grant.
    (OUT/'approve-synthetic-device').touch()
    until('wizard completed', lambda: xbmcgui.getCurrentWindowDialogId() == 12002
          and xbmc.getInfoLabel('Control.GetLabel(1)') == 'Online playback enabled')
    assert connection.read_text() == 'rd-oauth-v1' and credentials.is_file()
    assert connection.stat().st_mode & 0o777 == 0o600
    assert credentials.stat().st_mode & 0o777 == 0o600
    assert events().count('fake-token-exchange') == 1
    assert not any(event.startswith('torrentio-') for event in events())
    capture('torrentio-enabled'); rpc('Input.Select')
    wait_for_movie_idle('wizard returns to browsing', online_path)
    checks.append({'check':'native-torrentio-wizard-device-approval', 'synthetic_grant':True, 'setup_provider_calls':False})

    nav('Sources'); rpc('Input.Select')
    select_choice('Set up online playback (Torrentio)')
    until('saved wizard', lambda: 'Set up online playback' in xbmc.getInfoLabel('Control.GetLabel(1)'))
    select_choice('Check saved connection (no playback)')
    until('connection check consent', lambda: xbmcgui.getCurrentWindowDialogId() == 10100)
    consent_choice(True)
    until('manifest response', lambda: xbmcgui.getCurrentWindowDialogId() == 12002
          and xbmc.getInfoLabel('Control.GetLabel(1)') == 'Provider responded')
    assert events().count('torrentio-manifest') == 1
    assert 'not verified' in xbmc.getInfoLabel('Control.GetLabel(9)')
    capture('torrentio-check'); rpc('Input.Select')
    wait_for_movie_idle('connection check returns', online_path)

    nav('Search'); rpc('Input.Select')
    until('native search keyboard', lambda: xbmc.getCondVisibility('Window.IsActive(virtualkeyboard)'))
    rpc('Input.SendText', {'text':'Synthetic Online Horizon', 'done':True})
    until('native search results', lambda: cinematic() and 'search=' in xbmc.getInfoLabel('Container.FolderPath'))
    search_path = xbmc.getInfoLabel('Container.FolderPath')
    assert 'catalogue-search' in events()
    rpc('Input.Down'); focus('Synthetic Online Horizon')
    capture('torrentio-search-results')

    # Manual chooser cancellation must never resolve, then Select auto-plays.
    focus('Synthetic Online Horizon')
    poster_context_action('Choose source')
    until('Choose a source', lambda: xbmcgui.getCurrentWindowDialogId() == 12000
          and 'Choose a source' in xbmc.getInfoLabel('Control.GetLabel(1)'))
    source = xbmc.getInfoLabel('System.CurrentControl')
    assert source.startswith('1. Real-Debrid') and '1080p' in source
    capture('torrentio-source-cancel')
    assert 'torrentio-resolve' not in events()
    rpc('Input.Back')
    wait_for_movie_idle('source cancellation preserves search', search_path)
    assert 'torrentio-resolve' not in events() and not xbmc.Player().isPlaying()
    focus('Synthetic Online Horizon')
    rpc('Input.Select')
    until('automatic movie selection', lambda: xbmc.Player().isPlayingVideo())
    until('Torrentio native VideoPlayer', lambda: xbmc.Player().isPlayingVideo())
    monitor.waitForAbort(3)
    players = rpc('Player.GetActivePlayers')
    assert any(p['type'] == 'video' for p in players)
    playing = xbmc.Player().getPlayingFile()
    assert Path(playing) == RUNTIME/'movies/Amber Horizon.mkv'
    assert events().count('torrentio-streams') == 3  # Manual lookup + automatic lookup + playback refetch.
    assert events().count('torrentio-resolve') == 1
    assert events().count('torrentio-local-handoff') == 1
    capture('torrentio-native-playback')
    from PIL import Image, ImageStat
    rgb = ImageStat.Stat(Image.open(OUT/'torrentio-native-playback.png').convert('RGB')).mean
    assert rgb[1] > 35 and rgb[1] > rgb[0]*1.5 and rgb[1] > rgb[2]*1.3
    checks.append({'check':'native-torrentio-search-manual-cancel-auto-play', 'players':players,
                   'file':playing, 'mean_rgb':rgb, 'synthetic_transport':True, 'real_provider_calls':False})
    rpc('Player.Stop', {'playerid':next(p['playerid'] for p in players if p['type'] == 'video')})
    until('Torrentio playback stopped', lambda: not xbmc.Player().isPlaying())
    wait_for_movie_idle('Torrentio playback returns to search', search_path)
    assert 'unexpected-provider-operation' not in events()
    capture('torrentio-return-search')


def history_journey():
    import xbmcvfs
    path = Path(xbmcvfs.translatePath('special://profile/addon_data/plugin.video.aperture.movies/history-private/history.json'))
    def rows():
        return json.loads(path.read_text())['records'] if path.exists() else {}
    until('actual playback persisted', lambda: 'tt1234567' in rows())
    position = rows()['tt1234567']['resume_seconds']
    assert position > 0
    assert set(rows()['tt1234567']) == {'id', 'title', 'year', 'genres', 'resume_seconds', 'duration_seconds', 'lastplayed', 'completed'}
    nav('Collections'); rpc('Input.Select'); select_choice('Continue watching')
    until('continue watching', lambda: cinematic() and 'mode=continue' in xbmc.getInfoLabel('Container.FolderPath'))
    rpc('Input.Down'); focus('Synthetic Online Horizon · Resume')
    before = events().count('torrentio-resolve')
    rpc('Input.Select')
    until('explicit history Resume', lambda: xbmc.Player().isPlayingVideo())
    until('resumed position', lambda: xbmc.Player().getTime() >= position)
    assert events().count('torrentio-resolve') == before + 1
    until('fullscreen resume', lambda: xbmcgui.getCurrentWindowId() == 12005)
    rpc('Input.Back')
    until('Back pauses movie', lambda: cinematic() and xbmc.getCondVisibility('Player.Paused'))
    nav('Collections'); rpc('Input.Select'); select_choice('History')
    until('history directory', lambda: cinematic() and 'mode=history' in xbmc.getInfoLabel('Container.FolderPath'))
    rpc('Input.Down'); focus('Clear history'); rpc('Input.Select')
    until('clear confirmation', lambda: xbmcgui.getCurrentWindowDialogId() == 10100)
    consent_choice(False)
    until('clear declined', cinematic)
    assert rows()
    focus('Clear history'); rpc('Input.Select')
    until('clear confirmation again', lambda: xbmcgui.getCurrentWindowDialogId() == 10100)
    consent_choice(True)
    until('history cleared', lambda: cinematic() and not rows())
    assert xbmc.Player().isPlayingVideo() and xbmc.getCondVisibility('Player.Paused')
    monitor.waitForAbort(22)
    assert not rows(), 'Active session must not repopulate cleared history'
    rpc('Player.Stop', {'playerid': 1})
    until('resumed video stopped', lambda: not xbmc.Player().isPlaying())
    assert not rows()
    nav('Collections'); rpc('Input.Select'); select_choice('Suggested for you')
    until('local suggestion fallback', lambda: cinematic() and 'mode=suggested' in xbmc.getInfoLabel('Container.FolderPath'))
    assert 'catalogue suggestions only' in xbmc.getInfoLabel('Container.PluginCategory')
    capture('history-cleared-suggestions')
    checks.append({'check': 'history-record-fresh-resolve-resume-back-pause-clear-suggestions',
                   'synthetic_transport': True, 'cleared_session_stayed_empty': True})


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
    poster_context_action('Movie details (Cinemeta)')
    until('online details',lambda:xbmcgui.getCurrentWindowDialogId()==12002)
    text=xbmc.getInfoLabel('Control.GetLabel(9)')
    assert 'Playback availability not checked' in text
    capture('online-details'); movie_actions('Back to browsing')
    wait_for_movie_idle('details dismissed without history change',online_path)
    checks.append({'check':'online-catalogue-and-details','synthetic_provider':True})
    for label,dialog in [('Search','virtualkeyboard'),('Search','virtualkeyboard'),('Collections','selectdialog'),('Genres','selectdialog')]:
        nav(label); rpc('Input.Select')
        until(label+' dialog',lambda:xbmc.getCondVisibility('Window.IsActive('+dialog+')'))
        capture('online-'+label.lower())
        rpc('Input.Back'); wait_for_movie_idle('cancel '+label,online_path)
    checks.append({'check':'online-search-repeat-collection-genre-cancel','history_preserved':True})
    for stage, back in ((1,False),(1,True),(2,False),(2,True)):
        text=source_consent()
        if stage == 2:
            consent_choice(True)
            until('storage consent',lambda:'Same-user apps' in xbmc.getInfoLabel('Control.GetLabel(9)'))
            text=xbmc.getInfoLabel('Control.GetLabel(9)')
            for phrase in ('refresh credentials','OS user','not encrypted','Same-user apps','backups','Connect?'):
                assert phrase in text
        capture('rd-consent-stage-'+str(stage)+('-back' if back else '-no'))
        assert 'fake-device-code' not in events()
        if back:
            rpc('Input.Back')
        else:
            consent_choice(False)
        wait_for_movie_idle('RD staged decline/back',online_path)
        assert 'fake-device-code' not in events()
    checks.append({'check':'RD-both-consent-stages-No-and-Back','provider_calls':False})
    source_consent(); consent_choice(True)
    until('storage consent before fake request',lambda:'Same-user apps' in xbmc.getInfoLabel('Control.GetLabel(9)'))
    assert 'fake-device-code' not in events()
    consent_choice(True)
    until('fake device progress',lambda:xbmcgui.getCurrentWindowDialogId()==10101)
    capture('rd-fake-device-progress')
    assert events().count('fake-device-code')==1
    until('first fake pending poll',lambda:'fake-pending' in events(),10)
    rpc('Input.Back')
    wait_for_movie_idle('cancel fake device progress',online_path)
    import xbmcvfs
    private=Path(xbmcvfs.translatePath('special://profile/addon_data/plugin.video.aperture.movies/real-debrid-private'))
    assert not (private/'credentials.json').exists()
    assert 'unexpected-provider-operation' not in events()
    stopped_events = events()
    monitor.waitForAbort(6)
    assert events() == stopped_events
    checks.append({'check':'RD-fake-device-cancel-after-first-poll','real_provider_calls':False,'credentials_saved':False})
    torrentio_journey(online_path)
    history_journey()
    nav('Local files'); rpc('Input.Select')
    until('return to local files',lambda:cinematic() and xbmc.getInfoLabel('Container.FolderPath')==local_path)
    rpc('Input.Down')
    focus('Amber Horizon'); capture('online-return-local')
    checks.append({'check':'controller-navigation-return-local'})
    result={'status':'passed','scenario':'online','checks':checks,'limitations':['Native Kodi 21.3 software-rendered CI only; not physical controller/Pi acceptance','Synthetic catalogue/RD/Torrentio transports and fake token exchange; no live account or usable grant. Validated resolver output maps only to generated local video, not real CDN playback','Screenshots require visual review for disclosure readability']}
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
except Exception as exc:
    try: capture('failure')
    except Exception: pass
    (OUT/'result.json').write_text(json.dumps({'status':'failed','scenario':'online','reason':str(exc),'checks':checks,'traceback':traceback.format_exc()},indent=2)+'\n')
finally:
    xbmc.executebuiltin('Quit')

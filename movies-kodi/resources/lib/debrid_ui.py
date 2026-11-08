"""Opt-in Kodi adapter. Account access only follows explicit Sources actions."""
import time
from urllib.parse import urlencode
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.debrid import Client, Store, DebridError, PAGE_SIZE, secret


def run(query, addon, profile, base, handle):
    action = query.get('action', [''])[0]
    store = Store(profile)
    dialog = xbmcgui.Dialog()
    playback = action == 'rd_play'
    directory = query.get('mode', [''])[0] == 'rd' and not action
    navigate = False
    try:
        with store.locked():
            client = Client(store)
            if playback:
                item_id = secret(query.get('id', [''])[0])
                page = int(query.get('page', ['1'])[0])
                path = client.playback(item_id, page)
                item = xbmcgui.ListItem(path=path)
                xbmcplugin.setResolvedUrl(handle, True, item)
                return
            if directory:
                page = int(query.get('page', ['1'])[0])
                entries = client.downloads(page)
                xbmcplugin.setContent(handle, 'movies')
                xbmcplugin.setPluginCategory(handle, 'Real-Debrid downloads')
                count = 0
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    try:
                        item_id = secret(entry.get('id'))
                    except DebridError:
                        continue
                    label = entry.get('filename')
                    if not isinstance(label, str) or not label.lower().endswith(('.mkv', '.mp4', '.avi', '.mov', '.m4v', '.webm', '.ts')):
                        continue
                    li = xbmcgui.ListItem(label=label)
                    li.setProperty('IsPlayable', 'true')
                    li.setProperty('Aperture.MovieFolder', 'false')
                    li.setArt({'icon': 'DefaultVideo.png'})
                    route = base + '?' + urlencode({'action': 'rd_play', 'id': item_id, 'page': page})
                    xbmcplugin.addDirectoryItem(handle, route, li, False)
                    count += 1
                if len(entries) == PAGE_SIZE and page < 10000:
                    li = xbmcgui.ListItem(label='More downloads')
                    li.setProperty('Aperture.MovieFolder', 'true')
                    xbmcplugin.addDirectoryItem(handle, base + '?' + urlencode({'mode': 'rd', 'page': page + 1}), li, True)
                if not count:
                    dialog.ok('Real-Debrid', 'No video downloads on this page. This lists existing account downloads, not an online movie catalogue.')
                xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
                return
            if action != 'providers':
                raise DebridError('invalid')
            origin = xbmc.getInfoLabel('Container.FolderPath')
            connected = store.load() is not None
            choices = (['Browse existing downloads', 'Play a link I am authorized to use', 'Disconnect from this profile']
                       if connected else ['Connect Real-Debrid', 'Configure application client ID'])
            selected = dialog.select('Movie sources: Real-Debrid' + (' connected' if connected else ' not connected'), choices)
            if selected < 0 or xbmc.getInfoLabel('Container.FolderPath') != origin:
                return
            if connected and selected == 0:
                navigate = True
            elif connected and selected == 1:
                link = dialog.input('HTTPS link you are authorized to play')
                if not link or not dialog.yesno('Resolve with Real-Debrid?', 'Send this link to Real-Debrid and play it? This can use your account traffic and add a download-history entry. Only use content you have permission to access.'):
                    return
                if xbmc.getInfoLabel('Container.FolderPath') != origin:
                    return
                path = client.resolve_link(link.strip())
                xbmc.Player().play(path)
            elif connected and selected == 2:
                if dialog.yesno('Disconnect Real-Debrid?', 'Remove saved credentials from this Kodi profile? To revoke the server-side grant too, remove Aperture in your Real-Debrid account applications.'):
                    store.clear()
                    dialog.ok('Real-Debrid', 'Local credentials removed. Revoke the application on Real-Debrid to remove its server-side access.')
            elif not connected and selected == 1:
                addon.openSettings()
            elif not connected and selected == 0:
                client_id = addon.getSetting('rd_client_id').strip()
                if not client_id:
                    raise DebridError('config')
                if not dialog.yesno('Connect Real-Debrid?', 'Authorize Aperture on Real-Debrid to access your account downloads and resolve links you choose. Save refresh credentials in this profile, restricted to your OS user (not encrypted). Other apps running as you and profile backups may read them. Continue?'):
                    return
                session = client.begin(client_id)
                progress = xbmcgui.DialogProgress()
                monitor = xbmc.Monitor()
                progress.create('Connect Real-Debrid', 'Open https://real-debrid.com/device\nEnter code: ' + session['user_code'] + '\nApprove Aperture there, or Cancel here.')
                def cancelled():
                    return (progress.iscanceled() or monitor.abortRequested()
                            or xbmc.getInfoLabel('Container.FolderPath') != origin)
                def wait(seconds):
                    deadline = time.monotonic() + seconds
                    while time.monotonic() < deadline:
                        if cancelled() or monitor.waitForAbort(min(0.1, max(0, deadline - time.monotonic()))):
                            return True
                    return False
                try:
                    client.connect(session, wait, cancelled)
                finally:
                    progress.close()
                dialog.ok('Real-Debrid', 'Connected. Sources can now browse existing downloads or play an authorized link. Online catalogue search is separate.')
        if navigate:
            xbmc.executebuiltin('Container.Update(' + base + '?mode=rd)')
    except (DebridError, OSError, ValueError):
        # Never expose filesystem paths, credentials, signed URLs or raw errors.
        import sys
        error = sys.exc_info()[1]
        message = str(error) if isinstance(error, DebridError) else 'Real-Debrid could not complete this action. Check your private profile storage and try again.'
        if not isinstance(error, DebridError) or error.kind != 'cancelled':
            dialog.ok('Real-Debrid', message)
        if playback:
            xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
        elif directory:
            xbmcplugin.endOfDirectory(handle, succeeded=False, cacheToDisc=False)

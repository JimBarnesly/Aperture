"""Aperture local movies: browse existing Kodi sources, never alter media."""
import json
import sys
import traceback
from urllib.parse import parse_qs, urlencode, urlsplit
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from resources.lib.library import select_source, default_from_xml, within_source, display_title, artwork
from resources.lib.posters import read_choice, save_choice, reset_choice

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE = sys.argv[0]


def rpc(method, params=None):
    result = json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})))
    if 'error' in result:
        raise RuntimeError('Kodi source RPC error code '+str(result['error'].get('code', 'unknown')))
    return result.get('result', {})


def read_default():
    p = xbmcvfs.translatePath('special://profile/sources.xml')
    try:
        f = xbmcvfs.File(p)
        try: return default_from_xml(f.read())
        finally: f.close()
    except Exception:
        return ''


def end(ok=True):
    xbmcplugin.endOfDirectory(HANDLE, succeeded=ok, cacheToDisc=False)


def poster_profile():
    return xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))


def poster_action(action, target, root):
    extensions = tuple(ext for ext in xbmc.getSupportedMedia('video').lower().split('|') if ext)
    if (not within_source(target, root) or target == root
            or not target.lower().endswith(extensions)):
        xbmcgui.Dialog().ok('Movie poster', 'Select a movie in the configured video source.')
        return
    if action not in ('choose_poster', 'reset_poster'):
        return
    origin = xbmc.getInfoLabel('Container.FolderPath')
    try:
        if action == 'choose_poster':
            picture = xbmcgui.Dialog().browseSingle(
                2, 'Choose a local movie poster', 'pictures', '.jpg|.jpeg|.png|.webp', True)
            if not picture:
                return
            save_choice(poster_profile(), target, picture)
        else:
            reset_choice(poster_profile(), target)
    except (OSError, ValueError):
        xbmcgui.Dialog().ok('Movie poster', 'Could not save the poster choice. Choose an existing local JPEG, PNG or WebP image and check that the Kodi profile is writable.')
        return
    # Never refresh a newer destination if navigation changed during the picker.
    current = xbmc.getInfoLabel('Container.FolderPath')
    if (current == origin and urlsplit(current).netloc == urlsplit(BASE).netloc
            and not xbmc.getCondVisibility('System.HasModalDialog')):
        xbmc.executebuiltin('Container.Refresh')


def local_art_exists(path):
    try:
        return xbmcvfs.exists(path)
    except Exception:
        return False



def apply_cinema_view():
    """Wait briefly for this directory, never change a different window's view."""
    expected = urlsplit(BASE + sys.argv[2])
    def same_directory(current):
        actual = urlsplit(current)
        return (actual.scheme == expected.scheme and actual.netloc == expected.netloc
                and actual.path.rstrip('/') == expected.path.rstrip('/')
                and parse_qs(actual.query, keep_blank_values=True)
                == parse_qs(expected.query, keep_blank_values=True))
    monitor = xbmc.Monitor()
    for _ in range(60):
        if monitor.abortRequested():
            return
        if (same_directory(xbmc.getInfoLabel('Container.FolderPath'))
                and not xbmc.getCondVisibility('System.HasModalDialog')
                and not xbmc.getCondVisibility('Window.IsActive(busydialog)')
                and not xbmc.getCondVisibility('Window.IsActive(busydialognocancel)')):
            xbmc.executebuiltin('Container.SetViewMode(61)')
            return
        if monitor.waitForAbort(0.05):
            return


def main():
    query = parse_qs(sys.argv[2].lstrip('?'))
    action = query.get('action', [''])[0]
    if not action:
        xbmcplugin.setContent(HANDLE, 'movies')
        xbmcplugin.setPluginCategory(HANDLE, 'Movies')
    sources = rpc('Files.GetSources', {'media': 'video'}).get('sources', [])
    sources = [s for s in sources if s.get('file') and not s['file'].startswith('plugin://')]
    if not sources:
        xbmcgui.Dialog().ok('Movies', 'Add your existing movie folder in Kodi → Videos → Files → Add videos, then return here.')
        if not action:
            end()
        return
    root = query.get('source', [''])[0]
    chosen = next((s for s in sources if s['file'] == root), None) if root else select_source(sources, read_default())
    if action:
        if chosen is not None and root == chosen['file']:
            poster_action(action, query.get('movie', [''])[0], root)
        return
    if chosen is None:
        # Multiple sources require one explicit choice; do not guess or persist it.
        for s in sources:
            li = xbmcgui.ListItem(label=s.get('label') or 'Video source')
            li.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
            li.setProperty('Aperture.MovieFolder', 'true')
            xbmcplugin.addDirectoryItem(HANDLE, BASE+'?'+urlencode({'source': s['file'], 'path': s['file']}), li, True)
        end(); apply_cinema_view(); return
    root = chosen['file']
    path = query.get('path', [root])[0]
    if not within_source(path, root):
        xbmcgui.Dialog().ok('Movies', 'That folder is outside the selected video source.')
        end(False); return
    properties = ['title', 'year', 'plot', 'runtime', 'genre', 'rating', 'art', 'thumbnail', 'playcount', 'resume']
    try:
        result = rpc('Files.GetDirectory', {'directory': path, 'media': 'video', 'properties': properties, 'sort': {'method': 'label', 'order': 'ascending', 'ignorearticle': True}})
        items = result.get('files', [])
    except RuntimeError:
        # JSON-RPC can refuse a saved source with allowsharing=false. Local VFS
        # browsing does not enable sharing or expose that source over the network.
        if not xbmcvfs.exists(path):
            raise RuntimeError('Source unavailable')
        folders, files = xbmcvfs.listdir(path)
        extensions = tuple(ext for ext in xbmc.getSupportedMedia('video').lower().split('|') if ext)
        prefix = path.rstrip('/')+'/'
        items = [{'file': prefix+n+'/', 'label': n, 'filetype': 'directory'} for n in folders]
        items += [{'file': prefix+n, 'label': n, 'filetype': 'file'} for n in files if n.lower().endswith(extensions)]
        items.sort(key=lambda item: item['label'].casefold())
    xbmcplugin.setPluginCategory(HANDLE, chosen.get('label') or 'Movies')
    # A shared directory's poster.jpg must not become every film's identity.
    single_movie = sum(1 for item in items if item.get('filetype') != 'directory'
                       and item.get('file')) == 1
    for item in items:
        directory = item.get('filetype') == 'directory'
        target = item.get('file', '')
        if not target:
            continue
        li = xbmcgui.ListItem(label=display_title(item), path=target)
        art = dict(item.get('art') or {})
        if item.get('thumbnail'):
            art.setdefault('thumb', item['thumbnail'])
        if not directory:
            art = artwork(item, local_art_exists, include_folder=single_movie,
                          poster=read_choice(poster_profile(), target))
            li.addContextMenuItems([
                (label, 'RunPlugin('+BASE+'?'+urlencode({'source': root, 'movie': target, 'action': action})+')')
                for label, action in [('Choose local poster...', 'choose_poster'),
                                      ('Use automatic poster', 'reset_poster')]])
            li.setInfo('video', {k: item[k] for k in ('title','year','plot','genre','rating','playcount') if item.get(k) is not None})
            if item.get('runtime'):
                li.getVideoInfoTag().setDuration(int(item['runtime']))
            li.setProperty('IsPlayable', 'true')
            li.setProperty('Aperture.MovieFolder', 'false')
        else:
            li.setProperty('Aperture.MovieFolder', 'true')
        art.setdefault('icon', 'DefaultFolder.png' if directory else 'DefaultVideo.png')
        li.setArt(art)
        url = BASE+'?'+urlencode({'source': root, 'path': target}) if directory else target
        xbmcplugin.addDirectoryItem(HANDLE, url, li, directory)
    if not items:
        xbmcgui.Dialog().notification('Movies', 'No videos in this folder, or the drive is unavailable.', time=4000)
    end()
    # New plugin view only; native Kodi windows retain their saved view choices.
    apply_cinema_view()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Paths may contain credentials. Never put remote URLs or exception values in logs.
        frames = traceback.extract_tb(error.__traceback__)
        location = frames[-1].lineno if frames else 0
        xbmc.log('Aperture Movies: source listing failed ('+type(error).__name__+', line '+str(location)+')', xbmc.LOGERROR)
        xbmcgui.Dialog().ok('Movies', 'Could not read the movie source. Check that the drive is connected and available in Kodi.')
        end(False)

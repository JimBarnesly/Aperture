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
from resources.lib.discovery import request as discovery_request, COLLECTIONS
from resources.lib import catalog

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


def discovery_action(action):
    """Modal controls are actions, not folders: cancel must not alter Back history."""
    origin = xbmc.getInfoLabel('Container.FolderPath')
    parsed = urlsplit(origin)
    if parsed.netloc != urlsplit(BASE).netloc:
        return
    query = parse_qs(parsed.query)
    if query.get('mode', [''])[0] == 'online' and action != 'providers':
        online_action(action, query, origin)
        return
    _, state, _ = discovery_request(query)
    if action == 'search':
        value = xbmcgui.Dialog().input('Search your Kodi movie library', defaultt=state.get('search', ''))
        if not value or not value.strip():
            return
        state['search'] = value.strip()[:200]
    elif action == 'collection':
        selected = xbmcgui.Dialog().select('Discover your movies', [label for _, label in COLLECTIONS])
        if selected < 0 or selected >= len(COLLECTIONS):
            return
        state['collection'] = COLLECTIONS[selected][0]
    elif action == 'genre':
        try:
            genres = rpc('VideoLibrary.GetGenres', {'type': 'movie'}).get('genres', [])
        except RuntimeError:
            xbmcgui.Dialog().ok('Genres', 'Could not read genres from the Kodi library. Local files remain available.')
            return
        labels = sorted({g.get('label') for g in genres if isinstance(g.get('label'), str) and g['label']})
        selected = xbmcgui.Dialog().select('Genre', ['All genres'] + labels)
        if selected < 0 or selected > len(labels):
            return
        state.pop('genre', None)
        if selected:
            state['genre'] = labels[selected - 1]
    elif action == 'providers':
        from resources.lib.debrid_ui import run
        run({'action': ['providers']}, ADDON, poster_profile(), BASE, HANDLE)
        return
    else:
        return
    if (xbmc.getInfoLabel('Container.FolderPath') == origin
            and not xbmc.getCondVisibility('System.HasModalDialog')):
        xbmc.executebuiltin('Container.Update(' + BASE + '?' + urlencode(state) + ')')


def discover(query):
    params, state, heading = discovery_request(query)
    xbmcplugin.setContent(HANDLE, 'movies')
    xbmcplugin.setPluginCategory(HANDLE, heading)
    try:
        result = rpc('VideoLibrary.GetMovies', params)
    except RuntimeError:
        xbmcgui.Dialog().ok('Discover', 'The Kodi movie library is unavailable. Your local movie folders are still available from Local files.')
        end(False)
        return
    movies = result.get('movies', [])
    for movie in movies:
        target = movie.get('file')
        if not target:
            continue
        li = xbmcgui.ListItem(label=display_title(movie), path=target)
        li.setInfo('video', {key: movie[key] for key in ('title', 'year', 'plot', 'genre', 'rating', 'playcount') if movie.get(key) is not None})
        if movie.get('runtime'):
            li.getVideoInfoTag().setDuration(int(movie['runtime']))
        # Kodi's DB identity preserves native Information/Resume/mark-watched actions.
        if isinstance(movie.get('movieid'), int):
            li.getVideoInfoTag().setDbId(movie['movieid'])
            li.getVideoInfoTag().setMediaType('movie')
        resume = movie.get('resume') or {}
        if resume.get('position', 0) > 0:
            li.getVideoInfoTag().setResumePoint(resume['position'], resume.get('total', 0))
        li.setProperty('IsPlayable', 'true')
        li.setProperty('Aperture.MovieFolder', 'false')
        li.setArt(artwork(movie, local_art_exists, poster=read_choice(poster_profile(), target)))
        li.addContextMenuItems([('Movie information', 'Action(Info)')])
        xbmcplugin.addDirectoryItem(HANDLE, target, li, False)
    limits = result.get('limits') or {}
    next_start = limits.get('end', 0)
    if isinstance(next_start, int) and next_start > params['limits']['start'] and next_start < limits.get('total', 0):
        state['start'] = next_start
        li = xbmcgui.ListItem(label='More movies')
        li.setArt({'icon': 'DefaultFolder.png'})
        li.setProperty('Aperture.MovieFolder', 'true')
        xbmcplugin.addDirectoryItem(HANDLE, BASE + '?' + urlencode(state), li, True)
    if not movies:
        message = ('No matches. Try another title, collection or genre.' if state.get('search') or state.get('genre') or state['collection'] != 'all'
                   else 'Your Kodi movie library is empty. Use Local files to browse existing folders, or add movies to the library in Kodi. Use Discover for online catalogue browsing.')
        xbmcgui.Dialog().ok('Discover', message)
    end()
    apply_cinema_view()


def online_action(action, query, origin):
    state = catalog.state(query)
    state.pop('start', None)
    if action == 'search':
        value = xbmcgui.Dialog().input('Search online movies (Cinemeta)', defaultt=state.get('search', ''))
        if not value or not value.strip():
            return
        state.update(search=value.strip()[:200], collection='top')
    elif action == 'collection':
        selected = xbmcgui.Dialog().select('Movie collections', [label for _, label in catalog.COLLECTIONS] + ['My Kodi library'])
        if selected < 0 or selected > len(catalog.COLLECTIONS):
            return
        state = ({'mode': 'discover'} if selected == len(catalog.COLLECTIONS)
                 else {'mode': 'online', 'collection': catalog.COLLECTIONS[selected][0]})
    elif action == 'genre':
        selected = xbmcgui.Dialog().select('Online genre', ['All genres'] + list(catalog.GENRES))
        if selected < 0 or selected > len(catalog.GENRES):
            return
        state.pop('genre', None)
        if selected:
            state['genre'] = catalog.GENRES[selected - 1]
    else:
        return
    if (xbmc.getInfoLabel('Container.FolderPath') == origin
            and not xbmc.getCondVisibility('System.HasModalDialog')):
        xbmc.executebuiltin('Container.Update(' + BASE + '?' + urlencode(state) + ')')


def online(query):
    xbmcplugin.setContent(HANDLE, 'movies')
    try:
        movies, state, next_start = catalog.browse(query)
    except catalog.CatalogError:
        xbmcgui.Dialog().ok('Online movies', 'Cinemeta is unavailable. Try Discover again later, or use Local files. No playback availability has been checked.')
        end(False)
        return
    heading = dict(catalog.COLLECTIONS)[state['collection']]
    if state.get('search'):
        heading += ' · ' + state['search']
    if state.get('genre'):
        heading += ' · ' + state['genre']
    xbmcplugin.setPluginCategory(HANDLE, heading + ' · Cinemeta')
    for movie in movies:
        li = xbmcgui.ListItem(label=movie['title'])
        li.setInfo('video', {'title': movie['title'], 'plot': movie['plot'], 'genre': movie['genre']})
        li.setArt({'poster': movie['poster'], 'thumb': movie['poster'], 'fanart': movie['fanart'], 'icon': 'DefaultVideo.png'})
        li.setProperty('IsPlayable', 'false')
        li.setProperty('Aperture.MovieFolder', 'false')
        li.setProperty('Aperture.Availability', 'Not checked')
        route = BASE + '?' + urlencode({'action': 'online_details', 'id': movie['id']})
        match_route = BASE + '?' + urlencode({'mode': 'rd', 'imdb': movie['id']})
        stream_route = BASE + '?' + urlencode({'action': 'torrentio_find', 'id': movie['id']})
        li.addContextMenuItems([('Movie details (Cinemeta)', 'RunPlugin(' + route + ')'),
                                ('Find streams (Torrentio)', 'RunPlugin(' + stream_route + ')'),
                                ('Check my Real-Debrid downloads (filename IMDb ID)', 'Container.Update(' + match_route + ')')])
        xbmcplugin.addDirectoryItem(HANDLE, route, li, False)
    if next_start is not None:
        state['start'] = next_start
        li = xbmcgui.ListItem(label='More online movies')
        li.setProperty('Aperture.MovieFolder', 'true')
        li.setArt({'icon': 'DefaultFolder.png'})
        xbmcplugin.addDirectoryItem(HANDLE, BASE + '?' + urlencode(state), li, True)
    if not movies:
        xbmcgui.Dialog().ok('Online movies', 'No more results. Try another title or genre, or return to Discover.')
    end()
    apply_cinema_view()


def online_details(query):
    origin = xbmc.getInfoLabel('Container.FolderPath')
    try:
        movie = catalog.details(catalog.value(query, 'id'))
    except catalog.CatalogError:
        xbmcgui.Dialog().ok('Movie details', 'Online details are unavailable. Try again later.')
        return
    summary = ' · '.join(filter(None, [movie['year'], ', '.join(movie['genre']),
                            ('IMDb ' + movie['rating']) if movie['rating'] else '']))
    xbmcgui.Dialog().ok(movie['title'], summary + '\n\n' + movie['plot'] +
                       '\n\nMetadata: Cinemeta. Playback availability not checked. This catalogue does not supply streams.')
    if xbmc.Monitor().abortRequested() or xbmc.getInfoLabel('Container.FolderPath') != origin:
        return
    selected = xbmcgui.Dialog().select('Movie actions', ['Find streams (Torrentio)', 'Set up online playback', 'Back to browsing'])
    if xbmc.Monitor().abortRequested() or xbmc.getInfoLabel('Container.FolderPath') != origin:
        return
    if selected == 0:
        route = BASE + '?' + urlencode({'action': 'torrentio_find', 'id': movie['id']})
        xbmc.executebuiltin('RunPlugin(' + route + ')')
    elif selected == 1:
        xbmc.executebuiltin('RunPlugin(' + BASE + '?action=torrentio_setup)')


def main():
    query = parse_qs(sys.argv[2].lstrip('?'))
    action = query.get('action', [''])[0]
    if action in ('torrentio_setup', 'torrentio_find'):
        from resources.lib.torrentio_ui import run
        run(query, poster_profile(), BASE, HANDLE)
        return
    if action == 'rd_play' or query.get('mode', [''])[0] == 'rd':
        from resources.lib.debrid_ui import run
        run(query, ADDON, poster_profile(), BASE, HANDLE)
        return
    if action == 'online_details':
        online_details(query)
        return
    if query.get('mode', [''])[0] == 'online' and not action:
        online(query)
        return
    if action in ('search', 'collection', 'genre', 'providers'):
        discovery_action(action)
        return
    if query.get('mode', [''])[0] == 'discover':
        discover(query)
        return
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


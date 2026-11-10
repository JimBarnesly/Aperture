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
    if query.get('mode', [''])[0] in ('online', 'history', 'continue', 'suggested') and action != 'providers':
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
        extra = [('discover', 'My Kodi library'), ('history', 'History'),
                 ('continue', 'Continue watching'), ('suggested', 'Suggested for you')]
        labels = [label for _, label in catalog.COLLECTIONS] + [label for _, label in extra]
        selected = xbmcgui.Dialog().select('Movie collections', labels)
        if selected < 0 or selected >= len(labels):
            return
        state = ({'mode': extra[selected - len(catalog.COLLECTIONS)][0]}
                 if selected >= len(catalog.COLLECTIONS)
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
        info = {'title': movie['title'], 'plot': movie['plot'] or 'Details unavailable. Open Movie details (Cinemeta) from the context menu.', 'genre': movie['genre']}
        if len(movie['year']) == 4 and movie['year'].isascii() and movie['year'].isdigit():
            info['year'] = int(movie['year'])
        li.setInfo('video', info)
        li.setArt({'poster': movie['poster'], 'thumb': movie['poster'], 'fanart': movie['fanart'], 'icon': 'DefaultVideo.png'})
        li.setProperty('IsPlayable', 'false')
        li.setProperty('Aperture.MovieFolder', 'false')
        li.setProperty('Aperture.Availability', 'Not checked')
        route = BASE + '?' + urlencode({'action': 'online_details', 'id': movie['id']})
        match_route = BASE + '?' + urlencode({'mode': 'rd', 'imdb': movie['id']})
        stream_route = BASE + '?' + urlencode({'action': 'torrentio_find', 'id': movie['id']})
        li.addContextMenuItems([('Movie details (Cinemeta)', 'RunPlugin(' + route + ')'),
                                ('Choose source', 'RunPlugin(' + stream_route + ')'),
                                ('Check my Real-Debrid downloads (filename IMDb ID)', 'Container.Update(' + match_route + ')')])
        play_route = BASE + '?' + urlencode({'action': 'torrentio_auto', 'id': movie['id']})
        xbmcplugin.addDirectoryItem(HANDLE, play_route, li, False)
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
    xbmcgui.Dialog().ok(movie['title'], summary + '\n\n' + (movie['plot'] or 'Details unavailable from Cinemeta.') +
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


def history_directory(mode):
    import os
    from resources.lib.movie_history import HistoryError, HistoryStore
    try:
        rows = HistoryStore(os.path.join(poster_profile(), 'history-private')).records()
    except HistoryError:
        rows = []
        xbmcgui.Dialog().ok('History unavailable', 'Could not read private history. Clear history can reset invalid data; playback and media are unaffected.')
    xbmcplugin.setContent(HANDLE, 'movies')
    heading = 'History' if mode == 'history' else 'Continue watching'
    if mode == 'suggested':
        from resources.lib.movie_recommendations import recommend
        try:
            candidates, _, _ = catalog.browse({})  # Never derive a remote query from history.
        except catalog.CatalogError:
            candidates = []
            xbmcgui.Dialog().ok('Suggestions unavailable', 'The public catalogue is unavailable. History and Continue watching remain local.')
        result = recommend(candidates, rows)
        rows = result['items']
        heading = 'Suggested for you · ' + result['reason']
    xbmcplugin.setPluginCategory(HANDLE, heading)
    for row in rows:
        resume = row.get('resume_seconds', 0) > 0
        if mode == 'continue' and not resume:
            continue
        route = {'action': 'torrentio_auto', 'id': row['id']}
        beginning = BASE + '?' + urlencode(route)
        if resume:
            route['resume'] = '1'
        li = xbmcgui.ListItem(label=row['title'] + ('' if mode == 'suggested' else ' · Resume' if resume else ' · Watched'))
        li.setInfo('video', {'title': row['title'], 'genre': row['genres']})
        li.setArt({'icon': 'DefaultVideo.png'})
        li.setProperty('IsPlayable', 'false')
        li.setProperty('Aperture.MovieFolder', 'false')
        li.addContextMenuItems([('Play from beginning', 'RunPlugin(' + beginning + ')')])
        xbmcplugin.addDirectoryItem(HANDLE, BASE + '?' + urlencode(route), li, False)
    li = xbmcgui.ListItem(label='Clear history')
    li.setProperty('Aperture.MovieFolder', 'true')
    xbmcplugin.addDirectoryItem(HANDLE, BASE + '?action=clear_history', li, False)
    end()
    apply_cinema_view()


def home_row(row):
    """Skin widgets contain metadata only; sources resolve only on Select."""
    xbmcplugin.setContent(HANDLE, 'movies')
    movies = []
    seen = set()
    import os
    from resources.lib.movie_history import HistoryError, HistoryStore
    status = ''
    try:
        history = (HistoryStore(os.path.join(poster_profile(), 'history-private')).records()
                   if row in ('continue', 'suggested') else [])
    except HistoryError:
        history = []
        status = 'History unavailable. Open History to clear invalid data; local files remain available.'
    if row == 'continue':
        movies = [movie for movie in history if movie.get('resume_seconds', 0) > 0]
        status = status or ('' if movies else 'Nothing to resume yet. History starts with playback on this device.')
    collections = {'continue': (), 'suggested': ('top',), 'popular': ('top', 'imdbRating')}
    for collection in collections.get(row, ()):
        try:
            batch, _, _ = catalog.browse({'collection': [collection]})
        except catalog.CatalogError:
            status = 'Cinemeta unavailable. Retry, Search or use Local files.'
            continue
        for index, movie in enumerate(batch):
            if movie['id'] not in seen:
                # Interleave both public collections before the visible limit.
                movies.insert(min(index * 2 + (collection == 'imdbRating'), len(movies)), movie)
                seen.add(movie['id'])
    if row == 'suggested':
        from resources.lib.movie_recommendations import recommend
        ranked = recommend(movies, history)
        by_id = {movie['id']: movie for movie in movies}
        movies = [by_id[movie['id']] for movie in ranked['items']]
        status = status or ranked['reason']
    if not movies and row != 'continue':
        status = status or 'No catalogue results. Try Search, Retry or Local files.'
    xbmcgui.Window(10000).setProperty('Aperture.Home.' + row + '.status', status)
    for movie in movies[:20]:
        li = xbmcgui.ListItem(label=movie['title'])
        li.setInfo('video', {'title': movie['title'],
                             'plot': movie.get('plot') or 'Details unavailable in this row. Open Movie details (Cinemeta) from the context menu.',
                             'genre': movie.get('genre', movie.get('genres', []))})
        li.setProperty('Aperture.Year', str(movie.get('year', '')))
        li.setArt({'poster': movie.get('poster', ''), 'thumb': movie.get('poster', ''),
                   'fanart': movie.get('fanart', ''), 'icon': 'DefaultVideo.png'})
        li.setProperty('IsPlayable', 'false')
        li.setProperty('Aperture.Availability', 'Not checked')
        route = BASE + '?' + urlencode({'action': 'torrentio_auto', 'id': movie['id']})
        choose = BASE + '?' + urlencode({'action': 'torrentio_find', 'id': movie['id']})
        details = BASE + '?' + urlencode({'action': 'online_details', 'id': movie['id']})
        li.addContextMenuItems([('Movie details (Cinemeta)', 'RunPlugin(' + details + ')'),
                                ('Choose source', 'RunPlugin(' + choose + ')'),
                                ('Play from beginning', 'RunPlugin(' + route + ')')])
        if row == 'continue':
            route += '&resume=1'
        xbmcplugin.addDirectoryItem(HANDLE, route, li, False)
    end()


def main():
    query = parse_qs(sys.argv[2].lstrip('?'))
    action = query.get('action', [''])[0]
    if action == 'home_refresh':
        import secrets
        xbmcgui.Window(10000).setProperty('Aperture.Home.refresh', secrets.token_hex(8))
        return
    if action == 'home_search':
        origin = xbmcgui.getCurrentWindowId()
        if origin != 11120:
            return
        value = xbmcgui.Dialog().input('Search online movies (Cinemeta)')
        if (value and value.strip() and xbmcgui.getCurrentWindowId() == origin
                and not xbmc.Monitor().abortRequested()):
            route = BASE + '?' + urlencode({'mode': 'online', 'search': value.strip()[:200]})
            xbmc.executebuiltin('ActivateWindow(Videos,' + route + ',return)')
        return
    if not action and query.get('mode', [''])[0] == 'sources':
        xbmcplugin.setContent(HANDLE, 'files')
        for label, params, folder in [('Sources / account settings', {'action': 'providers'}, False),
                                      ('My Kodi library', {'mode': 'discover'}, True)]:
            li = xbmcgui.ListItem(label=label)
            li.setProperty('Aperture.MovieFolder', 'true')
            li.setArt({'icon': 'DefaultFolder.png'})
            xbmcplugin.addDirectoryItem(HANDLE, BASE + '?' + urlencode(params), li, folder)
        end()
        apply_cinema_view()
        return
    if not action and query.get('mode', [''])[0] == 'home_row':
        home_row(catalog.value(query, 'row'))
        return
    if action == 'clear_history':
        origin = xbmc.getInfoLabel('Container.FolderPath')
        if not xbmcgui.Dialog().yesno('Clear history?',
                'Remove local movie history and suggestions? Current playback continues without recording until a new selection. Media and backups are unchanged.'):
            return
        from resources.lib.history_playback import request_clear, CLEAR_ACK
        window = xbmcgui.Window(10000)
        request = request_clear(window)
        monitor = xbmc.Monitor()
        for _ in range(50):
            if window.getProperty(CLEAR_ACK) == request:
                if (xbmc.getInfoLabel('Container.FolderPath') == origin
                        and not xbmc.getCondVisibility('System.HasModalDialog')):
                    xbmc.executebuiltin('Container.Refresh')
                return
            if monitor.waitForAbort(0.1):
                return
        xbmcgui.Dialog().ok('History', 'Clear not confirmed. The playback service may be unavailable; try again later.')
        return
    if not action and query.get('mode', [''])[0] in ('history', 'continue', 'suggested'):
        history_directory(query['mode'][0])
        return
    if action in ('torrentio_setup', 'torrentio_find', 'torrentio_auto'):
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
            li.getVideoInfoTag().setMediaType('movie')
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


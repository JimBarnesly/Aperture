"""Aperture local movies: browse existing Kodi sources, never alter media."""
import json
import sys
import traceback
from urllib.parse import parse_qs, urlencode
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from resources.lib.library import select_source, default_from_xml, within_source, display_title, sidecar_candidates

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


def main():
    xbmcplugin.setContent(HANDLE, 'movies')
    xbmcplugin.setPluginCategory(HANDLE, 'Movies')
    sources = rpc('Files.GetSources', {'media': 'video'}).get('sources', [])
    sources = [s for s in sources if s.get('file') and not s['file'].startswith('plugin://')]
    if not sources:
        xbmcgui.Dialog().ok('Movies', 'Add your existing movie folder in Kodi → Videos → Files → Add videos, then return here.')
        end(); return
    query = parse_qs(sys.argv[2].lstrip('?'))
    root = query.get('source', [''])[0]
    chosen = next((s for s in sources if s['file'] == root), None) if root else select_source(sources, read_default())
    if chosen is None:
        # Multiple sources require one explicit choice; do not guess or persist it.
        for s in sources:
            li = xbmcgui.ListItem(label=s.get('label') or 'Video source')
            li.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
            li.setProperty('Aperture.MovieFolder', 'true')
            xbmcplugin.addDirectoryItem(HANDLE, BASE+'?'+urlencode({'source': s['file'], 'path': s['file']}), li, True)
        end(); xbmc.executebuiltin('Container.SetViewMode(61)'); return
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
            # Existing local art only. Do not automatically fetch or scrape metadata.
            for key, candidates in sidecar_candidates(target).items():
                if not art.get(key):
                    for candidate in candidates:
                        if xbmcvfs.exists(candidate):
                            art[key] = candidate; break
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
    xbmc.executebuiltin('Container.SetViewMode(61)')


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

"""Small, read-only source selection helpers. No filesystem traversal or scraping."""
import os
import posixpath
import re
from urllib.parse import urlsplit, unquote
import xml.etree.ElementTree as ET


def select_source(sources, default=''):
    """Respect Kodi's configured default by label/path; don't guess among drives."""
    if default:
        matches = [s for s in sources if default in (s.get('label'), s.get('file'))]
        if len(matches) == 1:
            return matches[0]
    return sources[0] if len(sources) == 1 else None


def default_from_xml(text):
    try:
        return (ET.fromstring(text).findtext('./video/default') or '').strip()
    except ET.ParseError:
        return ''


def within_source(path, root):
    """Validate directory requests; constrain plugin query strings to saved source."""
    p, r = urlsplit(path), urlsplit(root)
    if (p.scheme.lower(), p.netloc.lower()) != (r.scheme.lower(), r.netloc.lower()):
        return False
    pp = posixpath.normpath(unquote(p.path).replace('\\', '/'))
    rr = posixpath.normpath(unquote(r.path).replace('\\', '/'))
    return pp == rr or pp.startswith(rr.rstrip('/') + '/')


def display_title(item):
    title = item.get('title') or item.get('label') or posixpath.basename(item.get('file', '').rstrip('/'))
    if not item.get('title') and item.get('filetype') != 'directory':
        title = os.path.splitext(title)[0]
        title = re.sub(r'[._]+', ' ', title).strip()
    return title or 'Untitled'


def sidecar_candidates(path, include_folder=True):
    """Exact nearby art candidates only, never a recursive walk."""
    folder, name = posixpath.split(path)
    stem = posixpath.splitext(name)[0]
    return {kind: [folder+'/'+stem+'-'+kind+extension for extension in ('.jpg', '.png')]
            + ([folder+'/'+kind+extension for extension in ('.jpg', '.png')] if include_folder else [])
            for kind in ('poster', 'fanart')}


def artwork(item, exists, include_folder=False, poster=''):
    """Explicit per-film choices win; never reuse a shared folder poster blindly."""
    art = {key: value for key, value in (item.get('art') or {}).items()
           if isinstance(value, str) and value}
    if item.get('thumbnail'):
        art.setdefault('thumb', item['thumbnail'])
    exact = sidecar_candidates(item['file'], include_folder=False)
    nearby = sidecar_candidates(item['file'], include_folder=include_folder)
    for kind in ('poster', 'fanart'):
        # A file-specific sidecar is an explicit local correction. Kodi's matched
        # library art remains preferable to unqualified folder artwork.
        candidate = next((path for path in exact[kind] if exists(path)), '')
        if candidate:
            art[kind] = candidate
        elif not art.get(kind):
            candidate = next((path for path in nearby[kind][len(exact[kind]):]
                              if exists(path)), '')
            if candidate:
                art[kind] = candidate
    if poster:
        art['poster'] = poster
    return art

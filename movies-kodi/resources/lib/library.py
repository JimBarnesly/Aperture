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


def sidecar_candidates(path):
    """Exact nearby art candidates only, never a recursive walk."""
    folder, name = posixpath.split(path)
    stem = posixpath.splitext(name)[0]
    return {
        'poster': [folder+'/'+stem+'-poster.jpg', folder+'/'+stem+'-poster.png', folder+'/poster.jpg', folder+'/poster.png'],
        'fanart': [folder+'/'+stem+'-fanart.jpg', folder+'/'+stem+'-fanart.png', folder+'/fanart.jpg', folder+'/fanart.png'],
    }

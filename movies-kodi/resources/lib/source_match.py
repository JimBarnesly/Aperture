"""Local-only identity evidence. Never infer title availability from a filename."""
import re

VIDEO_EXTENSIONS = ('.mkv', '.mp4', '.avi', '.mov', '.m4v', '.webm', '.ts')
IMDB = re.compile(r'tt\d{5,12}')
TOKEN = re.compile(r'(?<![a-zA-Z0-9])tt\d{5,12}(?![a-zA-Z0-9])')


def valid_id(identifier):
    return isinstance(identifier, str) and IMDB.fullmatch(identifier) is not None


def matches(entry, identifier):
    """Require one unambiguous, explicit IMDb token in a video filename.

    This is evidence supplied by a filename, not verification of the file's
    contents, permissions, link validity or current provider availability.
    """
    if not valid_id(identifier) or not isinstance(entry, dict):
        return False
    name = entry.get('filename')
    if (not isinstance(name, str) or len(name) > 1024
            or any(ord(c) < 32 for c in name)
            or not name.lower().endswith(VIDEO_EXTENSIONS)):
        return False
    # Do not match a directory name or silently discard a conflicting identity.
    basename = re.split(r'[/\\]', name)[-1]
    return set(TOKEN.findall(basename)) == {identifier}

"""Local poster choices. Never query providers or write beside a movie."""
import hashlib
import json
import os
from pathlib import Path
import tempfile

EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def local_picture(path):
    """Accept local raster image paths only, not provider URLs or Kodi commands."""
    return (isinstance(path, str) and '\x00' not in path
            and os.path.isabs(path) and not path.startswith(('//', '\\\\'))
            and Path(path).suffix.lower() in EXTENSIONS)


def choice_path(profile, movie):
    if not os.path.isabs(profile):
        raise ValueError('An absolute Kodi profile path is required.')
    # Do not expose movie names in cache filenames, or trust query-string paths.
    key = hashlib.sha256(movie.encode('utf-8')).hexdigest()
    return Path(profile) / 'posters' / (key + '.json')


def read_choice(profile, movie):
    try:
        with choice_path(profile, movie).open(encoding='utf-8') as stream:
            raw = stream.read(16385)
        if len(raw) > 16384:
            return ''
        value = json.loads(raw)
        path = value.get('path') if isinstance(value, dict) else None
        return path if local_picture(path) and os.path.isfile(path) else ''
    except (OSError, ValueError, TypeError):
        return ''


def save_choice(profile, movie, picture):
    """Save a reference only. Cancellation/invalid input must leave it unchanged."""
    if not local_picture(picture) or not os.path.isfile(picture):
        raise ValueError('Choose an existing local JPEG, PNG or WebP image.')
    raw = json.dumps({'path': picture}, ensure_ascii=False)
    if len(raw) > 16384:
        raise ValueError('The picture path is too long.')
    target = choice_path(profile, movie)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent,
                                         prefix='.poster-', delete=False) as stream:
            temporary = stream.name
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def reset_choice(profile, movie):
    """Remove only Aperture's preference, never the selected image or media."""
    try:
        choice_path(profile, movie).unlink()
    except FileNotFoundError:
        pass

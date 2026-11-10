"""Local Movies playback history; no Kodi, network or account dependencies."""
import fcntl
import json
import math
import os
import re
import stat
import secrets
from contextlib import contextmanager
from pathlib import Path


class HistoryError(Exception):
    """Private history could not be safely read or written (no path in message)."""


@contextmanager
def private_directory(path, create=False):
    """Walk with directory FDs, never following a symlink in any component."""
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        parts = Path(os.path.abspath(path)).parts[1:]
        for part in parts:
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                if create:
                    raise
                yield None
                return
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise HistoryError('History directory is not private')
        yield fd
    except OSError:
        raise HistoryError('History storage unavailable') from None
    finally:
        os.close(fd)


def private_file(directory, name, flags):
    fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=directory)
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
        os.close(fd)
        raise HistoryError('History file is not private')
    return fd


def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r'tt[0-9]{5,12}', value) is not None


def number(value):
    return type(value) in (int, float) and 0 <= value <= 1e12 and math.isfinite(value)


GENRES = frozenset(('Action', 'Adventure', 'Animation', 'Biography', 'Comedy', 'Crime',
                    'Documentary', 'Drama', 'Family', 'Fantasy', 'History', 'Horror',
                    'Mystery', 'Romance', 'Sci-Fi', 'Sport', 'Thriller', 'War', 'Western'))
MAX_BYTES = 1024 * 1024


def metadata(movie):
    if not isinstance(movie, dict) or not valid_id(movie.get('id')):
        return None
    title, year, genres = movie.get('title'), movie.get('year', ''), movie.get('genre', [])
    if (not isinstance(title, str) or not title.strip() or '://' in title
            or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in title)
            or not isinstance(year, str) or (year and not re.fullmatch(r'[0-9]{4}', year))
            or not isinstance(genres, list)
            or any(not isinstance(g, str) or g not in GENRES for g in genres)):
        return None
    return {'id': movie['id'], 'title': title[:300], 'year': year,
            'genres': list(dict.fromkeys(genres))}


class HistoryStore:
    """Store catalogue metadata and observed playback progress locally."""

    def __init__(self, directory, max_records=200):
        if type(max_records) is not int or not 1 <= max_records <= 500:
            raise ValueError('max_records must be between 1 and 500')
        self.directory = Path(directory)
        self.max_records = max_records

    def records(self):
        with private_directory(self.directory) as directory:
            if directory is None:
                return []
            return self._read(directory)

    def _read(self, directory):
        try:
            fd = private_file(directory, 'history.json', os.O_RDONLY)
        except FileNotFoundError:
            return []
        with os.fdopen(fd, 'rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        try:
            if len(raw) > MAX_BYTES:
                raise ValueError()
            data = json.loads(raw)
            if (not isinstance(data, dict) or set(data) != {'version', 'records'}
                    or type(data['version']) is not int or data['version'] != 1
                    or not isinstance(data['records'], dict) or len(data['records']) > 500):
                raise ValueError()
            rows = list(data['records'].values())
            for identifier, row in data['records'].items():
                if not isinstance(row, dict):
                    raise ValueError()
                meta = metadata(dict(row, genre=row.get('genres')))
                if (meta is None or identifier != meta['id']
                        or set(row) != set(meta) | {'resume_seconds', 'duration_seconds', 'lastplayed', 'completed'}
                        or any(row[k] != v for k, v in meta.items())
                        or type(row['completed']) is not bool
                        or not all(number(row[k]) for k in ('resume_seconds', 'duration_seconds', 'lastplayed'))):
                    raise ValueError()
            return sorted(rows, key=lambda row: (-row['lastplayed'], row['id']))[:self.max_records]
        except (ValueError, TypeError, KeyError, RecursionError):
            raise HistoryError('History data is invalid') from None

    def record_playback(self, movie, *, is_playing, position_seconds,
                        duration_seconds, lastplayed):
        if (is_playing is not True or not isinstance(movie, dict)
                or not valid_id(movie.get('id'))
                or not all(number(n) for n in (position_seconds, duration_seconds, lastplayed))
                or position_seconds == 0):
            return False
        record = metadata(movie)
        if record is None:
            return False
        record.update(resume_seconds=position_seconds, duration_seconds=duration_seconds,
                      lastplayed=lastplayed, completed=False)
        with private_directory(self.directory, create=True) as directory:
            fcntl.flock(directory, fcntl.LOCK_EX)
            records = {row['id']: row for row in self._read(directory)}
            previous = records.get(record['id'], {})
            if previous.get('lastplayed', 0) > lastplayed:
                return False
            reached_end = duration_seconds > 0 and position_seconds >= duration_seconds * 0.9
            record['completed'] = reached_end or previous.get('completed', False)
            record['resume_seconds'] = 0 if reached_end else position_seconds
            records[record['id']] = record
            records = {row['id']: row for row in sorted(
                records.values(), key=lambda row: (-row['lastplayed'], row['id']))[:self.max_records]}
            self._write(directory, records)
        return True

    def clear(self):
        """Replace only history.json with an empty document; never delete media."""
        with private_directory(self.directory) as directory:
            if directory is None:
                return
            fcntl.flock(directory, fcntl.LOCK_EX)
            try:
                fd = private_file(directory, 'history.json', os.O_RDONLY)
            except FileNotFoundError:
                return
            os.close(fd)
            self._write(directory, {})

    def _write(self, directory, records):
        name = '.history-' + secrets.token_hex(16) + '.tmp'
        fd = private_file(directory, name, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump({'version': 1, 'records': records}, stream,
                          allow_nan=False, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, 'history.json', src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        finally:
            try:
                os.unlink(name, dir_fd=directory)
            except FileNotFoundError:
                pass

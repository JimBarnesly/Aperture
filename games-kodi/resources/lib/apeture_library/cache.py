"""Durable, bounded library snapshots. Only this add-on's profile is writable.

The ROM tree is always read-only. Cache identity is independent of add-on/skin
versions. Relative paths keep share credentials out of snapshots and filenames.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time

from .catalog import SYSTEM_BY_FOLDER, SYSTEM_BY_ID
from .scanner import Game, ScanResult, SystemLibrary, join_path, safe_name

SCHEMA = 1
MAX_BYTES = 32 * 1024 * 1024
MAX_GAMES = 100000
REFRESH_SECONDS = 24 * 60 * 60
RETRY_SECONDS = 15 * 60


def source_key(root):
    return hashlib.sha256(root.encode("utf-8")).hexdigest()


def _relative(root, path, system_id):
    prefix = root.rstrip("/\\") + ("/" if "://" in root else os.sep)
    if not isinstance(path, str) or not path.startswith(prefix):
        raise ValueError("Cache path outside source")
    relative = path[len(prefix):].replace(os.sep, "/")
    _absolute(root, relative, system_id)
    return relative


def _absolute(root, relative, system_id):
    if not isinstance(relative, str) or len(relative) > 8192:
        raise ValueError("Invalid cache path")
    parts = relative.split("/")
    if len(parts) < 2 or not all(safe_name(part) for part in parts):
        raise ValueError("Invalid cache path")
    system = SYSTEM_BY_FOLDER.get(parts[0].casefold())
    if system is None or system.id != system_id:
        raise ValueError("Cache path outside system")
    path = root
    for part in parts:
        path = join_path(path, part)
    return path


def _timestamp(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("Invalid timestamp")
    return value


class LibraryCache:
    def __init__(self, profile, root, now=time.time):
        self.directory = Path(profile) / "library-v1"
        self.root = root
        self.key = source_key(root)
        self.path = self.directory / (self.key + ".json")
        self.attempt_path = self.directory / (self.key + ".attempt")
        self.request_path = self.directory / (self.key + ".request")
        self.now = now

    def _read(self, path):
        with path.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Cache exceeds size limit")
        return json.loads(data)

    def load(self):
        """Return (result, completed_at), or None without touching the ROM root."""
        try:
            data = self._read(self.path)
            if data["schema"] != SCHEMA or data["source"] != self.key:
                return None
            completed = _timestamp(data["completed"])
            libraries, count, seen = [], 0, set()
            for entry in data["libraries"]:
                system_id = entry["system"]
                if system_id not in SYSTEM_BY_ID or system_id in seen:
                    raise ValueError("Invalid cached system")
                seen.add(system_id)
                games = []
                for item in entry["games"]:
                    count += 1
                    if count > MAX_GAMES or not isinstance(item["title"], str) or len(item["title"]) > 8192:
                        raise ValueError("Invalid cached games")
                    path = _absolute(self.root, item["path"], system_id)
                    discs = tuple(_absolute(self.root, disc, system_id) for disc in item["discs"])
                    artwork = tuple((kind, _absolute(self.root, value, system_id))
                                    for kind, value in item["artwork"] if kind in ("thumb", "poster"))
                    games.append(Game(system_id, item["title"], path, discs, artwork))
                libraries.append(SystemLibrary(SYSTEM_BY_ID[system_id], tuple(games)))
            return ScanResult(tuple(libraries), ()), completed
        except (OSError, ValueError, KeyError, TypeError, OverflowError, RecursionError):
            return None

    def _write(self, path, data):
        content = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(content) > MAX_BYTES:
            raise ValueError("Cache exceeds size limit")
        self.directory.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".snapshot-", dir=str(self.directory))
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.utime(temporary, (self.now(), self.now()))
            os.replace(temporary, path)
            # Persist the rename across abrupt power loss on POSIX filesystems.
            if os.name != "nt":
                descriptor = os.open(str(self.directory), os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def publish(self, result):
        # Incomplete/unreadable scans must never erase a last-known-good library.
        if any(issue.code in ("unsafe_path", "unreadable_directory") for issue in result.issues):
            raise ValueError("Incomplete scan cannot replace library cache")
        libraries = []
        for library in result.libraries:
            system_id = library.system.id
            games = [{"title": game.title, "path": _relative(self.root, game.path, system_id),
                      "discs": [_relative(self.root, disc, system_id) for disc in game.discs],
                      "artwork": [(kind, _relative(self.root, path, system_id)) for kind, path in game.artwork]}
                     for game in library.games]
            libraries.append({"system": system_id, "games": games})
        self._write(self.path, {"schema": SCHEMA, "source": self.key,
                                "completed": self.now(), "libraries": libraries})

    def request_refresh(self):
        """Explicit user refresh, independent of navigation and cache lifetime."""
        self._write(self.request_path, {"requested": self.now()})

    def status(self):
        try:
            return self._read(self.attempt_path).get("status", "indexing")
        except (OSError, ValueError, TypeError, AttributeError):
            return "indexing"

    def due(self, snapshot=None):
        if self.request_path.exists():
            return True
        now = self.now()
        try:
            attempt = self._read(self.attempt_path)
            age = now - _timestamp(attempt["started"])
            if attempt.get("status") in ("indexing", "unavailable"):
                # A failed explicit refresh also retries, even if the older
                # snapshot was originally created less than a day ago.
                return not 0 <= age < RETRY_SECONDS
        except (OSError, ValueError, KeyError, TypeError):
            pass
        try:
            completed = snapshot[1] if snapshot is not None else self.path.stat().st_mtime
            if 0 <= now - completed < REFRESH_SECONDS:
                return False
        except OSError:
            pass
        return True

    def mark_attempt(self, status="indexing", started=None):
        self._write(self.attempt_path, {"started": self.now() if started is None else started, "status": status})

    @contextmanager
    def refresh_lock(self):
        """Kernel-owned lock: no stale busy flag survives a crash or reboot."""
        self.directory.mkdir(parents=True, exist_ok=True)
        stream = (self.directory / (self.key + ".lock")).open("a+b")
        acquired = False
        try:
            try:
                if os.name == "nt":
                    import msvcrt
                    stream.seek(0)
                    if not stream.read(1):
                        stream.write(b"0")
                        stream.flush()
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except (OSError, BlockingIOError):
                pass
            yield acquired
        finally:
            # Closing releases either OS lock, including on exceptions.
            stream.close()


def refresh(cache, scanner, cancelled=lambda: False):
    """Refresh once if due. Caller reports failures without disturbing browsing."""
    with cache.refresh_lock() as acquired:
        if not acquired or not cache.due():
            return False
        explicit = cache.request_path.exists()
        previous = cache.load()
        started = cache.now()
        # Consume only the request that preceded this attempt. A newer request
        # arriving during the scan remains pending for the next service tick.
        try:
            cache.request_path.unlink()
        except FileNotFoundError:
            pass
        cache.mark_attempt(started=started)
        try:
            result = scanner()
            if cancelled():
                from .scanner import ScanCancelled
                raise ScanCancelled()
            if not result.libraries and previous and previous[0].libraries and not explicit:
                raise ValueError("Empty background scan cannot erase a populated library")
            cache.publish(result)
        except Exception:
            cache.mark_attempt("unavailable", started)
            raise
        cache.mark_attempt("ready", started)
        return True

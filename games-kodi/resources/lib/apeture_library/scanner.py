"""Read-only, bounded discovery over local files or an injected Kodi VFS.

Only explicit system folders directly below the configured root are scanned.
No Kodi imports, ROM probing, downloads, database, or background services.
SPDX-License-Identifier: GPL-3.0-or-later
"""

import ntpath
import os
import posixpath
import re
from dataclasses import dataclass
from typing import Callable, Tuple

from .catalog import SYSTEM_BY_FOLDER, SYSTEM_BY_ID, System

MANIFEST_LIMIT = 256 * 1024
PLAYLIST_EXTENSIONS = frozenset((".m3u", ".m3u8"))
_CUE_FILE = re.compile(r'^\s*FILE\s+(?:"([^"\r\n]+)"|(\S+))\s+\S+\s*$', re.IGNORECASE)
_URI = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_ENCODED_TRAVERSAL = re.compile(r"%(?:2e|2f|5c)", re.IGNORECASE)


class ScanError(Exception):
    """A failed or unsafe root, or a bounded scan limit."""


class ScanCancelled(Exception):
    """Cancellation never publishes a misleading partial library."""


@dataclass(frozen=True)
class Game:
    system_id: str
    title: str
    path: str
    discs: Tuple[str, ...] = ()


@dataclass(frozen=True)
class SystemLibrary:
    system: System
    games: Tuple[Game, ...]


@dataclass(frozen=True)
class ScanIssue:
    code: str
    path: str


@dataclass(frozen=True)
class ScanResult:
    libraries: Tuple[SystemLibrary, ...]
    issues: Tuple[ScanIssue, ...]


def is_uri(path):
    return bool(_URI.match(path))


def _path_module(path):
    return ntpath if not is_uri(path) and (ntpath.splitdrive(path)[0] or "\\" in path) else posixpath


def safe_name(name):
    """A VFS listing must return one plain child, never a path or dot entry."""
    return (
        isinstance(name, str) and bool(name) and not name.startswith(".")
        and not any(character in name for character in ("/", "\\", ":", "|", "?", "#"))
        and not any(ord(character) < 32 for character in name)
        and not _ENCODED_TRAVERSAL.search(name)
    )


def join_path(parent, child):
    if not safe_name(child):
        raise ValueError("Expected a plain child name")
    if is_uri(parent):
        return parent.rstrip("/") + "/" + child
    return _path_module(parent).join(parent, child)


def filename(path):
    return _path_module(path).basename(path)


def extension(path):
    return posixpath.splitext(filename(path))[1].lower()


def reference_path(manifest, reference, boundary):
    """Resolve relative descriptor entries without escaping a system folder.

    Absolute paths, URI references, protocol options, and encoded traversal are
    deliberately unsupported. Existing filenames are matched exactly afterward.
    """
    reference = reference.strip().replace("\\", "/")
    if (not reference or reference.startswith("/") or ":" in reference
            or any(character in reference for character in ("|", "?", "#"))
            or _ENCODED_TRAVERSAL.search(reference)
            or any(ord(character) < 32 for character in reference)):
        return None
    parts = reference.split("/")
    if any(part.startswith(".") and part not in (".", "..") for part in parts):
        return None
    module = _path_module(manifest)
    if is_uri(manifest):
        # normpath on the whole URI would corrupt its double slash.
        prefix, path = manifest.split("://", 1)
        candidate = prefix + "://" + posixpath.normpath(posixpath.dirname(path) + "/" + reference)
        return candidate if candidate.startswith(boundary.rstrip("/") + "/") else None
    candidate = module.normpath(module.join(module.dirname(manifest), reference))
    try:
        if module.commonpath((candidate, boundary)) == module.normpath(boundary):
            return candidate
    except ValueError:
        pass
    return None


class LocalFileSystem:
    """Never follow symlinks; only regular files and real directories count."""

    def listdir(self, path):
        directories, files = [], []
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    directories.append(entry.name)
                elif entry.is_file(follow_symlinks=False):
                    files.append(entry.name)
        return directories, files

    def read_text(self, path, limit=MANIFEST_LIMIT):
        with open(path, "rb") as stream:
            content = stream.read(limit + 1)
        if len(content) > limit:
            raise ValueError("Descriptor exceeds read limit")
        return content.decode("utf-8-sig")

    def safe(self, path, boundary):
        # A second containment check also rejects symlink replacement before
        # traversal/manifest reading. Not a sandbox against concurrent FS edits.
        try:
            return (not os.path.islink(path)
                    and os.path.commonpath((os.path.realpath(path), os.path.realpath(boundary)))
                    == os.path.realpath(boundary))
        except ValueError:
            return False


def scan_library(root, filesystem=None, cancelled: Callable[[], bool] = lambda: False,
                 system_id=None, max_depth=32, max_entries=100000):
    """Return only populated systems, sorted by name, with immutable game lists.

    Root errors fail visibly. Unreadable subfolders/descriptors are reported as
    issues while unrelated games remain available. Hidden entries are skipped.
    Every directory/file consumes the global entry budget, even unknown names.
    """
    if not root or not root.strip():
        return ScanResult((), ())
    if system_id is not None and system_id not in SYSTEM_BY_ID:
        raise ScanError("Unknown system")
    filesystem = filesystem or LocalFileSystem()
    issues, grouped = [], {}
    visited, remaining = set(), max_entries

    def check_cancel():
        if cancelled():
            raise ScanCancelled()

    def listing(path):
        nonlocal remaining
        check_cancel()
        directories, files = filesystem.listdir(path)
        remaining -= len(directories) + len(files)
        if remaining < 0:
            raise ScanError("Scan limit exceeded; choose a smaller ROM root")
        return sorted(set(directories)), sorted(set(files))

    def walk(boundary):
        files, stack = set(), [(boundary, 0)]
        while stack:
            check_cancel()
            directory, depth = stack.pop()
            if directory in visited:
                continue
            visited.add(directory)
            if not filesystem.safe(directory, boundary):
                issues.append(ScanIssue("unsafe_path", directory))
                continue
            try:
                directories, names = listing(directory)
            except (OSError, IOError):
                issues.append(ScanIssue("unreadable_directory", directory))
                continue
            for name in names:
                check_cancel()
                if safe_name(name):
                    path = join_path(directory, name)
                    if filesystem.safe(path, boundary):
                        files.add(path)
            for name in reversed(directories):
                if safe_name(name):
                    if depth >= max_depth:
                        raise ScanError("Folder depth limit exceeded; choose a shallower ROM root")
                    stack.append((join_path(directory, name), depth + 1))
        return files

    def read_descriptor(path, boundary):
        check_cancel()
        if not filesystem.safe(path, boundary):
            raise ValueError("Unsafe descriptor")
        return filesystem.read_text(path, MANIFEST_LIMIT)

    def games_for(system, boundary, all_files):
        candidates = {path for path in all_files if extension(path) in system.extensions}
        cue_members, playlists = {}, {}
        for path in sorted(candidates):
            check_cancel()
            if extension(path) != ".cue":
                continue
            try:
                refs = []
                for line in read_descriptor(path, boundary).splitlines():
                    if re.match(r"^\s*FILE\b", line, re.IGNORECASE):
                        match = _CUE_FILE.match(line)
                        if not match:
                            raise ValueError("Malformed FILE entry")
                        refs.append(reference_path(path, match.group(1) or match.group(2), boundary))
                if not refs or any(ref not in all_files or ref == path for ref in refs):
                    raise ValueError("Missing or unsafe CUE member")
                cue_members[path] = tuple(refs)
            except (OSError, IOError, UnicodeError, ValueError):
                issues.append(ScanIssue("invalid_cue", path))
        candidates = {path for path in candidates if extension(path) != ".cue" or path in cue_members}
        for path in sorted(candidates):
            check_cancel()
            if extension(path) not in PLAYLIST_EXTENSIONS:
                continue
            try:
                refs = []
                for line in read_descriptor(path, boundary).splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        ref = reference_path(path, line, boundary)
                        if ref not in candidates or extension(ref) in PLAYLIST_EXTENSIONS:
                            raise ValueError("Missing, unsafe, or nested playlist member")
                        if ref not in refs:
                            refs.append(ref)
                if not refs:
                    raise ValueError("Empty playlist")
                playlists[path] = tuple(refs)
            except (OSError, IOError, UnicodeError, ValueError):
                issues.append(ScanIssue("invalid_playlist", path))
        hidden = {member for members in cue_members.values() for member in members}
        hidden.update(member for members in playlists.values() for member in members)
        games = []
        for path in sorted(candidates - hidden):
            if extension(path) in PLAYLIST_EXTENSIONS and path not in playlists:
                continue
            games.append(Game(system.id, posixpath.splitext(filename(path))[0], path, playlists.get(path, ())))
        return games

    check_cancel()
    try:
        directories, _ = listing(root)
    except (OSError, IOError) as exc:
        raise ScanError("ROM root is unavailable or unreadable") from exc
    for directory in directories:
        check_cancel()
        system = SYSTEM_BY_FOLDER.get(directory.casefold())
        if system is None or (system_id is not None and system.id != system_id) or not safe_name(directory):
            continue
        boundary = join_path(root, directory)
        if not filesystem.safe(boundary, root):
            issues.append(ScanIssue("unsafe_path", boundary))
            continue
        games = games_for(system, boundary, walk(boundary))
        grouped.setdefault(system.id, []).extend(games)
    libraries = [SystemLibrary(SYSTEM_BY_ID[key], tuple(sorted(games, key=lambda game: (game.title.casefold(), game.path))))
                 for key, games in grouped.items() if games]
    libraries.sort(key=lambda library: library.system.name.casefold())
    check_cancel()
    return ScanResult(tuple(libraries), tuple(issues))

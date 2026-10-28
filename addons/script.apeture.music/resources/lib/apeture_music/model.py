# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure shelf rules. No Kodi, filesystem access, networking or global randomness."""
from dataclasses import dataclass
import re
from urllib.parse import unquote, urlsplit


def text(value, fallback=""):
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def number(value, fallback=0):
    # Reject bools, negative IDs and malformed metadata without interpreting paths.
    return value if type(value) is int and value >= 0 else fallback


def artists(value):
    if isinstance(value, str):
        value = [value]
    return tuple(name.strip() for name in (value or []) if isinstance(name, str) and name.strip()) if isinstance(value, (list, tuple)) else ()


def artist_key(value):
    return re.sub(r"^the\s+", "", value.casefold()).strip()


def local_artwork(value):
    """Only local/cached artwork: never turn a thumbnail into an online fetch.

    Keep the original Kodi image URL intact, including escaping/transform options.
    Existing HTTP/SMB artwork is omitted, not downloaded or rewritten. Kodi's
    special://thumbnails cache files and local embedded artwork remain usable.
    """
    value = text(value)
    candidate = value
    for _ in range(3):
        if candidate.lower().startswith("image://"):
            wrapped = candidate[8:].split("/", 1)[0]
            # Kodi encodes embedded artwork as image://[type@]<encoded-path>/.
            # The type is URI userinfo (for example music@), not part of the
            # underlying file path. Strip before decoding, so a literal %40
            # in a local filename is preserved and remote URLs stay rejected.
            candidate = unquote(wrapped.split("@", 1)[-1])
        else:
            break
    if not candidate or candidate.startswith(("//", "\\\\")):
        return ""
    if re.match(r"^[A-Za-z]:[\\/]", candidate):
        return value
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return ""
    scheme = parsed.scheme.lower()
    if scheme in ("special", "resource", "file"):
        if scheme == "file":
            # Empty authority does not imply local: file:////server/share is
            # another UNC spelling. Reject encoded network roots as well.
            path = unquote(parsed.path)
            if parsed.netloc.lower() not in ("", "localhost") or path.startswith(("//", "\\\\")):
                return ""
        return value
    return value if not scheme and candidate.startswith("/") else ""


@dataclass(frozen=True)
class Album:
    id: int
    title: str
    artists: tuple
    year: int
    art: str

    @property
    def artist(self):
        return " / ".join(self.artists) or "Unknown artist"


@dataclass(frozen=True)
class Song:
    id: int
    title: str
    artists: tuple
    album_artists: tuple
    disc: int
    track: int
    duration: int
    file: str


def albums_from_rows(rows):
    albums, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        identifier = number(row.get("albumid"), -1)
        if identifier < 0 or identifier in seen:
            continue
        seen.add(identifier)
        albums.append(Album(identifier, text(row.get("title"), text(row.get("label"), "Untitled album")),
                            artists(row.get("artist")), number(row.get("year")),
                            local_artwork(row.get("thumbnail"))))
    # Unknown years precede dated releases, matching Format's zero-year behavior.
    # Title and ID tie-breaks make the shelf stable without shuffling it.
    return sorted(albums, key=lambda a: (tuple(artist_key(n) for n in a.artists) or ("unknown artist",),
                                        a.year, a.title.casefold(), a.id))


def songs_from_rows(rows):
    songs, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        identifier = number(row.get("songid"), -1)
        path = row.get("file")
        # Preserve paths byte-for-character: spaces, quotes, percent signs, URL
        # escaping and user-configured network schemes belong to Kodi, not us.
        if identifier < 0 or identifier in seen or not isinstance(path, str) or not path.strip():
            continue
        seen.add(identifier)
        songs.append(Song(identifier, text(row.get("title"), text(row.get("label"), "Untitled track")),
                          artists(row.get("artist")), artists(row.get("albumartist")),
                          max(1, number(row.get("disc"))), number(row.get("track")),
                          number(row.get("duration")), path))
    # Kodi JSON-RPC supplies disc and track separately; never sort by filename.
    return sorted(songs, key=lambda s: (s.disc, s.track or 65536, s.title.casefold(), s.id))


def initial_index(albums, playing_album_id, rng):
    if not albums:
        return None
    if type(playing_album_id) is int:
        for index, album in enumerate(albums):
            if album.id == playing_album_id:
                return index
    return rng.randrange(len(albums))


class Shelf:
    def __init__(self, albums, playing_album_id, rng):
        self.albums = tuple(albums)
        self.index = initial_index(self.albums, playing_album_id, rng)

    @property
    def current(self):
        return self.albums[self.index] if self.index is not None else None

    def move(self, delta):
        if self.index is not None:
            self.index = min(len(self.albums) - 1, max(0, self.index + delta))
        return self.current

    def neighbor(self, offset):
        if self.index is None or not 0 <= self.index + offset < len(self.albums):
            return None
        return self.albums[self.index + offset]

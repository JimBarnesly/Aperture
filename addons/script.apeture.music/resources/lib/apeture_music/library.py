# SPDX-License-Identifier: GPL-3.0-or-later
"""Kodi JSON-RPC adapter, injected transport for deterministic offline tests."""
import json
from .model import albums_from_rows, songs_from_rows, number


class LibraryError(Exception):
    """Deliberately carries no server response, media path or private metadata."""


class Library:
    PAGE_SIZE = 500

    def __init__(self, execute, cancelled=lambda: False):
        self.execute = execute
        self.cancelled = cancelled
        self.request_id = 0

    def call(self, method, **params):
        if self.cancelled():
            raise LibraryError("Library request cancelled.")
        self.request_id += 1
        try:
            response = json.loads(self.execute(json.dumps({"jsonrpc": "2.0", "id": self.request_id,
                                                          "method": method, "params": params})))
            if not isinstance(response, dict) or "error" in response or "result" not in response:
                raise ValueError("Invalid response")
            return response["result"]
        except Exception:
            # Do not surface exception text: JSON-RPC failures may contain URLs,
            # credentials, media filenames or tag data.
            raise LibraryError("Kodi could not read the music library.") from None

    def rows(self, method, key, **params):
        rows, start = [], 0
        while True:
            result = self.call(method, limits={"start": start, "end": start + self.PAGE_SIZE}, **params)
            if not isinstance(result, dict):
                raise LibraryError("Unexpected library response.")
            batch = result.get(key, [])
            limits = result.get("limits", {})
            if not isinstance(batch, list) or not isinstance(limits, dict):
                raise LibraryError("Unexpected library response.")
            end = number(limits.get("end"), start + len(batch))
            total = number(limits.get("total"), end)
            rows.extend(batch)
            if end >= total:
                return rows
            if not batch or end <= start:
                raise LibraryError("The library changed while loading. Try again.")
            start = end

    def albums(self):
        return albums_from_rows(self.rows("AudioLibrary.GetAlbums", "albums",
            properties=["title", "artist", "year", "thumbnail"],
            sort={"method": "label", "order": "ascending"}))

    def songs(self, album_id):
        if type(album_id) is not int or album_id < 0:
            raise LibraryError("Invalid album.")
        rows = self.rows("AudioLibrary.GetSongs", "songs", filter={"albumid": album_id},
            properties=["title", "artist", "albumartist", "disc", "track", "duration", "file"],
            sort={"method": "track", "order": "ascending"})
        songs = songs_from_rows(rows)
        if len(songs) != len(rows):
            # Do not quietly play half an album or mutate the existing queue
            # when a track has no playable file, malformed ID or duplicate row.
            raise LibraryError("Some album tracks are unavailable. Check Kodi Music.")
        return songs

    def playing_album(self):
        # A transient player transition must not prevent browsing the library.
        try:
            players = self.call("Player.GetActivePlayers")
            if not isinstance(players, list):
                return None
            audio = next((p for p in players if isinstance(p, dict) and p.get("type") == "audio"), None)
            if not audio or type(audio.get("playerid")) is not int:
                return None
            result = self.call("Player.GetItem", playerid=audio["playerid"], properties=["albumid"])
            item = result.get("item", {}) if isinstance(result, dict) else {}
            if not isinstance(item, dict):
                return None
            identifier = number(item.get("albumid"), -1)
            return identifier if identifier >= 0 else None
        except LibraryError:
            return None

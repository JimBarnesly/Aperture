"""Read-only Format client for Kodi 20/21. No acquisition or library writes."""
import json
import math
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

ADDON_ID = "plugin.audio.aperture.format"
BASE = "plugin://{}/".format(ADDON_ID)
MAX_LIBRARY_BYTES = 64 * 1024 * 1024
LIBRARY_CHUNK_BYTES = 64 * 1024
LIBRARY_BODY_SECONDS = 20
SOCKET_TIMEOUT_SECONDS = 12


class FormatError(Exception):
    """An error safe to show without exposing the server response or URL."""


def plugin_url(action, **kwargs):
    return BASE + "?" + urlencode(dict(action=action, **kwargs))


def server_url():
    # Read on each invocation so a settings change does not leave a stale URL.
    value = xbmcaddon.Addon(ADDON_ID).getSetting("server_url").strip().rstrip("/")
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme in ("http", "https") and parsed.hostname
                 and not parsed.username and not parsed.password
                 and not parsed.query and not parsed.fragment
                 and not any(character.isspace() for character in value))
        parsed.port  # Raises ValueError for malformed/out-of-range ports.
    except ValueError:
        valid = False
    if not valid:
        raise FormatError("Set a reachable http:// or https:// Format server URL in the add-on settings.")
    return value


def media(server, endpoint, track_id):
    return server + endpoint + "?" + urlencode({"id": track_id})


def library(server):
    try:
        with urlopen(server + "/api/library", timeout=SOCKET_TIMEOUT_SECONDS) as response:
            deadline = time.monotonic() + LIBRARY_BODY_SECONDS
            payload = bytearray()
            while True:
                if time.monotonic() >= deadline:
                    raise FormatError("Format took too long to return its library. Try again when the server responds.")
                # read() may wait to fill its entire size while a server drips
                # bytes forever. read1() performs at most one underlying read,
                # letting the monotonic body budget be checked between chunks.
                chunk = response.read1(min(LIBRARY_CHUNK_BYTES, MAX_LIBRARY_BYTES + 1 - len(payload)))
                if time.monotonic() >= deadline:
                    raise FormatError("Format took too long to return its library. Try again when the server responds.")
                if not chunk:
                    break
                payload.extend(chunk)
                if len(payload) > MAX_LIBRARY_BYTES:
                    raise FormatError("The Format library response is too large.")
        data = json.loads(payload)
    except HTTPError as error:
        raise FormatError("Format returned HTTP {}. Check the server address and access.".format(error.code)) from error
    except (URLError, TimeoutError, OSError) as error:
        raise FormatError("Cannot reach Format. Check the server is running and the Pi can reach it.") from error
    except (ValueError, UnicodeError) as error:
        raise FormatError("The server did not return a Format library. Check the server URL.") from error
    if (not isinstance(data, dict)
            or not isinstance(data.get("albums"), list)
            or not isinstance(data.get("tracks"), list)
            or not all(isinstance(item, dict) for item in data["albums"] + data["tracks"])):
        raise FormatError("The server returned an unsupported Format library.")
    return data


def number(value, default=0):
    """Handle optional metadata and tag values such as 2/12 without crashing."""
    try:
        result = float(str(value).split("/", 1)[0])
        return max(0, int(result)) if math.isfinite(result) else default
    except (TypeError, ValueError, OverflowError):
        return default


def text(value, fallback=""):
    return str(value) if value is not None and value != "" else fallback


def track_ids(album):
    values = album.get("trackIds")
    if not isinstance(values, list):
        return []
    return list(dict.fromkeys(str(value) for value in values
                              if isinstance(value, (str, int)) and str(value)))


def album_tracks(data, album):
    lookup = {str(track["id"]): track for track in data["tracks"] if track.get("id") is not None}
    ids = track_ids(album)
    if not ids or any(track_id not in lookup for track_id in ids):
        raise FormatError("This album has missing tracks. Refresh Format's library on the server and try again.")
    tracks = [lookup[track_id] for track_id in ids]
    # Format's older API sorted only by track number, interleaving double albums.
    # Python's stable sort preserves API order when disc/track metadata is absent.
    return sorted(tracks, key=lambda track: (number(track.get("disc"), 1) or 1,
                                             number(track.get("track"))))


def find_album(data, album_id):
    for album in data["albums"]:
        if str(album.get("id")) == album_id:
            return album
    raise FormatError("This album is no longer in Format. Return to Albums and refresh.")


def set_metadata(item, source, album, is_album=False):
    tag = item.getMusicInfoTag()
    # Container content does not set the individual item's native media type.
    # Kodi 20+ exposes this separately from local music database identifiers.
    tag.setMediaType("album" if is_album else "song")
    tag.setTitle(text(source.get("title"), "Untitled"))
    tag.setAlbum(text(album.get("title"), "Untitled"))
    tag.setArtist(text(source.get("artist"), text(album.get("artist"), "Unknown artist")))
    tag.setAlbumArtist(text(source.get("albumArtist"), text(album.get("artist"), "Unknown artist")))
    tag.setYear(number(album.get("year")))
    tag.setDuration(number(source.get("duration")))
    tag.setGenres([text(source.get("genre"))] if source.get("genre") else [])
    if not is_album:
        tag.setDisc(number(source.get("disc"), 1) or 1)
        tag.setTrack(number(source.get("track")))


def track_item(server, track, album):
    track_id = str(track["id"])
    item = xbmcgui.ListItem(label=text(track.get("title"), "Untitled"),
                            path=media(server, "/api/audio", track_id), offscreen=True)
    item.setContentLookup(False)
    item.setProperty("IsPlayable", "true")
    set_metadata(item, track, album)
    item.setArt({"thumb": media(server, "/api/cover", track_id), "icon": "DefaultAlbumCover.png"})
    return item


def album_context(album):
    return [("Play album", "RunPlugin({})".format(plugin_url("play_album", album_id=album["id"]))),
            ("Configure Format server", "Addon.OpenSettings({})".format(ADDON_ID))]


def root(handle):
    for title, action in (("Albums", "albums"), ("Configure Format server", "configure")):
        item = xbmcgui.ListItem(label=title, offscreen=True)
        item.setArt({"icon": "DefaultAlbumCover.png"})
        xbmcplugin.addDirectoryItem(handle, plugin_url(action), item, True)


def albums(handle, server, data):
    xbmcplugin.setContent(handle, "albums")
    xbmcplugin.setPluginCategory(handle, "Format albums")
    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_NONE)
    count = 0
    for album in sorted(data["albums"], key=lambda item: (text(item.get("artist")).casefold(),
                                                         text(item.get("title")).casefold())):
        ids = track_ids(album)
        if album.get("id") is None or not ids:
            continue
        label = "{} - {}".format(text(album.get("artist"), "Unknown artist"), text(album.get("title"), "Untitled"))
        item = xbmcgui.ListItem(label=label, offscreen=True)
        set_metadata(item, album, album, is_album=True)
        item.setArt({"thumb": media(server, "/api/cover", ids[0]), "icon": "DefaultAlbumCover.png"})
        item.addContextMenuItems(album_context(album))
        xbmcplugin.addDirectoryItem(handle, plugin_url("album", album_id=album["id"]), item, True)
        count += 1
    if not count:
        xbmcgui.Dialog().notification("Format", "No published albums yet. Check your Format server.",
                                      xbmcgui.NOTIFICATION_INFO, 6000)


def tracks(handle, server, data, album):
    xbmcplugin.setContent(handle, "songs")
    xbmcplugin.setPluginCategory(handle, text(album.get("title"), "Format tracks"))
    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_NONE)
    for track in album_tracks(data, album):
        item = track_item(server, track, album)
        item.addContextMenuItems(album_context(album))
        xbmcplugin.addDirectoryItem(handle, media(server, "/api/audio", track["id"]), item, False)


def play_album(server, data, album):
    # Finish validation and item construction before touching the user's queue.
    prepared = [(media(server, "/api/audio", track["id"]), track_item(server, track, album))
                for track in album_tracks(data, album)]
    playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
    playlist.clear()
    for path, item in prepared:
        playlist.add(path, item)
    playlist.unshuffle()
    xbmc.Player().play(playlist, startpos=0)


def main(argv=None):
    argv = sys.argv if argv is None else argv
    handle = int(argv[1]) if len(argv) > 1 else -1
    args = parse_qs(argv[2].lstrip("?")) if len(argv) > 2 else {}
    action = args.get("action", ["root"])[0]
    succeeded = False
    try:
        if action in ("root", "configure"):
            if action == "configure":
                xbmcaddon.Addon(ADDON_ID).openSettings()
            if handle >= 0:
                root(handle)
        elif action in ("albums", "album", "play_album"):
            server = server_url()
            data = library(server)
            if action == "albums":
                albums(handle, server, data)
            else:
                album = find_album(data, args.get("album_id", [""])[0])
                if action == "album":
                    tracks(handle, server, data, album)
                else:
                    play_album(server, data, album)
        else:
            raise FormatError("Unknown Format action. Open the add-on again from Music add-ons.")
        succeeded = True
    except FormatError as error:
        xbmc.log("Aperture Format: {}".format(error), xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Format", str(error))
    except Exception as error:
        # Avoid logging server response contents, URL credentials or media paths.
        xbmc.log("Aperture Format: unexpected {}".format(type(error).__name__), xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Format", "Format could not complete this action. Check the Kodi log and try again.")
    finally:
        # RunPlugin context-menu actions use handle -1, not a directory handle.
        if handle >= 0:
            xbmcplugin.endOfDirectory(handle, succeeded=succeeded, cacheToDisc=False)


if __name__ == "__main__":
    main()

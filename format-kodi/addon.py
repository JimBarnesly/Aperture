"""Native Format library, catalogue and explicitly confirmed downloads for Kodi 20/21."""
import json
import math
import random
import uuid
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

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
MAX_API_BYTES = 16 * 1024 * 1024
MAX_QUERY_LENGTH = 200
ACQUISITION_STATES = frozenset(("queued", "resolving", "running", "complete", "failed", "cancelled", "cancelling"))
CANCELLABLE_STATES = frozenset(("queued", "resolving", "running"))
SHADOW_STATES = frozenset(("detected", "queued", "resolving", "running", "incomplete", "validating", "published", "failed", "cancelled", "cancelling", "retry_wait", "identifying", "acquiring", "needs_attention", "missing_local_files", "legacy_published_needs_attention"))
MUTATION_CAPABILITIES = {
    "/api/acquire-album": "acquire",
    "/api/acquisitions/cancel": "cancel",
    "/api/acquisitions/prioritize": "prioritize",
}
WRITE_ENDPOINTS = frozenset(MUTATION_CAPABILITIES)
DOWNLOAD_REASON_NOTICES = {
    "disabled": "Downloading disabled on this Format server. Browsing and status are still available.",
    "unsafe_configuration": "Downloading unavailable: the Format server's download configuration needs attention.",
    "storage_unavailable": "Downloading unavailable: the Format server's music storage is unavailable.",
    "downloader_unavailable": "Downloading unavailable: the Format server's downloader is unavailable.",
}
DOWNLOAD_ACTIONS = (
    ("Cancel download", "cancel_download", "cancel", "/api/acquisitions/cancel"),
    ("Move to front", "prioritize_download", "prioritize", "/api/acquisitions/prioritize"),
)
READ_ENDPOINTS = frozenset(("/api/library", "/api/health", "/api/catalog/search", "/api/catalog/album", "/api/acquisitions", "/api/shadow-albums"))


class NoRedirect(HTTPRedirectHandler):
    """Never replay a mutation or send IDs to a redirect destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def urlopen(request, timeout):
    # Refuse even same-origin redirects: a POST may already have taken effect.
    return build_opener(NoRedirect()).open(request, timeout=timeout)


class FormatError(Exception):
    """An error safe to show without exposing the server response or URL."""


class MutationUncertainError(FormatError):
    """The POST was attempted; inspect status rather than repeating it."""


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


def request_json(server, endpoint, params=None, post=False, maximum=None):
    if endpoint not in (WRITE_ENDPOINTS if post else READ_ENDPOINTS):
        raise FormatError("This Format operation is not supported.")
    maximum = MAX_API_BYTES if maximum is None else maximum
    url = server + endpoint + ("?" + urlencode(params) if params else "")
    request = Request(url, data=b"", method="POST") if post else url
    try:
        with urlopen(request, timeout=SOCKET_TIMEOUT_SECONDS) as response:
            deadline = time.monotonic() + LIBRARY_BODY_SECONDS
            payload = bytearray()
            while True:
                if time.monotonic() >= deadline:
                    raise FormatError("Format took too long to return a response. Try again when the server responds.")
                # A read1 call does at most one socket read, allowing the overall
                # budget to stop servers that trickle bytes without timing out.
                chunk = response.read1(min(LIBRARY_CHUNK_BYTES, maximum + 1 - len(payload)))
                if time.monotonic() >= deadline:
                    raise FormatError("Format took too long to return a response. Try again when the server responds.")
                if not chunk:
                    break
                payload.extend(chunk)
                if len(payload) > maximum:
                    raise FormatError("The Format response is too large.")
        return json.loads(payload)
    except HTTPError as error:
        code = error.code
        error.close()
        raise FormatError("Format returned HTTP {}. Check the server address and access.".format(code)) from error
    except (URLError, TimeoutError, OSError) as error:
        raise FormatError("Cannot reach Format. Check the server is running and this device can reach it.") from error
    except (ValueError, UnicodeError, RecursionError) as error:
        raise FormatError("The server did not return a valid Format response. Check the server URL.") from error


def library(server):
    data = request_json(server, "/api/library", maximum=MAX_LIBRARY_BYTES)
    if (not isinstance(data, dict)
            or not object_list(data.get("albums"))
            or not object_list(data.get("tracks"))):
        raise FormatError("The server returned an unsupported Format library.")
    return data


def object_list(value):
    return isinstance(value, list) and all(isinstance(item, dict) for item in value)


def identifier(value):
    # Mutation IDs must be actual server strings, never derived from display labels.
    return isinstance(value, str) and 0 < len(value) <= 2048 and not any(ord(c) < 32 for c in value)


def download_access(server):
    """Read independent capabilities; readiness text never grants permission."""
    permissions = {capability: False for capability in MUTATION_CAPABILITIES.values()}
    unavailable = "Downloading unavailable: cannot verify Format server permissions. Browsing and status are still available."
    try:
        health = request_json(server, "/api/health", maximum=64 * 1024)
    except FormatError:
        return permissions, {key: unavailable for key in permissions}
    if not isinstance(health, dict):
        return permissions, {key: unavailable for key in permissions}
    if "capabilities" in health:
        capabilities = health["capabilities"]
        if isinstance(capabilities, dict):
            permissions = {key: capabilities.get(key) is True for key in permissions}
        # Presence is authoritative, including malformed objects and missing keys.
        # A broad readOnly:false must never override a narrow capability denial.
        notices = {
            "acquire": "Downloading unavailable: this Format server has not enabled album acquisition. Browsing and status are still available.",
            "cancel": "This Format server does not allow cancelling downloads.",
            "prioritize": "This Format server does not allow changing download priority.",
        }
        downloads = health.get("downloads")
        reason = downloads.get("reason") if isinstance(downloads, dict) else None
        if not permissions["acquire"] and isinstance(reason, str) and reason in DOWNLOAD_REASON_NOTICES:
            notices["acquire"] = DOWNLOAD_REASON_NOTICES[reason]
    elif health.get("readOnly") is False:
        # Compatibility with older servers that do not expose capabilities at all.
        permissions = {key: True for key in permissions}
        notices = {key: "Downloads are saved to your Format server." for key in permissions}
    elif health.get("readOnly") is True:
        message = "Downloading disabled: this Format server is read-only. Browsing and status are still available."
        notices = {key: message for key in permissions}
    else:
        message = "Downloading unavailable: the Format server did not confirm download permissions."
        notices = {key: message for key in permissions}
    if permissions["acquire"]:
        notices["acquire"] = "Downloads are saved to your Format server."
    return permissions, notices


def require_capability(server, capability):
    if capability not in MUTATION_CAPABILITIES.values():
        raise FormatError("This Format download action is not supported.")
    permissions, notices = download_access(server)
    if not permissions[capability]:
        raise FormatError(notices[capability])


def mutate(server, endpoint, item_id):
    if endpoint not in WRITE_ENDPOINTS or not identifier(item_id):
        raise FormatError("This Format download action is invalid.")
    # Recheck after the confirmation dialog: permission can change while it is open.
    require_capability(server, MUTATION_CAPABILITIES[endpoint])
    try:
        result = request_json(server, endpoint, {"id": item_id}, post=True, maximum=256 * 1024)
        if (not isinstance(result, dict) or not identifier(result.get("id"))
                or not isinstance(result.get("status"), str) or result["status"] not in ACQUISITION_STATES):
            raise FormatError("Invalid download response.")
        if endpoint != "/api/acquire-album" and result["id"] != item_id:
            raise FormatError("Unexpected download identity.")
    except Exception as error:
        # A timeout, bad JSON or a redirect does not establish whether the POST
        # executed. Never retry it, and never expose raw server diagnostics.
        raise MutationUncertainError("Format could not confirm the download action. Check Downloads before trying again; the action may already have happened.") from error
    return result


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
    tag.setTitle(display(source.get("title"), "Untitled"))
    tag.setAlbum(display(album.get("title"), "Untitled"))
    tag.setArtist(display(source.get("artist"), display(album.get("artist"), "Unknown artist")))
    tag.setAlbumArtist(display(source.get("albumArtist"), display(album.get("artist"), "Unknown artist")))
    tag.setYear(number(album.get("year")))
    tag.setDuration(number(source.get("duration")))
    tag.setGenres([display(source.get("genre"))] if source.get("genre") else [])
    if not is_album:
        tag.setDisc(number(source.get("disc"), 1) or 1)
        tag.setTrack(number(source.get("track")))


def track_item(server, track, album):
    track_id = str(track["id"])
    item = xbmcgui.ListItem(label=display(track.get("title"), "Untitled"),
                            path=media(server, "/api/audio", track_id), offscreen=True)
    item.setContentLookup(False)
    item.setProperty("IsPlayable", "true")
    set_metadata(item, track, album)
    display_properties(item, track)
    item.setArt({"thumb": media(server, "/api/cover", track_id), "icon": "DefaultAlbumCover.png"})
    return item


def album_context(album):
    return [("Play album", "RunPlugin({})".format(plugin_url("play_album", album_id=album["id"]))),
            ("Browse tracks", "Container.Update({})".format(plugin_url("album", album_id=album["id"]))),
            ("Configure Format server", "Addon.OpenSettings({})".format(ADDON_ID))]


def set_view(handle, mode, content="files", category="Music", notice=""):
    xbmcplugin.setContent(handle, content)
    xbmcplugin.setPluginCategory(handle, category)
    xbmcplugin.setProperty(handle, "Aperture.FormatView", mode)
    xbmcplugin.setProperty(handle, "Aperture.FormatTitle", category)
    xbmcplugin.setProperty(handle, "Aperture.FormatNotice", notice)
    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_NONE)


def display(value, fallback=""):
    # Kodi labels support formatting tags. Server metadata is plain text, not markup.
    value = text(value, fallback) if isinstance(value, (str, int, float)) or value is None else fallback
    value = "".join(character if character.isprintable() else " " for character in value[:2048])
    return " ".join(value.replace("[", "(").replace("]", ")").split())[:240]


def display_properties(item, source, status="", detail="", progress=""):
    item.setProperty("Aperture.FormatTitle", display(source.get("title"), "Untitled"))
    item.setProperty("Aperture.FormatArtist", display(source.get("artist"), "Unknown artist"))
    item.setProperty("Aperture.FormatStatus", status)
    item.setProperty("Aperture.FormatDetail", detail)
    item.setProperty("Aperture.FormatProgress", str(progress))


def menu_item(handle, label, action="noop", folder=False, detail="", source=None,
              status="", progress="", art=None, context=None, **params):
    item = xbmcgui.ListItem(label=label, offscreen=True)
    item.setArt({"icon": "DefaultAlbumCover.png"})
    item.setProperty("IsPlayable", "false")
    item.setProperty("Aperture.FormatDetail", detail)
    if source is not None:
        display_properties(item, source, status, detail, progress)
    if art:
        item.setArt(art)
    if context:
        item.addContextMenuItems(context)
    # Kodi copies the ListItem here: all annotations must precede this call.
    xbmcplugin.addDirectoryItem(handle, plugin_url(action, **params), item, folder)
    return item


def root(handle):
    set_view(handle, "menu")
    for title, action in (("Albums", "albums"), ("Artists", "artists"),
                          ("Search library", "search"), ("Find music", "find_music"),
                          ("Downloads", "downloads"), ("Configure Format server", "configure")):
        menu_item(handle, title, action, action not in ("search", "find_music", "configure"))


def albums(handle, server, data, artist=None):
    set_view(handle, "albums", "albums", display(artist, "Albums"))
    count = 0
    entry = uuid.uuid4().hex
    xbmcplugin.setProperty(handle, "Aperture.FormatEntry", entry)
    for album in sorted(data["albums"], key=lambda item: (text(item.get("artist")).casefold(),
                                                         text(item.get("title")).casefold())):
        if artist is not None and text(album.get("artist"), "Unknown artist").casefold() != artist.casefold():
            continue
        if add_album(handle, server, album, position=count + 1):
            count += 1
    if not count:
        xbmcgui.Dialog().notification("Format", "No published albums yet. Check your Format server.",
                                      xbmcgui.NOTIFICATION_INFO, 6000)
    return count, entry


def focus_random_album(count, entry):
    """Choose a record, not a parent-folder card; never shuffle or play it."""
    if not count:
        return False
    target = random.randint(1, count)
    monitor = xbmc.Monitor()
    try:
        for _ in range(20):
            if (monitor.abortRequested() or xbmc.getSkinDir() != "skin.aperture"
                    or xbmcgui.getCurrentWindowId() != 10502
                    or xbmcgui.getCurrentWindowDialogId() not in (9999, 10138)):
                return False
            if (xbmcgui.getCurrentWindowDialogId() == 9999
                    and xbmc.getInfoLabel("Container.Property(Aperture.FormatEntry)") == entry
                    and xbmc.getCondVisibility("Control.IsVisible(64)")):
                # Kodi may insert one parent-folder item. Match our per-album
                # property instead of guessing whether the native index is +1.
                if xbmc.getInfoLabel("System.CurrentControlId") not in ("0", "50", "63", "64", ""):
                    return False
                for index in (target - 1, target):
                    if xbmc.getInfoLabel("Container(64).ListItemAbsolute({}).Property(Aperture.FormatPosition)".format(index)) == str(target):
                        if xbmc.getInfoLabel("Container.Property(Aperture.FormatEntry)") != entry:
                            return False
                        xbmc.executebuiltin("Control.SetFocus(64,{},absolute)".format(index))
                        return True
            if monitor.waitForAbort(0.1):
                return False
    except Exception as error:
        xbmc.log("Aperture Format: initial shelf focus unavailable ({})".format(type(error).__name__), xbmc.LOGERROR)
    return False


def tracks(handle, server, data, album):
    set_view(handle, "tracks", "songs", display(album.get("title"), "Format tracks"))
    for track in album_tracks(data, album):
        item = track_item(server, track, album)
        item.addContextMenuItems(album_context(album))
        xbmcplugin.addDirectoryItem(handle, media(server, "/api/audio", track["id"]), item, False)


def presentation_origin(allow_busy=False):
    """Only explicit playback from Aperture's Format browser can open its player."""
    try:
        if (xbmc.getSkinDir() != "skin.aperture" or xbmcgui.getCurrentWindowId() != 10502
                or xbmcgui.getCurrentWindowDialogId() not in ((9999, 10138) if allow_busy else (9999,))
                or xbmc.getInfoLabel("Container.PluginName") != ADDON_ID):
            return None
        return xbmc.getInfoLabel("Container.FolderPath")
    except Exception:
        return None


def show_now_playing(path, origin, player=None):
    """Wait briefly for this exact stream; never steal later navigation or retry it."""
    if origin is None:
        return False
    try:
        return _show_now_playing(path, origin, player)
    except Exception as error:
        # Presentation is optional after playback has started/resolved. Never
        # fail an already-resolved handle or expose paths from a GUI error.
        xbmc.log("Aperture Format: now-playing presentation unavailable ({})".format(type(error).__name__), xbmc.LOGERROR)
        return False


def _show_now_playing(path, origin, player):
    player = player or xbmc.Player()
    monitor = xbmc.Monitor()
    for _ in range(50):
        # Kodi can show its own cancellable busy dialog while opening this
        # stream. Wait for it to close; user dialogs still cancel presentation.
        if monitor.abortRequested() or presentation_origin(allow_busy=True) != origin:
            return False
        try:
            # isPlayingAudio becomes true before Kodi opens its playback-busy
            # dialog. Require the actual stream clock too, or a queued window
            # activation can race that dialog and be refused by Kodi.
            ready = (player.isPlayingAudio() and player.getPlayingFile() == path
                     and player.getTime() >= 0.1)
        except RuntimeError:
            ready = False  # A player can disappear between read-only calls.
        if ready and presentation_origin() == origin:
            xbmc.executebuiltin("ActivateWindow(visualisation)")
            return True
        if monitor.waitForAbort(0.1):
            return False
    return False


def play_album(server, data, album):
    # Finish validation and item construction before touching the user's queue.
    prepared = [(media(server, "/api/audio", track["id"]), track_item(server, track, album))
                for track in album_tracks(data, album)]
    playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
    playlist.clear()
    for path, item in prepared:
        playlist.add(path, item)
    playlist.unshuffle()
    origin = presentation_origin()
    player = xbmc.Player()
    player.play(playlist, startpos=0)
    show_now_playing(prepared[0][0], origin, player)


def add_album(handle, server, album, prefix="", position=0):
    ids = track_ids(album)
    if album.get("id") is None or not ids:
        return False
    label = "{}{} - {}".format(prefix, display(album.get("artist"), "Unknown artist"), display(album.get("title"), "Untitled"))
    item = xbmcgui.ListItem(label=label, offscreen=True)
    set_metadata(item, album, album, is_album=True)
    display_properties(item, album)
    item.setArt({"thumb": media(server, "/api/cover", ids[0]), "icon": "DefaultAlbumCover.png"})
    # One-based shelf position is presentation metadata, never a media/database ID.
    item.setProperty("Aperture.FormatPosition", str(position))
    item.addContextMenuItems(album_context(album))
    # Selecting a release is an explicit whole-album play action. Do not let
    # Kodi resolve this plugin route as a single media stream or a directory.
    item.setProperty("IsPlayable", "false")
    xbmcplugin.addDirectoryItem(handle, plugin_url("play_album", album_id=album["id"]), item, False)
    return True


def artists(handle, server, data):
    set_view(handle, "menu", "artists", "Artists")
    grouped = {}
    for album in data["albums"]:
        if album.get("id") is None or not track_ids(album):
            continue
        artist = text(album.get("artist"), "Unknown artist")
        group = grouped.setdefault(artist.casefold(), {"name": artist, "albums": []})
        group["albums"].append(album)
    for key in sorted(grouped):
        group = grouped[key]
        count = len(group["albums"])
        menu_item(handle, display(group["name"]), "artist", True,
                  detail="{} album{}".format(count, "" if count == 1 else "s"), artist=group["name"],
                  art={"thumb": media(server, "/api/cover", track_ids(group["albums"][0])[0])})
    if not grouped:
        menu_item(handle, "No published artists yet")


def search_query(args, heading, minimum=1):
    value = args.get("q", [None])[0]
    if value is None:
        value = xbmcgui.Dialog().input(heading)
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if len(value) < minimum or len(value) > MAX_QUERY_LENGTH:
        raise FormatError("Enter between {} and {} characters.".format(minimum, MAX_QUERY_LENGTH))
    return value


def search_library(handle, server, data, query):
    set_view(handle, "menu", "files", "Library: " + display(query))
    needle = query.casefold()
    count = 0
    for album in data["albums"]:
        if any(needle in text(album.get(field)).casefold() for field in ("title", "artist")):
            count += bool(add_album(handle, server, album, "Album: "))
    # Only published album members are searchable/playable. Orphan/staging tracks
    # cannot leak into the library search even if a malformed server includes them.
    membership = {}
    for album in data["albums"]:
        for track_id in track_ids(album):
            membership.setdefault(track_id, album)
    for track in data["tracks"]:
        album = membership.get(str(track.get("id")))
        if album is None or not any(needle in text(track.get(field)).casefold() for field in ("title", "artist")):
            continue
        item = track_item(server, track, album)
        item.addContextMenuItems(album_context(album))
        xbmcplugin.addDirectoryItem(handle, media(server, "/api/audio", track["id"]), item, False)
        count += 1
    if not count:
        menu_item(handle, "No matching albums or tracks in your library")


def find_music(handle, server, query):
    data = request_json(server, "/api/catalog/search", {"q": query})
    if (not isinstance(data, dict) or not object_list(data.get("albums"))
            or (data.get("artist") is not None and not isinstance(data.get("artist"), dict))):
        raise FormatError("Format returned an unsupported artist catalogue.")
    artist = data.get("artist") or {}
    _, notices = download_access(server)
    notice = notices["acquire"]
    set_view(handle, "catalog", "files", "Find music: " + display(artist.get("name"), query),
             "Artist catalogue: up to 100 studio album releases. " + notice)
    menu_item(handle, "Artist catalogue: up to 100 studio album releases", detail=notice)
    for album in data["albums"][:100]:
        if not identifier(album.get("id")):
            continue
        label = display(album.get("title"), "Untitled")
        if album.get("year"):
            label += " ({})".format(display(album["year"]))
        if album.get("owned") is True:
            label += " - In your library"
        menu_item(handle, label, "catalog_album", True, album_id=album["id"],
                  source=dict(album, artist=artist.get("name")),
                  status="In your library" if album.get("owned") is True else "Catalogue")
        # The catalogue cover field points to external providers, not our server.
        # Do not let Kodi request it outside the configured Format destination.
    if not data["albums"]:
        menu_item(handle, "No matching studio albums. Try another artist name.")


def catalogue_preview(server, album_id):
    if not identifier(album_id):
        raise FormatError("Select an album from Find music first.")
    album = request_json(server, "/api/catalog/album", {"id": album_id})
    if (not isinstance(album, dict) or album.get("id") != album_id
            or not isinstance(album.get("artist"), str) or not album["artist"].strip()
            or not isinstance(album.get("title"), str) or not album["title"].strip()
            or not object_list(album.get("tracks")) or not album["tracks"]):
        raise FormatError("Format returned an unsupported catalogue album. Search for it again.")
    return album


def catalogue_album(handle, server, album_id):
    album = catalogue_preview(server, album_id)
    permissions, notices = download_access(server)
    notice = notices["acquire"]
    set_view(handle, "catalog", "files", display(album["title"]), notice)
    if permissions["acquire"]:
        menu_item(handle, "Download album", "acquire", False,
                  detail="Download to your Format server", album_id=album["id"],
                  source=album, status="Available to download")
    else:
        menu_item(handle, notice)
    for track in album["tracks"]:
        label = "{}.{}  {}".format(number(track.get("disc"), 1) or 1,
                                    number(track.get("position")), display(track.get("title"), "Untitled"))
        menu_item(handle, label, detail="Catalogue preview; not in the playback queue",
                  source=dict(track, artist=track.get("artist", album["artist"])), status="Preview")


def acquire(server, album_id):
    require_capability(server, "acquire")
    album = catalogue_preview(server, album_id)
    message = "Download {} - {} to your Format server? Only download music you have the right to obtain.".format(
        display(album["artist"]), display(album["title"]))
    if xbmcgui.Dialog().yesno("Download album", message) is not True:
        return False
    mutate(server, "/api/acquire-album", album["id"])
    return True


def status_list(server, endpoint):
    items = request_json(server, endpoint)
    if not object_list(items):
        raise FormatError("Format returned an unsupported download status list.")
    return items


def acquisition_detail(source):
    state = source.get("status")
    if not isinstance(state, str) or state not in ACQUISITION_STATES:
        return "Unknown", "Refresh to check this download", ""
    progress = min(100, number(source.get("progress")))
    if source.get("cancelRequested") is True and state in CANCELLABLE_STATES:
        return "Cancellation requested", "Waiting for the server to stop this download", ""
    detail = ""
    if state == "queued":
        position = number(source.get("queuePosition"))
        detail = "Queue position {}".format(position) if position else "Waiting to start"
    elif state == "running":
        detail = "Finalising album" if progress == 100 else "{}% downloaded".format(progress)
    elif state == "failed":
        detail = "Download failed. Check the Format server for details."
    return state.capitalize(), detail, str(progress) if state in ("running", "complete") else ""


def available_download_actions(item, permissions):
    state = item.get("status")
    if (not isinstance(state, str) or state not in CANCELLABLE_STATES
            or item.get("cancelRequested") is True):
        return []
    return [action for action in DOWNLOAD_ACTIONS
            if permissions.get(action[2]) is True
            and ((action[2] == "cancel" and item.get("publicationStarted") is not True)
                 or (action[2] == "prioritize" and state == "queued"))]


def downloads(handle, server):
    permissions, notices = download_access(server)
    notice = notices["acquire"]
    set_view(handle, "downloads", "files", "Downloads", notice)
    menu_item(handle, "Refresh downloads", "downloads", True, detail="Refresh status only")
    if not permissions["acquire"]:
        menu_item(handle, notice)
    # Each source can still be useful when the other is temporarily unavailable.
    for endpoint, shadow in (("/api/acquisitions", False), ("/api/shadow-albums", True)):
        try:
            items = status_list(server, endpoint)
        except FormatError:
            menu_item(handle, "Shadow album status unavailable" if shadow else "Download status unavailable")
            continue
        if not items:
            menu_item(handle, "No shadow albums" if shadow else "No downloads yet")
        for source in items:
            if shadow:
                status = source.get("status")
                status = status.replace("_", " ").capitalize() if isinstance(status, str) and status in SHADOW_STATES else "Unknown"
                manifest = source.get("manifest") if object_list(source.get("manifest")) else []
                validated = sum(track.get("status") in ("validated", "published") for track in manifest)
                expected = number(source.get("expectedTrackCount")) or len(manifest)
                detail = "{} local / {} validated / {} expected".format(
                    number(source.get("localTrackCount")), validated, expected or "?")
                state = "Shadow: " + status
                progress = ""
            else:
                state, detail, progress = acquisition_detail(source)
            label = "{} - {} | {}".format(display(source.get("artist"), "Unknown artist"),
                                          display(source.get("title"), "Untitled"), state)
            item_id = source.get("id")
            choices = available_download_actions(source, permissions) if not shadow and identifier(item_id) else []
            interactive = bool(choices)
            actions = [(choice[0], "RunPlugin({})".format(plugin_url(choice[1], acquisition_id=item_id)))
                       for choice in choices]
            menu_item(handle, label, "download" if interactive else "noop", False,
                      detail=detail, source=source, status=state, progress=progress, context=actions,
                      **({"acquisition_id": item_id} if interactive else {}))


def download_action(server, item_id, action=None):
    permissions, notices = download_access(server)
    by_action = {choice[1]: choice for choice in DOWNLOAD_ACTIONS}
    if action is not None:
        if action not in by_action:
            raise FormatError("This download action is not supported.")
        capability = by_action[action][2]
        if not permissions[capability]:
            raise FormatError(notices[capability])
    elif not permissions["cancel"] and not permissions["prioritize"]:
        raise FormatError("Download controls are unavailable. Browsing and status are still available.")
    if not identifier(item_id):
        raise FormatError("Select a download from the current Downloads list.")
    matches = [item for item in status_list(server, "/api/acquisitions") if item.get("id") == item_id]
    if (len(matches) != 1 or not isinstance(matches[0].get("status"), str)
            or matches[0]["status"] not in CANCELLABLE_STATES or matches[0].get("cancelRequested") is True):
        raise FormatError("This download is no longer active or queued. Refresh Downloads.")
    item = matches[0]
    if action == "cancel_download" and item.get("publicationStarted") is True:
        raise FormatError("This album is being finalised and can no longer be cancelled. Refresh Downloads.")
    choices = available_download_actions(item, permissions)
    if not choices:
        if item.get("publicationStarted") is True:
            raise FormatError("This album is being finalised. Download controls are no longer available.")
        raise FormatError("No permitted controls are available for this download. Refresh Downloads.")
    if action is None:
        selected = xbmcgui.Dialog().select("Download actions", [choice[0] for choice in choices])
        if type(selected) is not int or not 0 <= selected < len(choices):
            return False
        action = choices[selected][1]
    choice = by_action[action]
    if choice not in choices:
        raise FormatError("Only queued downloads can move to the front. Refresh Downloads.")
    title, _, _, endpoint = choice
    message = "{}: {} - {}?".format(title, display(item.get("artist"), "Unknown artist"), display(item.get("title"), "Untitled"))
    if xbmcgui.Dialog().yesno(title, message) is not True:
        return False
    mutate(server, endpoint, item_id)
    return True


def main(argv=None):
    argv = sys.argv if argv is None else argv
    handle = int(argv[1]) if len(argv) > 1 else -1
    args = parse_qs(argv[2].lstrip("?")) if len(argv) > 2 else {}
    action = args.get("action", ["root"])[0]
    succeeded = False
    changed = False
    redirect = None
    view = "menu"
    shelf_entry = None
    try:
        if action in ("acquire", "download", "cancel_download", "prioritize_download") and handle >= 0:
            raise FormatError("Select this action from Find music or Downloads, not as a saved folder.")
        if action in ("root", "configure"):
            if action == "configure":
                xbmcaddon.Addon(ADDON_ID).openSettings()
                xbmc.executebuiltin("Container.Refresh")
            if handle >= 0:
                root(handle)
        elif action in ("search", "find_music"):
            query = search_query(args, "Search your Format library" if action == "search" else "Find music by artist (at least 2 characters)",
                                 minimum=1 if action == "search" else 2)
            if query is None:
                if handle >= 0:
                    root(handle)
            elif "q" not in args or handle < 0:
                # Store the query in the directory URL, not a transient prompt,
                # so Back and refresh never repeat the keyboard dialog.
                redirect = plugin_url(action, q=query)
            else:
                server = server_url()
                if action == "search":
                    search_library(handle, server, library(server), query)
                else:
                    view = "catalog"
                    find_music(handle, server, query)
        elif action in ("albums", "artists", "artist", "album", "play_album"):
            server = server_url()
            data = library(server)
            if action in ("albums", "artist"):
                view = "albums"
                shelf_entry = albums(handle, server, data, args.get("artist", [None])[0] if action == "artist" else None)
            elif action == "artists":
                artists(handle, server, data)
            else:
                album = find_album(data, args.get("album_id", [""])[0])
                if action == "album":
                    view = "tracks"
                    tracks(handle, server, data, album)
                else:
                    play_album(server, data, album)
        elif action in ("catalog_album", "acquire"):
            server = server_url()
            album_id = args.get("album_id", [""])[0]
            if action == "acquire":
                changed = acquire(server, album_id)
                if changed:
                    redirect = plugin_url("downloads")
            elif handle >= 0:
                view = "catalog"
                catalogue_album(handle, server, album_id)
        elif action in ("downloads", "download", "cancel_download", "prioritize_download"):
            server = server_url()
            if action != "downloads":
                changed = download_action(server, args.get("acquisition_id", [""])[0], None if action == "download" else action)
            if handle >= 0:
                view = "downloads"
                downloads(handle, server)
        elif action != "noop":
            raise FormatError("Unknown Format action. Open the add-on again from Music add-ons.")
        succeeded = True
    except FormatError as error:
        changed = changed or isinstance(error, MutationUncertainError)
        if isinstance(error, MutationUncertainError) and action == "acquire":
            redirect = plugin_url("downloads")
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
            if succeeded and not redirect and xbmc.getSkinDir() == "skin.aperture":
                xbmc.executebuiltin("Container.SetViewMode({})".format(64 if view == "albums" else 63))
                if shelf_entry is not None:
                    focus_random_album(*shelf_entry)
        if redirect:
            # Non-folder actions never enter history. Do not use 'replace', which
            # clears Kodi's complete Back stack for query-only plugin routes.
            xbmc.executebuiltin("Container.Update({})".format(redirect))
        elif changed:
            xbmc.executebuiltin("Container.Refresh")


if __name__ == "__main__":
    main()

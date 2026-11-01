import json
import sys
from urllib.parse import urlencode, parse_qs, urlparse
from urllib.request import urlopen

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE = sys.argv[0]
SERVER = ADDON.getSetting("server_url").strip().rstrip("/")
if not SERVER:
    SERVER = "http://192.168.68.60:4534"


def url(path, **kwargs):
    return BASE + "?" + urlencode(dict(action=path, **kwargs))


def api(path, **kwargs):
    with urlopen(SERVER + path + ("?" + urlencode(kwargs) if kwargs else ""), timeout=12) as response:
        return json.load(response)


def media(path, track_id):
    return SERVER + path + "?" + urlencode({"id": track_id})


def add_folder(title, target, **kwargs):
    item = xbmcgui.ListItem(label=title)
    item.setArt({"icon": "DefaultAlbumCover.png"})
    xbmcplugin.addDirectoryItem(HANDLE, url(target, **kwargs), item, True)


def library():
    return api("/api/library")


def albums():
    data = library()
    for album in sorted(data.get("albums", []), key=lambda a: (str(a.get("artist", "")).lower(), str(a.get("title", "")).lower())):
        ids = album.get("trackIds") or []
        if not ids:
            continue
        title = "{} — {}".format(album.get("artist", "Unknown"), album.get("title", "Untitled"))
        item = xbmcgui.ListItem(label=title)
        item.setArt({"thumb": media("/api/cover", ids[0]), "icon": media("/api/cover", ids[0])})
        xbmcplugin.addDirectoryItem(HANDLE, url("album", ids=",".join(ids), title=title), item, True)


def tracks(ids):
    data = library()
    lookup = {str(t.get("id")): t for t in data.get("tracks", [])}
    for tid in ids:
        track = lookup.get(tid)
        if not track:
            continue
        item = xbmcgui.ListItem(label=track.get("title") or "Untitled", path=media("/api/audio", tid))
        item.setInfo("music", {"title": track.get("title", ""), "artist": track.get("artist", ""), "album": track.get("album", ""), "tracknumber": int(track.get("track") or 0)})
        item.setArt({"thumb": media("/api/cover", tid)})
        item.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(HANDLE, media("/api/audio", tid), item, False)


def main():
    args = parse_qs(sys.argv[2].lstrip("?"))
    action = args.get("action", ["root"])[0]
    xbmcplugin.setContent(HANDLE, "albums" if action != "album" else "songs")
    try:
        if action == "root":
            add_folder("Albums", "albums")
            add_folder("Configure Format server", "configure")
        elif action == "albums":
            albums()
        elif action == "album":
            tracks([i for i in args.get("ids", [""])[0].split(",") if i])
        elif action == "configure":
            ADDON.openSettings()
    except Exception as error:
        xbmc.log("Aperture Format: {}".format(error), xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Format", "Cannot reach Format server. Check add-on settings.", xbmcgui.NOTIFICATION_ERROR, 6000)
    finally:
        xbmcplugin.endOfDirectory(HANDLE, succeeded=True)


if __name__ == "__main__":
    main()

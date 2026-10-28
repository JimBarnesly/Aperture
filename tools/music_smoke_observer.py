# SPDX-License-Identifier: GPL-3.0-or-later
"""TEST ONLY: in-process observer/fixture scanner for a disposable Kodi profile.

Never bundled in release ZIPs. No network listener, arbitrary RPC command, real
media path or user's Kodi profile is accepted. The only writes requested from
Kodi are scanning the labelled local fixture and stopping its test playback.
"""
import json
import os
from pathlib import Path
import time

import xbmc
import xbmcaddon
import xbmcgui

LABEL = "SYNTHETIC QA"
SERVICE_ID = "service.apeture.musicsmoke"


def rpc(method, **params):
    reply = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1,
                                                     "method": method, "params": params})))
    if not isinstance(reply, dict) or "error" in reply or "result" not in reply:
        raise RuntimeError("Synthetic music observer RPC failed: " + method)
    return reply["result"]


def atomic(path, payload):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False))
    temporary.replace(path)


def verified_config():
    addon_path = Path(xbmcaddon.Addon(SERVICE_ID).getAddonInfo("path")).resolve()
    config = json.loads((addon_path / "config.json").read_text())
    runtime = Path(config["runtime"]).resolve()
    if not runtime.name.startswith("apeture-kodi-smoke.") or config.get("label") != LABEL:
        raise RuntimeError("Not an explicit disposable music fixture")
    if addon_path != runtime / "system/addons" / SERVICE_ID:
        raise RuntimeError("Observer is not inside the disposable system")
    if Path(os.environ.get("KODI_HOME", "")).resolve() != runtime / "system":
        raise RuntimeError("Refusing a nonfixture Kodi system")
    if Path(os.environ.get("KODI_DATA", "")).resolve() != runtime / "data":
        raise RuntimeError("Refusing a nonfixture Kodi profile")
    if Path(config["fixture"]).resolve() != runtime / "synthetic-music":
        raise RuntimeError("Refusing a nonfixture media path")
    marker = json.loads((runtime / ".apeture-music-smoke.json").read_text())
    if marker != config or not config.get("token"):
        raise RuntimeError("Music fixture marker mismatch")
    if rpc("Settings.GetSettingValue", setting="musiclibrary.downloadinfo").get("value") is not False:
        raise RuntimeError("Fixture metadata downloading must be disabled")
    return config


def snapshot(config, sequence, last_command):
    window_id = xbmcgui.getCurrentWindowId()
    window = xbmcgui.Window(window_id)
    try:
        focus = window.getFocusId()
    except RuntimeError:
        focus = -1
    keys = ("Ready", "Status", "Detail", "Primary", "Error", "Title", "Artist", "Year", "Position")
    properties = {key.lower(): window.getProperty("Shelf." + key) for key in keys}
    properties["covers"] = [{"visible": window.getProperty("Shelf.Cover{}.Visible".format(i)),
                             "art": window.getProperty("Shelf.Cover{}.Art".format(i))} for i in range(7)]
    result = rpc("AudioLibrary.GetAlbums", properties=["title", "artist", "year"],
                 sort={"method": "label", "order": "ascending"})
    albums = result.get("albums", [])
    expected_titles = {album["title"] for album in config["expected"]["albums"]}
    if any(album.get("title") not in expected_titles for album in albums):
        raise RuntimeError("Nonfixture album found; observer refuses this library")
    if result.get("limits", {}).get("total", len(albums)) > 7:
        raise RuntimeError("Unexpected library size in synthetic profile")
    album_ids = {album["albumid"] for album in albums}
    def fixture_file(path):
        return bool(path) and Path(path).resolve().is_relative_to(Path(config["fixture"]))
    songs = rpc("AudioLibrary.GetSongs", properties=["title", "album", "albumid", "disc", "track", "file"]).get("songs", [])
    if any(not fixture_file(song.get("file", "")) for song in songs):
        raise RuntimeError("Nonfixture song found; observer refuses this library")
    active = rpc("Player.GetActivePlayers")
    audio = next((player for player in active if player.get("type") == "audio"), None)
    player = None
    if audio is not None:
        item = rpc("Player.GetItem", playerid=audio["playerid"],
                   properties=["title", "album", "albumid", "disc", "track", "file"])["item"]
        if item.get("albumid") not in album_ids and not fixture_file(item.get("file", "")):
            raise RuntimeError("Nonfixture audio is playing; observer refuses further actions")
        player = {"id": audio["playerid"], "item": item,
                  "properties": rpc("Player.GetProperties", playerid=audio["playerid"],
                                    properties=["speed", "position", "playlistid", "shuffled", "time"])}
    queue = rpc("Playlist.GetItems", playlistid=0,
                properties=["title", "album", "albumid", "disc", "track", "file"]).get("items", [])
    for item in queue:
        path = item.get("file", "")
        if path and not fixture_file(path):
            raise RuntimeError("Nonfixture item found in music queue")
    return {"sequence": sequence, "time": time.time(), "pid": os.getpid(), "label": LABEL,
            "window": window_id, "dialog": xbmcgui.getCurrentWindowDialogId(), "focus": focus,
            "skin": xbmc.getSkinDir(), "shelf": properties,
            "shelf_open": xbmcgui.Window(10000).getProperty("Apeture.Music.Open"),
            "music_enabled": bool(xbmc.getCondVisibility("System.AddonIsEnabled(script.apeture.music)")),
            "scanning": bool(xbmc.getCondVisibility("Library.IsScanningMusic")),
            "albums": albums, "songs": songs, "player": player, "queue": queue, "last_command": last_command}


def main():
    config = verified_config()
    out = Path(config["out"])
    monitor = xbmc.Monitor()
    sequence = 0
    last_command = None
    seen = set()
    scanned = False
    with (out / "music-states.jsonl").open("a", buffering=1) as history:
        while not monitor.abortRequested():
            sequence += 1
            current = snapshot(config, sequence, last_command)
            history.write(json.dumps(current, ensure_ascii=False) + "\n")
            atomic(out / "music-state.json", current)
            command_path = out / "music-command.json"
            if command_path.exists():
                command = json.loads(command_path.read_text())
                identifier, action = command.get("id"), command.get("action")
                if not isinstance(identifier, str) or not identifier or len(identifier) > 80:
                    raise RuntimeError("Invalid synthetic test command identity")
                if set(command) != {"id", "action"} or action not in ("scan", "stop"):
                    raise RuntimeError("Only fixed fixture scan/stop commands are allowed")
                if identifier not in seen:
                    seen.add(identifier)
                    if action == "scan":
                        if scanned:
                            raise RuntimeError("Fixture scan may be requested only once")
                        scanned = True
                        rpc("AudioLibrary.Scan", directory=config["fixture"] + os.sep, showdialogs=False)
                    elif current["player"] is not None:
                        rpc("Player.Stop", playerid=current["player"]["id"])
                    last_command = {"id": identifier, "action": action, "status": "accepted"}
            if monitor.waitForAbort(0.15):
                break


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Only the isolated CI observer writes this; never include private payloads.
        path = Path(xbmcaddon.Addon(SERVICE_ID).getAddonInfo("path")) / "config.json"
        config = json.loads(path.read_text())
        out = Path(config["out"])
        atomic(out / "music-error.json", {"error": type(exc).__name__, "reason": str(exc), "label": LABEL})
        raise

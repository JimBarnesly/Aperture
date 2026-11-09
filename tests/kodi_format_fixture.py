#!/usr/bin/env python3
"""Disposable CI-only Format source. Never point this at a user's Kodi profile.

prepare creates original WAV/PNG fixtures and an observation-only Kodi service.
serve binds 127.0.0.1 on an OS-selected port, writes settings, then ready.json.
Mock acquisition endpoints only alter this disposable fixture's JSON. They never
contact a provider or acquire files. An offline marker simulates an outage.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import shutil
import struct
import threading
import time
from urllib.parse import parse_qs, urlsplit
import uuid
import wave
import xml.etree.ElementTree as ET
import zlib

ROOT = Path(__file__).resolve().parents[1]
ADDON = "plugin.audio.aperture.format"
OBSERVER = "service.aperture.formatsmoke"
LABEL = "SYNTHETIC QA"
TRACK_SECONDS = 90  # Leave time for full-resolution playback/overlay screenshots.
ARTIST = "A SYNTHETIC QA"
CATALOG_ID = "synthetic-catalog%00album, A & B"
CATALOG_TITLE = "SYNTHETIC QA Mock Download"
WRITE_CAPABILITIES = {"/api/acquire-album":"acquire", "/api/acquisitions/cancel":"cancel",
                      "/api/acquisitions/prioritize":"prioritize"}
ALBUM_ID = "synthetic%00double,album"
TRACK_IDS = ["SYNTHETIC QA/Disc 1/01, A & B.wav", "SYNTHETIC QA/Disc 1/02.wav",
             "SYNTHETIC QA/Disc 2/01.wav", "SYNTHETIC QA/Disc 2/02.wav"]
OBSERVER_SOURCE = r'''"""Read-only observer of the disposable Format test. No Kodi actions."""
import json
import os
from pathlib import Path
import time
import traceback
import xbmc
import xbmcaddon
import xbmcgui

root = Path(xbmcaddon.Addon("service.aperture.formatsmoke").getAddonInfo("path")).resolve()
config = json.loads((root / "config.json").read_text())
runtime = Path(config["runtime"])
if (not runtime.name.startswith("aperture-kodi-smoke.")
        or root != runtime / "system/addons/service.aperture.formatsmoke"
        or Path(os.environ["KODI_HOME"]).resolve() != runtime / "system"
        or Path(os.environ["KODI_DATA"]).resolve() != runtime / "data"
        or json.loads((runtime / ".aperture-format-fixture.json").read_text()) != config):
    raise RuntimeError("Not a disposable Format fixture")
out = Path(config["out"])
server = json.loads((out / "format-ready.json").read_text())["url"]

def rpc(method, **params):
    result = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc":"2.0", "id":1, "method":method, "params":params})))
    if "error" in result:
        raise RuntimeError("Read-only RPC failed: " + method)
    return result["result"]

monitor = xbmc.Monitor()
sequence = 0
try:
    with (out / "format-states.jsonl").open("a", buffering=1) as history:
        while not monitor.abortRequested():
            sequence += 1
            queue = rpc("Playlist.GetItems", playlistid=0, properties=["title", "album", "disc", "track", "file"]).get("items", [])
            if any(not item.get("file", "").startswith(server + "/api/audio?") for item in queue):
                raise RuntimeError("Unexpected nonfixture queue")
            players = rpc("Player.GetActivePlayers")
            audio = next((p for p in players if p.get("type") == "audio"), None)
            player = None
            if audio:
                try:
                    item = rpc("Player.GetItem", playerid=audio["playerid"], properties=["title", "album", "disc", "track", "file"])["item"]
                    properties = rpc("Player.GetProperties", playerid=audio["playerid"], properties=["speed", "position", "playlistid", "shuffled", "time"])
                except RuntimeError:
                    # Player can disappear between read-only calls during Stop.
                    item, properties = {}, None
                if item.get("file") and not item["file"].startswith(server + "/api/audio?"):
                    raise RuntimeError("Unexpected nonfixture playback")
                if properties is not None:
                    player = {"item":item, "properties":properties}
            state = {"sequence":sequence, "time":time.time(), "pid":os.getpid(), "queue":queue, "player":player,
                     "window":xbmcgui.getCurrentWindowId(),
                     "dialog":xbmcgui.getCurrentWindowDialogId(),
                     "nowplaying_visible":bool(xbmc.getCondVisibility("Control.IsVisible(7100)")),
                     "long_album_tracks_visible":bool(xbmc.getCondVisibility("Control.IsVisible(7122)")),
                     "long_album_current_page":xbmc.getInfoLabel("Container(7122).CurrentPage"),
                     "long_album_pages":xbmc.getInfoLabel("Container(7122).NumPages"),
                     "long_album_tracks_text":xbmcgui.Window(10000).getProperty("Aperture.FormatAlbumTracks"),
                     "album_tracks_visible":bool(xbmc.getCondVisibility("Control.IsVisible(7120)")),
                     "album_track_titles":[xbmc.getInfoLabel("Container(7120).ListItemAbsolute({}).Title".format(i)) for i in range(12)],
                     "nowplaying_button_visible":bool(xbmc.getCondVisibility("Control.IsVisible(65)")),
                     "player_has_performed_seek":bool(xbmc.getCondVisibility("Player.HasPerformedSeek(3)")),
                     "presentation_progress_visible":bool(xbmc.getCondVisibility("Control.IsVisible(7112)")),
                     "player_show_info":bool(xbmc.getCondVisibility("Player.ShowInfo")),
                     "native_topbar_visible":bool(xbmc.getCondVisibility("Window.IsVisible(1109)")),
                     "native_seekbar_visible":bool(xbmc.getCondVisibility("Window.IsVisible(seekbar)")),
                     "presentation_header_visible":bool(xbmc.getCondVisibility("Control.IsVisible(7110)")),
                     "presentation_footer_visible":bool(xbmc.getCondVisibility("Control.IsVisible(7111)")),
                     "paused_visible":bool(xbmc.getCondVisibility("Control.IsVisible(7103)")),
                     "turntable_captions":[xbmc.getInfoLabel("Control.GetLabel({})".format(i)) for i in (7104, 7102, 7105)],
                     "playing_title":xbmc.getInfoLabel("MusicPlayer.Title"),
                     "playing_cover":xbmc.getInfoLabel("MusicPlayer.Cover"),
                     "folder":xbmc.getInfoLabel("Container.FolderPath"),
                     "focused_title":xbmc.getInfoLabel("ListItem.Title"),
                     "shelf_position":xbmc.getInfoLabel("Container(64).ListItem.Property(Aperture.FormatPosition)"),
                     "focused_label":xbmc.getInfoLabel("ListItem.Label"),
                     "labels":[xbmc.getInfoLabel("Container.ListItemAbsolute({}).Label".format(i)) for i in range(12)],
                     "format_view":xbmc.getInfoLabel("Container.Property(Aperture.FormatView)"),
                     "format_notice":xbmc.getInfoLabel("Container.Property(Aperture.FormatNotice)"),
                     "shelf_focus_complete":bool(xbmc.getInfoLabel("Container.Property(Aperture.FormatEntry)")) and xbmc.getInfoLabel("Container.Property(Aperture.FormatEntry)") == xbmc.getInfoLabel("Window(10502).Property(Aperture.FormatFocusEntry)"),
                     "shelf_visible":bool(xbmc.getCondVisibility("Control.IsVisible(64)")),
                     "list_visible":bool(xbmc.getCondVisibility("Control.IsVisible(63)")),
                     "focus":xbmc.getInfoLabel("System.CurrentControlId"),
                     "art":xbmc.getInfoLabel("ListItem.Art(thumb)"),
                     "enabled":bool(xbmc.getCondVisibility("System.AddonIsEnabled(plugin.audio.aperture.format)"))}
            payload = json.dumps(state)
            history.write(payload + "\n")
            temporary = out / "format-state.tmp"
            temporary.write_text(payload)
            temporary.replace(out / "format-state.json")
            if monitor.waitForAbort(0.2):
                break
except Exception:
    (out / "format-observer-error.txt").write_text(traceback.format_exc())
    raise
'''


def atomic(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.replace(path)


def fixture_library():
    tracks = [{"id":identifier, "title":"SYNTHETIC QA Disc {} Track {}".format(index // 2 + 1, index % 2 + 1),
               "artist":"A SYNTHETIC QA", "albumArtist":"A SYNTHETIC QA", "album":"SYNTHETIC QA Double",
               "disc":index // 2 + 1, "track":index % 2 + 1, "duration":TRACK_SECONDS, "year":"2026"}
              for index, identifier in enumerate(TRACK_IDS)]
    return {"albums":[{"id":ALBUM_ID, "artist":"A SYNTHETIC QA", "title":"SYNTHETIC QA Double", "year":"2026",
                       "trackIds":[TRACK_IDS[2], TRACK_IDS[1], TRACK_IDS[3], TRACK_IDS[0]]}],
            "tracks":list(reversed(tracks))}


def fixture_catalogue():
    # Covers and tracks are synthetic too. No provider URLs exist in this source.
    return {"artist":{"id":"synthetic-artist", "name":ARTIST, "country":"", "disambiguation":""},
            "albums":[{"id":CATALOG_ID, "title":CATALOG_TITLE, "year":"2026", "secondaryTypes":[],
                       "owned":False, "localAlbumId":None, "downloadable":True, "cover":""}]}


def fixture_preview():
    return {"id":CATALOG_ID, "artist":ARTIST, "title":CATALOG_TITLE, "year":"2026",
            "releaseId":"synthetic-release", "releaseTitle":CATALOG_TITLE, "country":"", "cover":"",
            "tracks":[{"disc":1, "position":i + 1, "title":"SYNTHETIC QA Catalogue Track {}".format(i + 1),
                       "artist":ARTIST, "duration":TRACK_SECONDS} for i in range(2)]}


def fixture_health(**actions):
    capabilities = {"acquire":True, "cancel":True, "prioritize":True,
                    "editMetadata":False, "deleteMedia":False, "repair":False}
    capabilities.update(actions)
    return {"readOnly":True, "capabilities":capabilities,
            "downloads":{"enabled":True, "ready":capabilities["acquire"] is True,
                         "reason":None if capabilities["acquire"] is True else "downloader_unavailable"}}


def fixture_write_allowed(health, path):
    action = WRITE_CAPABILITIES.get(path)
    if action is None or not isinstance(health, dict):
        return False
    if "capabilities" in health:
        capabilities = health["capabilities"]
        return isinstance(capabilities, dict) and capabilities.get(action) is True
    # Only a legacy server with no capabilities contract uses this fallback.
    return health.get("readOnly") is False


def write_wav(path, frequency):
    rate = 8000
    # Quiet original sine tone; no downloaded or copyrighted source audio.
    samples = b"".join(struct.pack("<h", round(300 * math.sin(2 * math.pi * frequency * i / rate))) for i in range(rate * TRACK_SECONDS))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(samples)


COVERFLOW_COLORS = [(220, 45, 45), (45, 210, 65), (45, 70, 225),
                    (220, 190, 40), (190, 45, 210), (40, 200, 210)]


def cover_png(color=None):
    def chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data) & 0xffffffff)
    pixels = b"".join(b"\x00" + b"".join(bytes(color or (30 + x, 60 + y, 130)) for x in range(128)) for y in range(128))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!2I5B", 128, 128, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")


def validated_runtime(runtime):
    runtime = runtime.resolve()
    if not runtime.name.startswith("aperture-kodi-smoke.") or not runtime.is_dir():
        raise ValueError("Expected a fresh aperture-kodi-smoke.* runtime")
    for variable, suffix in (("HOME", "home"), ("KODI_HOME", "system"), ("KODI_DATA", "data")):
        if Path(os.environ.get(variable, "")).resolve() != runtime / suffix:
            raise ValueError("{} must target the disposable runtime".format(variable))
    return runtime


def prepare(runtime, out, root=ROOT):
    runtime = validated_runtime(runtime)
    out = out.resolve()
    if Path(os.environ.get("APERTURE_SMOKE_OUT", "")).resolve() != out:
        raise ValueError("Output must match APERTURE_SMOKE_OUT")
    system, data = runtime / "system", runtime / "data"
    manifest_path = system / "system/addon-manifest.xml"
    settings_path = data / "userdata/guisettings.xml"
    if not manifest_path.is_file() or not settings_path.is_file():
        raise ValueError("Prepare after the runner creates its system and guisettings.xml")
    marker = runtime / ".aperture-format-fixture.json"
    fixture = runtime / "format-fixture"
    observer = system / "addons" / OBSERVER
    addon = system / "addons" / ADDON
    settings = data / "userdata/addon_data" / ADDON / "settings.xml"
    pulse = runtime / "pulse"
    if any(path.exists() for path in (marker, fixture, observer, addon, settings, pulse)):
        raise ValueError("Refusing to replace an existing fixture or add-on")
    out.mkdir(parents=True, exist_ok=True)
    fixture.mkdir()
    library = fixture_library()
    atomic(fixture / "library.json", library)
    atomic(fixture / "health.json", fixture_health())
    atomic(fixture / "acquisitions.json", [])
    files = {}
    for index, identifier in enumerate(TRACK_IDS):
        name = "track-{}.wav".format(index + 1)
        write_wav(fixture / name, 220 + index * 55)
        files[identifier] = name
    (fixture / "cover.png").write_bytes(cover_png())
    config = {"label":LABEL, "token":uuid.uuid4().hex, "runtime":str(runtime), "out":str(out), "files":files,
              "artist":ARTIST, "catalog_id":CATALOG_ID, "catalog_title":CATALOG_TITLE, "protected_health":fixture_health(),
              "catalog_tracks":[track["title"] for track in fixture_preview()["tracks"]],
              "expected_ids":TRACK_IDS, "album_id":ALBUM_ID, "album_title":library["albums"][0]["title"], "expected_titles":["SYNTHETIC QA Disc {} Track {}".format(i // 2 + 1, i % 2 + 1) for i in range(4)]}
    atomic(marker, config)
    shutil.copytree(root / "format-kodi", addon, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    observer.mkdir()
    (observer / "service.py").write_text(OBSERVER_SOURCE)
    atomic(observer / "config.json", config)
    (observer / "addon.xml").write_text('''<addon id="service.aperture.formatsmoke" name="Format synthetic QA observer" version="1.0.0" provider-name="Aperture QA">
<requires><import addon="xbmc.python" version="3.0.1"/></requires>
<extension point="xbmc.service" library="service.py"/>
<extension point="xbmc.addon.metadata"><summary lang="en_GB">Read-only disposable test observer</summary><platform>all</platform><license>GPL-3.0-or-later</license></extension></addon>''')
    manifest = ET.parse(manifest_path)
    for identifier in (ADDON, OBSERVER):
        if not any(node.text == identifier for node in manifest.getroot().findall("addon")):
            ET.SubElement(manifest.getroot(), "addon").text = identifier
    manifest.write(manifest_path, encoding="utf-8", xml_declaration=True)
    keymap = data / "userdata/keymaps/format-ci.xml"
    keymap.parent.mkdir(exist_ok=True)
    keymap.write_text('''<keymap><global><keyboard>
<j>ActivateWindow(10502,plugin://plugin.audio.aperture.format/?action=albums,return)</j>
<k>ActivateWindow(10502,plugin://plugin.audio.aperture.format/,return)</k>
<l>RunPlugin(plugin://plugin.audio.aperture.format/?action=refresh_library)</l>
</keyboard></global></keymap>''')
    pulse.mkdir(mode=0o700)
    (pulse / "cookie").write_bytes(os.urandom(256))
    (pulse / "cookie").chmod(0o600)
    (pulse / "client.conf").write_text("autospawn = no\nenable-shm = no\n")
    (pulse / "default.pa").write_text(
        "load-module module-native-protocol-unix socket={0}/native auth-cookie={0}/cookie auth-anonymous=no\n"
        "load-module module-null-sink sink_name=aperture_format_qa rate=44100 channels=2 sink_properties=device.description=Aperture_SYNTHETIC_QA_discard_only\n"
        "set-default-sink aperture_format_qa\n".format(pulse))
    settings_tree = ET.parse(settings_path)
    audio = settings_tree.find("./setting[@id='audiooutput.audiodevice']")
    if audio is None:
        audio = ET.SubElement(settings_tree.getroot(), "setting", id="audiooutput.audiodevice")
    audio.text = "PULSE:aperture_format_qa"
    settings_tree.write(settings_path, encoding="utf-8", xml_declaration=True)
    atomic(out / "format-expected.json", config)
    atomic(out / "format-result.json", {"status":"not_run", "label":LABEL})
    return config


def byte_range(value, length):
    if not value:
        return 0, length - 1, False
    if not value.startswith("bytes=") or "," in value:
        raise ValueError("Unsupported range")
    first, last = value[6:].split("-", 1)
    if first:
        start = int(first)
        end = min(int(last), length - 1) if last else length - 1
    else:
        count = int(last)
        if count <= 0:
            raise ValueError("Invalid suffix range")
        start, end = max(0, length - count), length - 1
    if start < 0 or start > end or start >= length:
        raise ValueError("Unsatisfiable range")
    return start, end, True


def fixture_handler(config, fixture, out):
    """Purely local mock contract. Only serve() may bind it to loopback."""
    lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_HEAD(self):
            self.respond(head=True)

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def do_PUT(self):
            self.respond()

        def do_DELETE(self):
            self.respond()

        def respond(self, head=False):
            url = urlsplit(self.path)
            query = parse_qs(url.query, keep_blank_values=True)
            identifier = query.get("id", [""])[0]
            # All requests, including prohibited methods and rejected writes,
            # enter the same log. An unexpected mutation must never be invisible.
            with lock:
                payload, mime, status = self.payload(url.path, query, identifier)
            # Delay only synthetic covers, outside the mutation lock: emulate
            # independent slow HTTP artwork without serializing library reads.
            delay_file = fixture / "cover-delay.json"
            if url.path == "/api/cover" and identifier.startswith("coverflow-track-") and delay_file.exists():
                time.sleep(min(2.0, max(0.0, float(json.loads(delay_file.read_text())))))
            total = len(payload)
            start, end, ranged = 0, total - 1, False
            if status == 200 and url.path == "/api/audio":
                try:
                    start, end, ranged = byte_range(self.headers.get("Range"), total)
                except (ValueError, TypeError):
                    status, payload = 416, b""
                if ranged:
                    status, payload = 206, payload[start:end + 1]
            with lock, (out / "format-requests.jsonl").open("a") as log:
                log.write(json.dumps({"time":time.time(), "path":url.path, "query":query,
                                      "id":query.get("id"), "status":status,
                                      "method":self.command,
                                      "health":getattr(self, "fixture_health", None)
                                      if url.path == "/api/health" or self.command not in ("GET", "HEAD") else None}) + "\n")
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.send_header("Accept-Ranges", "bytes")
            if status == 206:
                self.send_header("Content-Range", "bytes {}-{}/{}".format(start, end, total))
            elif status == 416:
                self.send_header("Content-Range", "bytes */{}".format(total))
            self.end_headers()
            if not head:
                try:
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def payload(self, path, query, identifier):
            def data(value, status=200):
                return json.dumps(value).encode(), "application/json", status
            if (fixture / "offline").exists():
                return data({"error":"SYNTHETIC QA offline"}, 503)
            health = json.loads((fixture / "health.json").read_text())
            self.fixture_health = health
            writes = WRITE_CAPABILITIES
            if self.command not in ("GET", "HEAD"):
                if self.command != "POST" or path not in writes:
                    return data({"error":"Not a supported mock acquisition action"}, 405)
                if not fixture_write_allowed(health, path):
                    return data({"error":"This Format action is not permitted."}, 403)
                if identifier != CATALOG_ID or set(query) != {"id"} or len(query["id"]) != 1:
                    return data({"error":"Not a synthetic catalogue album"}, 404)
                items = json.loads((fixture / "acquisitions.json").read_text())
                item = next((row for row in items if row["id"] == identifier), None)
                if path == "/api/acquire-album":
                    if item is None or item["status"] == "cancelled":
                        item = {"id":CATALOG_ID, "artist":ARTIST, "title":CATALOG_TITLE,
                                "origin":"manual", "status":"queued", "message":"SYNTHETIC QA mock queue; no provider or file transfer.",
                                "progress":0, "queuePosition":1, "trackNumber":0, "totalTracks":2}
                        items = [item]
                elif item is None or item["status"] != "queued":
                    return data({"error":"Queued download not found"}, 404)
                elif path.endswith("/cancel"):
                    item.update(status="cancelled", queuePosition=0, message="SYNTHETIC QA mock cancelled.")
                else:
                    item.update(queuePosition=1, priority=100, message="SYNTHETIC QA moved to front.")
                atomic(fixture / "acquisitions.json", items)
                return data(item, 202)
            if path in writes:
                return data({"error":"POST required"}, 405)
            if path == "/api/health":
                if (fixture / "health-offline").exists():
                    return data({"error":"SYNTHETIC QA health unavailable"}, 503)
                return data(dict(health, initialLibraryScanComplete=True, albums=1, tracks=4)
                            if isinstance(health, dict) else health)
            if path == "/api/catalog/search":
                if query.get("q", [""])[0].strip().casefold() != ARTIST.casefold():
                    return data({"artist":None, "albums":[]})
                return data(fixture_catalogue())
            if path == "/api/catalog/album":
                return data(fixture_preview()) if identifier == CATALOG_ID else data({"error":"Not a synthetic album"}, 404)
            if path == "/api/acquisitions":
                return data(json.loads((fixture / "acquisitions.json").read_text()))
            if path == "/api/shadow-albums":
                return data([])
            if path == "/api/library":
                payload, mime = (fixture / "library.json").read_bytes(), "application/json"
            elif path in ("/api/audio", "/api/cover"):
                if path == "/api/cover" and identifier in ["coverflow-track-" + str(i) for i in range(1, 7)]:
                    return cover_png(COVERFLOW_COLORS[int(identifier.rsplit("-", 1)[1]) - 1]), "image/png", 200
                if identifier not in config["files"]:
                    return b"Not a fixture track", "text/plain", 404
                elif path == "/api/cover":
                    if identifier == TRACK_IDS[-1]:
                        return b"Synthetic missing artwork", "text/plain", 404
                    payload, mime = (fixture / "cover.png").read_bytes(), "image/png"
                else:
                    payload, mime = (fixture / config["files"][identifier]).read_bytes(), "audio/wav"
            else:
                return b"Not found", "text/plain", 404
            return payload, mime, 200
    return Handler


def serve(runtime):
    runtime = validated_runtime(runtime)
    config = json.loads((runtime / ".aperture-format-fixture.json").read_text())
    out, fixture = Path(config["out"]), runtime / "format-fixture"
    if config.get("label") != LABEL or config.get("runtime") != str(runtime):
        raise ValueError("Invalid fixture marker")

    server = ThreadingHTTPServer(("127.0.0.1", 0), fixture_handler(config, fixture, out))
    server.daemon_threads = True
    url = "http://127.0.0.1:{}".format(server.server_port)
    settings = runtime / "data/userdata/addon_data" / ADDON / "settings.xml"
    settings.parent.mkdir(parents=True)
    tree = ET.Element("settings", version="2")
    ET.SubElement(tree, "setting", id="server_url").text = url
    ET.ElementTree(tree).write(settings, encoding="utf-8", xml_declaration=True)
    atomic(out / "format-ready.json", {"url":url, "pid":os.getpid(), "label":LABEL})
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "serve"))
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        if args.out is None:
            parser.error("prepare requires --out")
        prepare(args.runtime, args.out)
    else:
        serve(args.runtime)

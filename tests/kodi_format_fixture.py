#!/usr/bin/env python3
"""Disposable CI-only Format source. Never point this at a user's Kodi profile.

prepare creates original WAV/PNG fixtures and an observation-only Kodi service.
serve binds 127.0.0.1 on an OS-selected port, writes settings, then ready.json.
Only GET/HEAD endpoints exist; an offline marker simulates an unavailable server.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import shutil
import struct
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
                     "folder":xbmc.getInfoLabel("Container.FolderPath"),
                     "focused_title":xbmc.getInfoLabel("ListItem.Title"),
                     "labels":[xbmc.getInfoLabel("Container.ListItemAbsolute({}).Label".format(i)) for i in range(6)],
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
               "disc":index // 2 + 1, "track":index % 2 + 1, "duration":30, "year":"2026"}
              for index, identifier in enumerate(TRACK_IDS)]
    return {"albums":[{"id":ALBUM_ID, "artist":"A SYNTHETIC QA", "title":"SYNTHETIC QA Double", "year":"2026",
                       "trackIds":[TRACK_IDS[2], TRACK_IDS[1], TRACK_IDS[3], TRACK_IDS[0]]}],
            "tracks":list(reversed(tracks))}


def write_wav(path, frequency):
    rate = 8000
    # Quiet original sine tone; no downloaded or copyrighted source audio.
    samples = b"".join(struct.pack("<h", round(300 * math.sin(2 * math.pi * frequency * i / rate))) for i in range(rate * 30))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(samples)


def cover_png():
    def chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data) & 0xffffffff)
    pixels = b"".join(b"\x00" + b"".join(bytes((30 + x, 60 + y, 130)) for x in range(128)) for y in range(128))
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
    files = {}
    for index, identifier in enumerate(TRACK_IDS):
        name = "track-{}.wav".format(index + 1)
        write_wav(fixture / name, 220 + index * 55)
        files[identifier] = name
    (fixture / "cover.png").write_bytes(cover_png())
    config = {"label":LABEL, "token":uuid.uuid4().hex, "runtime":str(runtime), "out":str(out), "files":files,
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
<l>Container.Refresh</l>
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


def serve(runtime):
    runtime = validated_runtime(runtime)
    config = json.loads((runtime / ".aperture-format-fixture.json").read_text())
    out, fixture = Path(config["out"]), runtime / "format-fixture"
    if config.get("label") != LABEL or config.get("runtime") != str(runtime):
        raise ValueError("Invalid fixture marker")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_HEAD(self):
            self.respond(head=True)

        def do_GET(self):
            self.respond()

        def respond(self, head=False):
            url = urlsplit(self.path)
            status = 200
            if (fixture / "offline").exists():
                payload, mime, status = b'{"error":"SYNTHETIC QA offline"}', "application/json", 503
            elif url.path == "/api/library":
                payload, mime = (fixture / "library.json").read_bytes(), "application/json"
            elif url.path in ("/api/audio", "/api/cover"):
                identifier = parse_qs(url.query).get("id", [""])[0]
                if identifier not in config["files"]:
                    payload, mime, status = b"Not a fixture track", "text/plain", 404
                elif url.path == "/api/cover":
                    payload, mime = (fixture / "cover.png").read_bytes(), "image/png"
                else:
                    payload, mime = (fixture / config["files"][identifier]).read_bytes(), "audio/wav"
            else:
                payload, mime, status = b"Not found", "text/plain", 404
            total = len(payload)
            start, end, ranged = 0, total - 1, False
            if status == 200 and url.path == "/api/audio":
                try:
                    start, end, ranged = byte_range(self.headers.get("Range"), total)
                except (ValueError, TypeError):
                    status, payload = 416, b""
                if ranged:
                    status, payload = 206, payload[start:end + 1]
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
            with (out / "format-requests.jsonl").open("a") as log:
                log.write(json.dumps({"time":time.time(), "path":url.path, "id":parse_qs(url.query).get("id"), "status":status, "method":self.command}) + "\n")
            if not head:
                try:
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
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

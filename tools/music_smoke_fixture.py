#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate/prepare explicitly synthetic music for the disposable Kodi GUI test.

Normal CI copies checked-in FLACs; only `generate` needs ffmpeg and Pillow.
This utility never touches an existing/user Kodi profile.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import uuid
import wave
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/music"
LABEL = "SYNTHETIC QA"
SERVICE_ID = "service.apeture.musicsmoke"
ALBUMS = [
    ("Amber SYNTHETIC QA", "SYNTHETIC QA — Dawn", 2001, [(1, 1)]),
    ("The Beacon SYNTHETIC QA", "SYNTHETIC QA — Earlier", 1999, [(1, 1)]),
    ("The Beacon SYNTHETIC QA", "SYNTHETIC QA — Later", 2004, [(1, 1)]),
    ("Cedar SYNTHETIC QA", "SYNTHETIC QA — Double", 2003, [(1, 1), (1, 2), (2, 1), (2, 2)]),
    ("Delta SYNTHETIC QA", "SYNTHETIC QA — Night", 2000, [(1, 1)]),
    ("Echo SYNTHETIC QA", "SYNTHETIC QA — Signal", 2005, [(1, 1)]),
    ("Zinc SYNTHETIC QA", "SYNTHETIC QA — Last", 2006, [(1, 1)]),
]


def flac_tags(path: Path) -> dict[str, str]:
    """Read actual Vorbis comments without mutagen/ffmpeg in normal CI."""
    with path.open("rb") as handle:
        if handle.read(4) != b"fLaC":
            raise ValueError("Fixture is not a FLAC file")
        while True:
            header = handle.read(4)
            if len(header) != 4:
                raise ValueError("Truncated FLAC metadata")
            kind, length = header[0] & 127, int.from_bytes(header[1:], "big")
            block = handle.read(length)
            if len(block) != length:
                raise ValueError("Truncated FLAC metadata block")
            if kind == 4:
                vendor_length = struct.unpack_from("<I", block)[0]
                at = 4 + vendor_length
                count = struct.unpack_from("<I", block, at)[0]
                at += 4
                tags = {}
                for _ in range(count):
                    size = struct.unpack_from("<I", block, at)[0]
                    at += 4
                    key, separator, value = block[at:at + size].decode("utf-8").partition("=")
                    at += size
                    if separator:
                        tags[key.upper()] = value
                return tags
            if header[0] & 128:
                raise ValueError("FLAC has no Vorbis comments")


def verify(source: Path = FIXTURES) -> dict:
    manifest = json.loads((source / "expected.json").read_text(encoding="utf-8"))
    if manifest.get("label") != LABEL or len(manifest.get("albums", [])) != 7:
        raise ValueError("Not the explicit seven-album synthetic fixture")
    for album in manifest["albums"]:
        if LABEL not in album["title"] or LABEL not in album["artist"]:
            raise ValueError("Fixture metadata must identify itself as synthetic")
        for track in album["tracks"]:
            relative = Path(track["file"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Unsafe fixture path")
            path = source / relative
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != track["sha256"]:
                raise ValueError("Fixture audio hash mismatch")
            tags = flac_tags(path)
            expected = {"ALBUM": album["title"], "ARTIST": album["artist"],
                        "ALBUMARTIST": album["artist"], "DATE": str(album["year"]),
                        "DISCNUMBER": str(track["disc"]), "TRACKNUMBER": str(track["track"]),
                        "TITLE": track["title"]}
            if any(tags.get(key) != value for key, value in expected.items()):
                raise ValueError("Actual FLAC metadata differs from expected shelf fixture")
    return manifest


def generate(destination: Path = FIXTURES):
    """Regenerate original tones and artwork; never download source material."""
    from PIL import Image, ImageDraw, ImageFont
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {"label": LABEL, "description": "Original quiet test tones, not a user catalogue.",
                "duration_seconds": 20, "albums": []}
    font = ImageFont.load_default(size=26)
    small = ImageFont.load_default(size=17)
    for index, (artist, title, year, tracks) in enumerate(ALBUMS):
        directory = destination / ("album-{:02}".format(index + 1))
        directory.mkdir(exist_ok=True)
        color = ((38 + index * 23) % 160, 70 + index * 13, 102 + index * 11)
        cover = Image.new("RGB", (400, 400), color)
        draw = ImageDraw.Draw(cover)
        for x in range(25, 375, 35):
            draw.line((x, 120, 400 - x, 350), fill=(140, 195, 194), width=3)
        draw.rectangle((0, 0, 400, 112), fill=(14, 26, 30))
        draw.text((20, 20), LABEL, font=font, fill="white")
        draw.text((20, 65), "ORIGINAL TEST TONE", font=small, fill=(170, 216, 216))
        draw.rectangle((0, 355, 400, 400), fill=(14, 26, 30))
        draw.text((20, 367), "NOT A REAL ALBUM  /  {} OF 7".format(index + 1), font=small, fill="white")
        cover.save(directory / "folder.jpg", quality=92)
        entry = {"artist": artist, "title": title, "year": year, "tracks": []}
        for ordinal, (disc, track) in enumerate(tracks):
            # Reversed filenames intentionally disagree with musical order.
            filename = "{}-disc{}-track{}.flac".format(chr(ord('z') - ordinal), disc, track)
            output = directory / filename
            track_title = "SYNTHETIC QA — Disc {} Track {}".format(disc, track)
            with tempfile.NamedTemporaryFile(suffix=".wav") as raw:
                sample_rate = 11025
                frequency = 245 + index * 35 + ordinal * 7
                # Very quiet, authored mathematical waveform; no sampled audio.
                samples = bytearray()
                for i in range(sample_rate * 20):
                    ramp = min(1.0, i / 1102.5, (sample_rate * 20 - i) / 1102.5)
                    value = round(600 * ramp * math.sin(2 * math.pi * frequency * i / sample_rate))
                    samples.extend(struct.pack('<h', value))
                with wave.open(raw.name, "wb") as wav:
                    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(sample_rate)
                    wav.writeframes(bytes(samples))
                command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", raw.name,
                           "-map_metadata", "-1", "-codec:a", "flac", "-compression_level", "12"]
                for key, value in {"TITLE": track_title, "ARTIST": artist, "ALBUMARTIST": artist,
                                   "ALBUM": title, "DATE": year, "DISCNUMBER": disc,
                                   "TRACKNUMBER": track, "COMMENT": "Original SYNTHETIC QA test tone; not user media."}.items():
                    command += ["-metadata", "{}={}".format(key, value)]
                subprocess.run(command + [str(output)], check=True)
            entry["tracks"].append({"file": output.relative_to(destination).as_posix(),
                                    "title": track_title, "disc": disc, "track": track,
                                    "sha256": hashlib.sha256(output.read_bytes()).hexdigest()})
        manifest["albums"].append(entry)
    (destination / "expected.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    verify(destination)


def prepare(runtime: Path, out: Path, root: Path = ROOT) -> dict:
    """Install test subjects/observer only inside main runner's new mktemp tree.

    Call after its guisettings.xml is created and before launching Kodi. The
    prefix and exact directory relationships prevent targeting a real profile.
    """
    runtime, out, root = runtime.resolve(), out.resolve(), root.resolve()
    if not runtime.name.startswith("apeture-kodi-smoke.") or not runtime.is_dir():
        raise ValueError("Expected the smoke runner's disposable mktemp directory")
    system, data = runtime / "system", runtime / "data"
    if not (system / "system/addon-manifest.xml").is_file() or not (data / "userdata/guisettings.xml").is_file():
        raise ValueError("Expected prepared disposable Kodi system/profile")
    if os.environ.get("KODI_HOME") and Path(os.environ["KODI_HOME"]).resolve() != system:
        raise ValueError("KODI_HOME is not the disposable smoke system")
    if os.environ.get("KODI_DATA") and Path(os.environ["KODI_DATA"]).resolve() != data:
        raise ValueError("KODI_DATA is not the disposable smoke profile")
    home = runtime / "home"
    if Path(os.environ.get("HOME", "")).resolve() != home or not home.is_dir():
        raise ValueError("HOME is not the disposable smoke home")
    alsa_config = home / ".asoundrc"
    if alsa_config.exists() or alsa_config.is_symlink():
        raise ValueError("Refusing to replace an existing ALSA configuration")
    marker = runtime / ".apeture-music-smoke.json"
    fixture = runtime / "synthetic-music"
    if marker.exists() or fixture.exists():
        raise ValueError("Refusing to replace an existing fixture run")
    expected = verify(root / "tests/fixtures/music")
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root / "tests/fixtures/music", fixture)
    helper = system / "addons/script.apeture.music"
    if helper.exists():
        raise ValueError("Music helper already installed in fixture system")
    shutil.copytree(root / "addons/script.apeture.music", helper,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    observer = system / ("addons/" + SERVICE_ID)
    observer.mkdir()
    shutil.copy2(root / "tools/music_smoke_observer.py", observer / "service.py")
    (observer / "addon.xml").write_text('''<addon id="service.apeture.musicsmoke" name="Synthetic music QA observer" version="1.0.0" provider-name="Apeture QA">
  <requires><import addon="xbmc.python" version="3.0.1"/></requires>
  <extension point="xbmc.service" library="service.py"/>
  <extension point="xbmc.addon.metadata"><summary lang="en_GB">Disposable synthetic music test only</summary><platform>all</platform><license>GPL-3.0-or-later</license></extension>
</addon>
''', encoding="utf-8")
    # Kodi 21 explicitly enumerates the device named default while filtering a
    # raw device named null. This override is confined to the disposable HOME;
    # it discards output and does not start an audio server or touch /etc/asound.conf.
    alsa_config.write_text('''# Disposable Apeture SYNTHETIC QA ONLY; no audible output.
pcm.!default {
    type null
    hint {
        show on
        description "Apeture SYNTHETIC QA discard-only audio"
        ioid "Output"
    }
}
''', encoding="utf-8")
    (out / "music-audio-sink.txt").write_text(
        "ALSA:default from disposable HOME/.asoundrc; type null; discard-only.\n"
        "Acceptance is native decoder/player-clock progression and queue state, not audible output.\n", encoding="utf-8")
    config = {"label": LABEL, "token": uuid.uuid4().hex, "runtime": str(runtime),
              "system": str(system), "data": str(data), "fixture": str(fixture), "out": str(out),
              "expected": expected}
    marker.write_text(json.dumps(config), encoding="utf-8")
    (observer / "config.json").write_text(json.dumps(config), encoding="utf-8")
    tree = ET.parse(system / "system/addon-manifest.xml")
    for identifier in ("script.apeture.music", SERVICE_ID):
        if not any(item.text == identifier for item in tree.getroot().findall("addon")):
            ET.SubElement(tree.getroot(), "addon").text = identifier
    tree.write(system / "system/addon-manifest.xml", encoding="utf-8", xml_declaration=True)
    settings = ET.parse(data / "userdata/guisettings.xml")
    for identifier, value in (("musiclibrary.downloadinfo", "false"),
                              ("audiooutput.audiodevice", "ALSA:default")):
        setting = settings.find("./setting[@id='{}']".format(identifier))
        if setting is None:
            setting = ET.SubElement(settings.getroot(), "setting", id=identifier)
        setting.text = value
    settings.write(data / "userdata/guisettings.xml", encoding="utf-8", xml_declaration=True)
    (out / "music-expected.json").write_text(json.dumps(expected, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "music-result.json").write_text(json.dumps({"status": "not_run", "label": LABEL}) + "\n", encoding="utf-8")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("generate")
    commands.add_parser("verify")
    prep = commands.add_parser("prepare")
    prep.add_argument("--runtime", type=Path, required=True)
    prep.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "generate": generate()
    elif args.command == "verify": verify()
    else: prepare(args.runtime, args.out)
    print("Synthetic music fixture {} succeeded; this is not a Kodi runtime pass.".format(args.command))


if __name__ == "__main__": main()

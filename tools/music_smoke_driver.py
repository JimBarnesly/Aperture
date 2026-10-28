# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual Kodi keyboard assertions for the separate synthetic music extension.

Import run() from the main smoke runner's Python driver after its baseline GUI
checks. All success predicates use fresh in-process Kodi snapshots, never mocks.
"""
import json
import os
from pathlib import Path
import time
import uuid

HOME, MUSIC = 10000, 10502


def run(out, focus, press, wait_for, screenshot, state):
    """Use main runner's actual keyboard/capture helpers; return detailed checks.

    `wait_for`, `focus`, `press`, `screenshot`, `state` are the existing native
    runner functions. This function raises on any failure so baseline CI fails.
    """
    out = Path(out)
    expected = json.loads((out / "music-expected.json").read_text())
    checks = []
    latest = {}
    expected_pid = int(os.environ["APETURE_KODI_PID"])

    def read():
        nonlocal latest
        error = out / "music-error.json"
        if error.exists():
            raise AssertionError("Music fixture observer failed: " + error.read_text())
        try:
            latest = json.loads((out / "music-state.json").read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return latest

    def wait(description, predicate, after=0, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            current = read()
            if (current.get("pid") == expected_pid and current.get("sequence", 0) > after and time.time() - current.get("time", 0) < 3
                    and predicate(current)):
                return current
            time.sleep(0.05)
        raise AssertionError("Timed out: {}; last actual music state={}".format(description, latest))

    def key(name, description, predicate):
        before = read().get("sequence", 0)
        press(name)
        return wait(description, predicate, after=before)

    def command(action):
        identifier = uuid.uuid4().hex
        temporary = out / "music-command.tmp"
        temporary.write_text(json.dumps({"id": identifier, "action": action}))
        temporary.replace(out / "music-command.json")
        return wait("fixture command " + action,
                    lambda s: (s.get("last_command") or {}).get("id") == identifier)

    def home():
        return wait_for("Home before music check", lambda s: s.get("window") == HOME)

    def open_shelf(populated):
        home(); focus(9103)
        before = read().get("sequence", 0)
        press("Return")
        if populated:
            return wait("actual populated album shelf", lambda s: s.get("shelf_open") == "true"
                        and s["shelf"]["ready"] == "true" and s.get("focus") == 100, after=before)
        return wait("actual empty album shelf", lambda s: s.get("shelf_open") == "true"
                    and s["shelf"]["status"] == "Your shelf is waiting."
                    and s["shelf"]["ready"] == "" and s.get("focus") == 200, after=before)

    def close_shelf():
        key("Escape", "Back closes shelf", lambda s: s.get("window") == HOME and not s.get("shelf_open"))
        home()

    def record(name, capture=False):
        if capture:
            screenshot(name)
        checks.append({"check": name, "state": read()})

    def at(index):
        return lambda s: (s.get("focus") == 100 and s["shelf"]["position"] == "{} / 7".format(index + 1)
                          and s["shelf"]["title"] == expected["albums"][index]["title"]
                          and s["shelf"]["artist"] == expected["albums"][index]["artist"]
                          and s["shelf"]["year"] == str(expected["albums"][index]["year"]))

    try:
        initial = wait("music observer in empty fixture", lambda s: s.get("music_enabled") and s.get("window") == HOME)
        if initial["albums"] or initial["queue"] or initial["player"]:
            raise AssertionError("Music test must begin with a genuine empty disposable library and queue")
        open_shelf(False)
        record("music-01-empty", capture=True)
        # Empty initial focus is Kodi Music: exercise that action, not just Back.
        key("Return", "empty shelf opens native Music", lambda s: s.get("window") == MUSIC and not s.get("shelf_open"))
        record("music-02-native-music", capture=True)
        key("Escape", "native Music returns Home", lambda s: s.get("window") == HOME)
        open_shelf(False)
        close_shelf()
        record("music-empty-repeated-open-back")

        command("scan")
        loaded = wait("seven actual tagged albums scanned", lambda s: len(s.get("albums", [])) == 7 and len(s.get("songs", [])) == 10 and not s.get("scanning"), timeout=90)
        actual = {a["title"]: a for a in loaded["albums"]}
        for album in expected["albums"]:
            item = actual.get(album["title"])
            if not item or item.get("artist") != [album["artist"]] or item.get("year") != album["year"]:
                raise AssertionError("Kodi did not read the actual FLAC album tags as expected")
        random_positions = []
        for attempt in range(3):
            opened = open_shelf(True)
            index_text = opened["shelf"]["position"].split(" / ")[0]
            initial_index = int(index_text) - 1
            if not 0 <= initial_index < 7 or not at(initial_index)(opened):
                raise AssertionError("Random entrance did not select an in-range ordered album")
            random_positions.append(initial_index + 1)
            record("music-random-entry-valid-position-{}".format(attempt + 1))
            if attempt < 2:
                close_shelf()
        # Repeated positions are valid random outcomes; never gate on 'must differ'.
        # Move exactly to the first record, then prove clamping and all order slots.
        for index in range(initial_index - 1, -1, -1):
            key("Left", "browse to album {}".format(index + 1), at(index))
        key("Left", "first album clamps rather than wraps", at(0))
        record("music-03-first-album", capture=True)
        for index in range(1, 7):
            key("Right", "ordered album {}".format(index + 1), at(index))
            record("music-album-order-{}".format(index + 1), capture=(index == 3))
        key("Right", "last album clamps rather than wraps", at(6))
        if read()["player"] or read()["queue"]:
            raise AssertionError("Browsing changed playback before an explicit Play action")
        for index in range(5, 2, -1):
            key("Left", "return to two-disc album", at(index))
        album_id = actual[expected["albums"][3]["title"]]["albumid"]
        play_sequence = read().get("sequence", 0)
        press("Return")
        playing = wait("actual multi-disc album playback", lambda s:
            s.get("player") is not None and s["player"]["item"].get("albumid") == album_id
            and s["player"]["properties"].get("speed") == 1 and len(s.get("queue", [])) == 4,
            after=play_sequence, timeout=20)
        wanted = [(1, 1), (1, 2), (2, 1), (2, 2)]
        if [(i.get("disc"), i.get("track")) for i in playing["queue"]] != wanted:
            raise AssertionError("Actual Kodi queue is not in complete disc/track order")
        native_songs = sorted((song for song in loaded["songs"] if song.get("albumid") == album_id),
                              key=lambda song: (song.get("disc"), song.get("track")))
        # Playlist.GetItems serializes the queued raw MusicInfoTag; its internal
        # albumid can remain -1 even though song DbIds are correct. Player.GetItem
        # rehydrates from the library, and its exact albumid assertion stays above.
        if (len(native_songs) != 4
                or [item.get("id") for item in playing["queue"]] != [song["songid"] for song in native_songs]):
            raise AssertionError("Native playlist song IDs do not match the complete scanned album")
        if playing["player"]["properties"].get("shuffled") is not False:
            raise AssertionError("Ordered album playback left shuffle enabled")
        if (playing["player"]["item"].get("disc"), playing["player"]["item"].get("track")) != (1, 1):
            raise AssertionError("Album did not start at disc 1 track 1")
        def milliseconds(player):
            value = player["properties"].get("time", {})
            return (value.get("hours", 0) * 3600000 + value.get("minutes", 0) * 60000
                    + value.get("seconds", 0) * 1000 + value.get("milliseconds", 0))
        first_time = milliseconds(playing["player"])
        first_song = playing["player"]["item"].get("id")
        progressed = wait("actual audio-player clock advances on first fixture track", lambda s:
            s.get("player") is not None and s["player"]["item"].get("id") == first_song
            and s["player"]["properties"].get("speed") == 1
            and milliseconds(s["player"]) >= first_time + 500,
            after=playing["sequence"], timeout=8)
        playback_progress_ms = milliseconds(progressed["player"]) - first_time
        record("music-04-playing-double-disc", capture=True)
        close_shelf()
        if not read().get("player"):
            raise AssertionError("Back unexpectedly stopped the album")
        reopened = open_shelf(True)
        if not at(3)(reopened):
            raise AssertionError("Reopening did not centre the actual currently playing album")
        record("music-05-current-album-focus", capture=True)
        close_shelf()
        command("stop")
        wait("test playback stopped", lambda s: s.get("player") is None)
        result = {"status": "passed", "label": "SYNTHETIC QA", "checks": checks,
                  "random_initial_positions": random_positions, "playback_progress_ms": playback_progress_ms,
                  "scope": "Actual Kodi 21 WindowXML, fixture library, ordered queue and advancing decoder/player clock against private ALSA null sink",
                  "audio_sink": "ALSA:default; disposable HOME/.asoundrc type null; discard-only",
                  "limitations": ["Not user media", "Null sink: no audible output, Pi audio or hardware audio-output assertion", "No controller/CEC assertion", "No ZIP-install or Pi acceptance", "Randomness distribution not a runtime statistical test"]}
        (out / "music-result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        return checks
    except Exception as exc:
        (out / "music-result.json").write_text(json.dumps({"status": "failed", "label": "SYNTHETIC QA",
            "reason": str(exc), "checks": checks, "last_state": latest}, indent=2, ensure_ascii=False) + "\n")
        raise

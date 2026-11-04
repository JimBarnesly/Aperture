"""Actual GUI/player Format assertions, called from ci_kodi_smoke.sh's driver.

run(globals()) consumes state/wait_for/press/screenshot/find_label/settle_focus hooks.
No network RPC is enabled; playback evidence comes from the read-only observer.
"""
import json
import os
from pathlib import Path
import time
import traceback
from urllib.parse import parse_qs, urlsplit


ADDON_ID = "plugin.audio.aperture.format"


def route_is(folder, action, **parameters):
    """Match the actual plugin route, never an action-name substring."""
    parsed = urlsplit(folder)
    expected = dict(action=[action], **{key: [str(value)] for key, value in parameters.items()})
    return (parsed.scheme == "plugin" and parsed.netloc == ADDON_ID
            and parsed.path in ("", "/") and not parsed.fragment
            and parse_qs(parsed.query, keep_blank_values=True) == expected)


def gui_position(actual):
    return tuple(actual.get(key) for key in
                 ("window", "dialog", "folder", "focus", "dialog_focus", "list_item", "control_label"))


def observation_is_fresh(actual, pid, after, now):
    return (actual.get("pid") == pid and actual.get("sequence", 0) > after
            and 0 <= now - actual.get("time", 0) < 3)


def settled_observation(settle_focus, music, wait_music, description, predicate, after=0):
    """Sample metadata after both GUI animation and the observer have advanced."""
    settle_focus()
    sequence = max(after, music().get("sequence", 0))
    return wait_music(description, predicate, after=sequence)


def run(hooks):
    state, wait_for, press = (hooks[key] for key in ("state", "wait_for", "press"))
    screenshot, find_label = hooks["screenshot"], hooks["find_label"]
    settle_focus = hooks["settle_focus"]
    out = Path(os.environ["APERTURE_SMOKE_OUT"])
    config = json.loads((out / "format-expected.json").read_text())
    runtime = Path(config["runtime"])
    if not runtime.name.startswith("aperture-kodi-smoke.") or Path(os.environ["KODI_DATA"]).resolve() != runtime / "data":
        raise AssertionError("Not a disposable Format test")
    pid = int(os.environ["APERTURE_KODI_PID"])
    checks, last = [], {}
    album_title = config["album_title"]

    def music():
        nonlocal last
        try:
            last = json.loads((out / "format-state.json").read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return last

    def wait_music(description, predicate, timeout=30, after=0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            os.kill(pid, 0)
            if (out / "format-observer-error.txt").exists():
                raise AssertionError((out / "format-observer-error.txt").read_text())
            actual = music()
            if observation_is_fresh(actual, pid, after, time.time()) and predicate(actual):
                return actual
            time.sleep(0.1)
        raise AssertionError("Timed out: {}; last actual Format state={}".format(description, last))

    def settled_music(description, predicate, after=0):
        return settled_observation(settle_focus, music, wait_music, description, predicate, after)

    def clock(actual):
        value = actual["player"]["properties"]["time"]
        return value["hours"] * 3600 + value["minutes"] * 60 + value["seconds"] + value["milliseconds"] / 1000

    def track_id(item):
        return parse_qs(urlsplit(item.get("file", "")).query).get("id", [""])[0]

    def find_title(title, action, max_steps=6, after=0, **parameters):
        # Kodi may render a track number or artist in ListItem.Label. The music
        # metadata title is the stable assertion, regardless of native skin view.
        actual = wait_music("Format folder before focusing " + title,
                            lambda s: route_is(s.get("folder", ""), action, **parameters), after=after)
        for step in range(max_steps + 1):
            # A changed title can be the first frame of a moving container.
            # Settle first, then take a newer metadata sample before deciding
            # whether another arrow is necessary. Never act on the prior frame.
            actual = settled_music("Stable Format focus toward " + title,
                                   lambda s: route_is(s.get("folder", ""), action, **parameters),
                                   after=actual["sequence"])
            if actual.get("focused_title") == title:
                return actual
            if step == max_steps:
                break
            previous = actual.get("focused_title")
            sequence = actual["sequence"]
            press("Down")
            actual = wait_music("Format focus changed toward " + title,
                                lambda s: route_is(s.get("folder", ""), action, **parameters)
                                and s.get("focused_title") != previous, after=sequence)
        raise AssertionError("Could not focus metadata title {!r}; actual={}".format(title, actual))

    def opened_albums(key="j"):
        settle_focus()
        sequence = music().get("sequence", 0)
        before = press(key)
        wait_for("Format album list", lambda s: s.get("window") == 10502 and s.get("dialog") == 9999
                 and route_is(s.get("folder", ""), "albums"), after=before)
        actual = find_title(album_title, "albums", after=sequence)
        wait_music("album cover URL", lambda s: route_is(s.get("folder", ""), "albums")
                   and s.get("focused_title") == album_title and "/api/cover?" in s.get("art", ""),
                   after=actual["sequence"])

    def return_home():
        for _ in range(7):
            current = settle_focus()
            if current.get("window") == 10000 and current.get("dialog") == 9999:
                return
            position = gui_position(current)[:3]
            # PreviousMenu intentionally leaves the Music window for Home.
            # Parent-directory navigation inside Format uses BackSpace below.
            before = press("Escape")
            wait_for("Back changes Format folder or window", lambda s: gui_position(s)[:3] != position, after=before)
        raise AssertionError("Format did not return Home")

    try:
        wait_music("Format enabled", lambda s: s.get("enabled"))
        opened_albums()
        screenshot("format-01-albums")
        sequence = music()["sequence"]
        before = press("Return")
        wait_for("Format album tracks", lambda s: s.get("window") == 10502 and s.get("dialog") == 9999
                 and route_is(s.get("folder", ""), "album", album_id=config["album_id"]), after=before)
        actual = find_title(config["expected_titles"][0], "album", after=sequence, album_id=config["album_id"])
        observed = []
        for index, expected in enumerate(config["expected_titles"]):
            if actual.get("focused_title") != expected:
                raise AssertionError("Displayed metadata track order differs from disc/track order: " + repr(actual))
            observed.append(actual["focused_title"])
            if index < len(config["expected_titles"]) - 1:
                sequence = actual["sequence"]
                press("Down")
                actual = wait_music("next ordered track " + config["expected_titles"][index + 1],
                                    lambda s: route_is(s.get("folder", ""), "album", album_id=config["album_id"])
                                    and s.get("focused_title") == config["expected_titles"][index + 1], after=sequence)
                actual = settled_music("Stable ordered track " + config["expected_titles"][index + 1],
                                       lambda s: route_is(s.get("folder", ""), "album", album_id=config["album_id"])
                                       and s.get("focused_title") == config["expected_titles"][index + 1],
                                       after=actual["sequence"])
        checks.append({"check": "displayed-track-order", "titles": observed})
        screenshot("format-02-track-order")
        sequence = music()["sequence"]
        # Kodi maps Escape to PreviousMenu (which leaves the Music window).
        # BackSpace is Back: return from album tracks to the parent album list.
        before = press("BackSpace")
        wait_for("Back to Format albums", lambda s: s.get("window") == 10502 and s.get("dialog") == 9999
                 and route_is(s.get("folder", ""), "albums"), after=before)
        find_title(album_title, "albums", after=sequence)
        before = press("c")
        wait_for("Album context menu", lambda s: s.get("dialog") == 10106, after=before)
        settle_focus()
        find_label("Play album", "Down", 12)
        sequence = music()["sequence"]
        before = press("Return")
        wait_for("Context menu dismissed", lambda s: s.get("dialog") == 9999, after=before)
        settle_focus()
        actual = wait_music("ordered album playback", lambda s: s.get("player") is not None
                            and s["player"]["properties"].get("speed") == 1
                            and track_id(s["player"]["item"]) == config["expected_ids"][0], after=sequence)
        if [track_id(item) for item in actual["queue"]] != config["expected_ids"]:
            raise AssertionError("Real Kodi queue is not in disc/track order")
        if actual["player"]["properties"].get("shuffled") is not False:
            raise AssertionError("Album playback was shuffled")
        initial_clock, sequence = clock(actual), actual["sequence"]
        later = wait_music("native playback clock advances", lambda s: s.get("player") is not None
                           and track_id(s["player"]["item"]) == config["expected_ids"][0]
                           and clock(s) >= initial_clock + 1.5, timeout=20, after=sequence)
        checks.append({"check":"album-playback", "queue":actual["queue"], "start_seconds":initial_clock, "later_seconds":clock(later)})
        screenshot("format-03-playback")
        sequence = music()["sequence"]
        press("period")
        actual = wait_music("Skip reaches second track", lambda s: s.get("player") is not None
                            and track_id(s["player"]["item"]) == config["expected_ids"][1], after=sequence)
        checks.append({"check":"skip-next", "player":actual["player"]})
        sequence = actual["sequence"]
        press("x")
        wait_music("Stop synthetic playback", lambda s: s.get("player") is None, after=sequence)
        return_home()
        # HTTP 503 simulates server outage. No system networking is changed.
        opened_albums()
        offline = runtime / "format-fixture/offline"
        offline.write_text("Synthetic CI outage\n")
        before = press("l")
        wait_for("Format outage error dialog", lambda s: s.get("dialog") == 12002, after=before)
        settle_focus()
        screenshot("format-04-offline-error")
        before = press("Return")
        wait_for("Error dismissed", lambda s: s.get("dialog") == 9999, after=before)
        settle_focus()
        # A fresh observer sequence alone does not prove refresh succeeded: it
        # could still describe the cached list. Change fixture content first.
        library_path = runtime / "format-fixture/library.json"
        library_data = json.loads(library_path.read_text())
        album_title = config["album_title"] + " RECOVERED"
        album = next(item for item in library_data["albums"] if item["id"] == config["album_id"])
        album["title"] = album_title
        temporary = library_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(library_data))
        temporary.replace(library_path)
        offline.unlink()
        recovery_started = time.time()
        sequence = music()["sequence"]
        before = press("l")
        wait_for("Format refresh recovered", lambda s: s.get("dialog") == 9999
                 and route_is(s.get("folder", ""), "albums"), after=before)
        settled_music("Refreshed album metadata proves outage recovery",
                   lambda s: route_is(s.get("folder", ""), "albums") and s.get("focused_title") == album_title,
                   after=sequence)
        screenshot("format-05-recovered")
        return_home()
        opened_albums()
        return_home()
        requests = [json.loads(line) for line in (out / "format-requests.jsonl").read_text().splitlines()]
        for endpoint in ("/api/library", "/api/cover", "/api/audio"):
            if not any(row["path"] == endpoint and row["status"] in (200, 206) for row in requests):
                raise AssertionError("Kodi never fetched fixture endpoint " + endpoint)
        if not any(row["path"] == "/api/library" and row["status"] == 503 for row in requests):
            raise AssertionError("Offline test did not hit the synthetic server")
        if not any(row["path"] == "/api/library" and row["status"] == 200 and row["time"] >= recovery_started for row in requests):
            raise AssertionError("Recovery did not fetch a fresh library response")
        checks.append({"check":"offline-recovery-and-return", "recovered_title":album_title, "state":state()})
        result = {"status":"passed", "label":"SYNTHETIC QA", "checks":checks,
                  "scope":"Real Kodi Format browsing, artwork request, ordered queue, native playback clock, skip, back and HTTP-outage recovery",
                  "limitations":["Synthetic loopback server, not the user's Format server", "Clocked discard sink, not audible hardware output", "No physical Pi acceptance"]}
        (out / "format-result.json").write_text(json.dumps(result, indent=2) + "\n")
        print("PASS: real Kodi Format synthetic browse/playback/recovery", flush=True)
        return result
    except Exception as error:
        try:
            screenshot("format-failure")
        except Exception:
            pass
        result = {"status":"failed", "reason":str(error), "checks":checks, "last_format_state":last,
                  "last_gui_state":state(), "traceback":traceback.format_exc()}
        (out / "format-result.json").write_text(json.dumps(result, indent=2) + "\n")
        raise

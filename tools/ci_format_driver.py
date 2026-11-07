"""Actual GUI/player Format assertions, called from ci_kodi_smoke.sh's driver.

run(globals()) consumes state/wait_for/press/screenshot/find_label/settle_focus hooks.
No network RPC is enabled; playback evidence comes from the read-only observer.
"""
import json
import os
from pathlib import Path
import subprocess
import time
import traceback
from PIL import Image, ImageChops, ImageStat
from urllib.parse import parse_qs, urlsplit


ADDON_ID = "plugin.audio.aperture.format"
ROOT_LABELS = ["Albums", "Artists", "Search library", "Find music", "Downloads", "Configure Format server"]


def view_is(actual, mode):
    """The property alone cannot prove Kodi rendered or focused the right view."""
    shelf = mode == "albums"
    return (actual.get("format_view") == mode
            and actual.get("shelf_visible") is shelf
            and actual.get("list_visible") is (not shelf)
            and str(actual.get("focus")) == ("64" if shelf else "63"))


def title_direction(mode):
    return "Right" if mode == "albums" else "Down"


def mutation_requests(requests):
    return [row for row in requests if row.get("method") not in ("GET", "HEAD")]


def assert_mock_mutations(requests, expected_paths, identifier):
    rows = mutation_requests(requests)
    if [(row.get("method"), row.get("path"), row.get("status"), row.get("id")) for row in rows] != [
            ("POST", path, 202, [identifier]) for path in expected_paths]:
        raise AssertionError("Unexpected or repeated Format mutation: " + repr(rows))
    return rows


def assert_protected_health_evidence(requests):
    """Prove health cases and per-action permissions from actual fixture requests."""
    cases = {name:False for name in ("protected-ready", "acquire-revoked", "missing-contract",
                                     "malformed-capabilities", "health-unavailable")}
    for row in requests:
        if row.get("path") != "/api/health":
            continue
        if row.get("status") == 503:
            cases["health-unavailable"] = True
            continue
        if row.get("status") != 200:
            continue
        health = row.get("health")
        if health == {}:
            cases["missing-contract"] = True
        if not isinstance(health, dict):
            continue
        capabilities = health.get("capabilities")
        if "capabilities" in health and not isinstance(capabilities, dict) and health.get("readOnly") is False:
            cases["malformed-capabilities"] = True
        if not isinstance(capabilities, dict) or health.get("readOnly") is not True:
            continue
        if capabilities.get("cancel") is True and capabilities.get("prioritize") is True:
            if capabilities.get("acquire") is True:
                cases["protected-ready"] = True
            elif capabilities.get("acquire") is False:
                cases["acquire-revoked"] = True
    if not all(cases.values()):
        raise AssertionError("Missing native permission cases: " + repr(cases))
    actions = {"/api/acquire-album":"acquire", "/api/acquisitions/cancel":"cancel",
               "/api/acquisitions/prioritize":"prioritize"}
    for row in mutation_requests(requests):
        health = row.get("health")
        capabilities = health.get("capabilities") if isinstance(health, dict) else None
        action = actions.get(row.get("path"))
        if (not isinstance(health, dict) or not isinstance(capabilities, dict)
                or health.get("readOnly") is not True or action is None or capabilities.get(action) is not True
                or any(capabilities.get(key) is not False for key in ("editMetadata", "deleteMedia", "repair"))
                or (action in ("cancel", "prioritize") and capabilities.get("acquire") is not False)):
            raise AssertionError("Mutation did not respect protected per-action permissions: " + repr(row))
    return cases


def route_is(folder, action, **parameters):
    """Match the actual plugin route, never an action-name substring."""
    parsed = urlsplit(folder)
    expected = {key: [str(value)] for key, value in parameters.items()}
    if action is not None:
        expected["action"] = [action]
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


def navigate_root(press, wait_for, settle_focus, max_steps=12):
    """Use real folder history; ActivateWindow ignores an already-active Music window."""
    for _ in range(max_steps):
        current = settle_focus()
        if current.get("dialog") != 9999:
            raise AssertionError("Unexpected dialog while returning to Format root: " + repr(current))
        if current.get("window") != 10502:
            before = press("k")
            wait_for("Enter Format root from outside Music", lambda s: s.get("window") == 10502
                     and s.get("dialog") == 9999 and route_is(s.get("folder", ""), None), after=before)
            continue
        if route_is(current.get("folder", ""), None):
            return current
        folder = urlsplit(current.get("folder", ""))
        if folder.scheme == "plugin" and folder.netloc == ADDON_ID:
            previous = (current.get("window"), current.get("folder"))
            before = press("BackSpace")
            wait_for("Back through Format history toward root", lambda s: s.get("dialog") == 9999
                     and (s.get("window"), s.get("folder")) != previous, after=before)
        else:
            # A failed directory can leave Music at its unrelated native root.
            # Leave that window before activating Format; do not claim it is root.
            before = press("Escape")
            wait_for("Leave unrelated Music window before reopening Format", lambda s: s.get("dialog") == 9999
                     and s.get("window") != 10502, after=before)
    raise AssertionError("Format history did not reach the exact root: " + repr(settle_focus()))


def reopen_albums(press, wait_for, settle_focus, find_label):
    """Recover from Kodi discarding a failed directory, through native UI."""
    navigate_root(press, wait_for, settle_focus)
    find_label("Albums", "Down", 5)
    before = press("Return")
    wait_for("Format Albums reopened after outage", lambda s: s.get("window") == 10502
             and s.get("dialog") == 9999 and route_is(s.get("folder", ""), "albums"), after=before)
    settle_focus()


def return_to_album_shelf(press, wait_for, settle_focus, album_id):
    """Stop remembers the track folder; use its real parent, not ActivateWindow."""
    wait_for("Stopped track returns to its album folder", lambda s: s.get("window") == 10502
             and s.get("dialog") == 9999 and route_is(s.get("folder", ""), "album", album_id=album_id))
    settle_focus()
    before = press("BackSpace")
    wait_for("Back from stopped track to album shelf", lambda s: s.get("window") == 10502
             and s.get("dialog") == 9999 and route_is(s.get("folder", ""), "albums"), after=before)
    settle_focus()


def open_album_tracks(press, wait_for, settle_focus, find_label, album_id):
    """Track browsing is explicit; selecting the album itself starts playback."""
    before = press("c")
    wait_for("Album browse context", lambda s: s.get("dialog") == 10106, after=before)
    settle_focus()
    find_label("Browse tracks", "Down", 12)
    before = press("Return")
    wait_for("Explicit album track browsing", lambda s: s.get("window") == 10502
             and s.get("dialog") == 9999 and route_is(s.get("folder", ""), "album", album_id=album_id), after=before)
    settle_focus()


def successful_recovery_request(requests, started, completed):
    return any(row["path"] == "/api/library" and row["status"] == 200
               and started <= row["time"] <= completed for row in requests)


def turntable_pixel_change(first, second):
    """Compare only the central record, excluding clocks/progress and OSD labels."""
    with Image.open(first) as a, Image.open(second) as b:
        if a.size != (1920, 1080) or b.size != a.size:
            raise AssertionError("Turntable evidence must be full-resolution Kodi screenshots")
        box = (690, 370, 1230, 650)
        delta = ImageChops.difference(a.convert("RGB").crop(box), b.convert("RGB").crop(box))
        return sum(ImageStat.Stat(delta).mean) / 3


def track_presentation_ready(actual):
    """Audio RPC appears before Kodi's own busy dialog finishes opening."""
    return (actual.get("window") == 10502 and actual.get("dialog") == 9999
            and actual.get("nowplaying_button_visible") is True
            and view_is(actual, "tracks") and actual.get("player") is not None
            and actual["player"]["properties"]["time"].get("seconds", 0) >= 1)


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
        mode = {"albums":"albums", "artist":"albums", "album":"tracks", "search":"menu"}[action]
        def correct_view(actual):
            return route_is(actual.get("folder", ""), action, **parameters) and view_is(actual, mode)
        actual = wait_music("Format folder before focusing " + title,
                            correct_view, after=after)
        for step in range(max_steps + 1):
            # A changed title can be the first frame of a moving container.
            # Settle first, then take a newer metadata sample before deciding
            # whether another arrow is necessary. Never act on the prior frame.
            actual = settled_music("Stable Format focus toward " + title,
                                   correct_view,
                                   after=actual["sequence"])
            if actual.get("focused_title") == title:
                return actual
            if step == max_steps:
                break
            previous = actual.get("focused_title")
            sequence = actual["sequence"]
            press(title_direction(actual.get("format_view")))
            actual = wait_music("Format focus changed toward " + title,
                                lambda s: correct_view(s)
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
                   and s.get("focused_title") == album_title and "/api/cover?" in s.get("art", "")
                   and view_is(s, "albums"),
                   after=actual["sequence"])

    def read_requests():
        return [json.loads(line) for line in (out / "format-requests.jsonl").read_text().splitlines()]

    def wait_view(action, mode, **parameters):
        wait_for("Format route " + str(action), lambda s: s.get("window") == 10502
                 and s.get("dialog") == 9999 and route_is(s.get("folder", ""), action, **parameters))
        return settled_music("Native Format " + mode + " view",
                             lambda s: route_is(s.get("folder", ""), action, **parameters) and view_is(s, mode))

    def root_menu():
        navigate_root(press, wait_for, settle_focus)
        actual = wait_view(None, "menu")
        if [label for label in actual["labels"] if label in ROOT_LABELS] != ROOT_LABELS:
            raise AssertionError("Unified Format root labels/order are wrong: " + repr(actual))
        return actual

    def select_root(label):
        root_menu()
        find_label(label, "Down", 8)
        return press("Return")

    def prompt_search(label, action, query=None):
        before = select_root(label)
        wait_for("Native Format search keyboard", lambda s: s.get("dialog") == 10103, after=before)
        settle_focus()
        if query is None:
            before = press("Escape")
            wait_for("Cancelled search returns to Format root", lambda s: s.get("dialog") == 9999
                     and route_is(s.get("folder", ""), None), after=before)
            return wait_view(None, "menu")
        # Real keyboard input, not RPC, direct plugin execution or fixture UI.
        subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "25", query], check=True, timeout=15)
        before = press("Return")
        wait_for("Search is canonical and keyboard dismissed", lambda s: s.get("dialog") == 9999
                 and route_is(s.get("folder", ""), action, q=query), after=before)
        return wait_view(action, "catalog" if action == "find_music" else "menu", q=query)

    def preview():
        prompt_search("Find music", "find_music", config["artist"])
        find_label(config["catalog_title"] + " (2026)", "Down", 6)
        before = press("Return")
        wait_for("Catalogue album preview", lambda s: s.get("dialog") == 9999
                 and route_is(s.get("folder", ""), "catalog_album", album_id=config["catalog_id"]), after=before)
        actual = wait_view("catalog_album", "catalog", album_id=config["catalog_id"])
        for title in config["catalog_tracks"]:
            if not any(title in label for label in actual["labels"]):
                raise AssertionError("Missing catalogue preview track: " + title)
        if actual.get("player") is not None:
            raise AssertionError("Catalogue preview unexpectedly started playback")
        return actual

    def confirmation(answer, name=None):
        settle_focus()
        if name:
            screenshot(name)
        find_label("Yes" if answer else "No", "Right", 3)
        before = press("Return")
        wait_for("Explicit native confirmation dismissed", lambda s: s.get("dialog") == 9999, after=before)
        settle_focus()

    def start_acquire():
        find_label("Download album", "Down", 6)
        before = press("Return")
        wait_for("Acquisition requires explicit native confirmation", lambda s: s.get("dialog") == 10100, after=before)

    def queued_action(label=None):
        wait_view("downloads", "downloads")
        find_label(config["artist"] + " - " + config["catalog_title"] + " | Queued", "Down", 8)
        before = press("Return")
        wait_for("Native download action selector", lambda s: s.get("dialog") == 12000, after=before)
        settle_focus()
        if label is None:
            before = press("Escape")
            wait_for("Dismissed download actions", lambda s: s.get("dialog") == 9999, after=before)
            return wait_view("downloads", "downloads")
        find_label(label, "Down", 4)
        before = press("Return")
        wait_for("Download change requires confirmation", lambda s: s.get("dialog") == 10100, after=before)

    def health(value):
        path = runtime / "format-fixture/health.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value))
        temporary.replace(path)

    def protected_health(acquire=True):
        value = json.loads(json.dumps(config["protected_health"]))
        value["capabilities"]["acquire"] = acquire
        value["downloads"].update(ready=acquire, reason=None if acquire else "downloader_unavailable")
        health(value)

    def unified_integration():
        root_state = root_menu()
        screenshot("format-06-unified-root")
        before = select_root("Artists")
        wait_for("Format artists route", lambda s: s.get("dialog") == 9999
                 and route_is(s.get("folder", ""), "artists"), after=before)
        wait_view("artists", "menu")
        find_label(config["artist"], "Down", 5)
        before = press("Return")
        wait_for("Artist album shelf route", lambda s: s.get("dialog") == 9999
                 and route_is(s.get("folder", ""), "artist", artist=config["artist"]), after=before)
        find_title(album_title, "artist", artist=config["artist"])
        artist_state = wait_view("artist", "albums", artist=config["artist"])
        screenshot("format-07-artist-albums")
        checks.append({"check":"unified-root-and-artists", "root":root_state, "artist":artist_state})

        # Returning through Artists legitimately refetches its library. Measure
        # prompt cancellation only once that native Back navigation has finished.
        root_menu()
        baseline = len(read_requests())
        prompt_search("Search library", "search")
        prompt_search("Find music", "find_music")
        if any(row["path"] in ("/api/library", "/api/catalog/search") for row in read_requests()[baseline:]):
            raise AssertionError("Cancelled search made a library or catalogue request")
        prompt_search("Search library", "search", config["artist"])
        actual = find_title(album_title, "search", q=config["artist"])
        screenshot("format-08-library-search")
        checks.append({"check":"local-search-and-cancelled-prompts", "search":actual})

        prompt_search("Find music", "find_music", config["artist"])
        screenshot("format-09-find-music")
        preview_state = preview()
        screenshot("format-10-catalogue-preview")
        find_label("1.1  " + config["catalog_tracks"][0], "Down", 6)
        sequence, selected_at = music()["sequence"], time.time()
        before = press("Return")
        wait_for("Catalogue track keeps the same preview", lambda s: s.get("dialog") == 9999
                 and route_is(s.get("folder", ""), "catalog_album", album_id=config["catalog_id"]), after=before)
        actual = wait_music("Catalogue row stays nonplayable after invocation", lambda s: s.get("time", 0) > selected_at + 1.5,
                            after=sequence)
        if (not route_is(actual.get("folder", ""), "catalog_album", album_id=config["catalog_id"])
                or actual.get("player") is not None or actual.get("queue") != preview_state.get("queue")):
            raise AssertionError("Selecting a catalogue preview row changed directory or playback")
        wait_view("catalog_album", "catalog", album_id=config["catalog_id"])
        start_acquire()
        confirmation(False, "format-11-decline-acquisition")
        wait_view("catalog_album", "catalog", album_id=config["catalog_id"])
        assert_mock_mutations(read_requests(), [], config["catalog_id"])
        before = press("BackSpace")
        wait_for("Back after declining acquisition keeps catalogue history", lambda s: s.get("dialog") == 9999
                 and route_is(s.get("folder", ""), "find_music", q=config["artist"]), after=before)
        wait_view("find_music", "catalog", q=config["artist"])
        find_label(config["catalog_title"] + " (2026)", "Down", 6)
        before = press("Return")
        wait_for("Reopen preview through preserved catalogue parent", lambda s: s.get("dialog") == 9999
                 and route_is(s.get("folder", ""), "catalog_album", album_id=config["catalog_id"]), after=before)
        wait_view("catalog_album", "catalog", album_id=config["catalog_id"])

        # Even explicit approval is insufficient if permissions change while
        # its dialog is open. The action must recheck health before POST.
        start_acquire()
        protected_health(acquire=False)
        find_label("Yes", "Right", 3)
        before = press("Return")
        wait_for("Permission changed during confirmation blocks POST", lambda s: s.get("dialog") == 12002, after=before)
        settle_focus()
        screenshot("format-12-acquire-capability-revoked")
        before = press("Return")
        wait_for("Permission message dismissed", lambda s: s.get("dialog") == 9999, after=before)
        revoked = preview()
        if "Download album" in revoked["labels"]:
            raise AssertionError("Revoked acquisition capability offers Download album")
        screenshot("format-13-acquisition-disabled-preview")
        protected_health()
        failed_health = runtime / "format-fixture/health-offline"
        failed_health.write_text("SYNTHETIC QA unavailable health\n")
        unavailable = preview()
        if "Download album" in unavailable["labels"]:
            raise AssertionError("Unavailable health offered Download album")
        screenshot("format-14-health-unavailable")
        failed_health.unlink()
        health({})
        missing = preview()
        if "Download album" in missing["labels"]:
            raise AssertionError("Missing permission contract offered Download album")
        screenshot("format-14b-missing-health-contract")
        health({"readOnly":False, "capabilities":[]})
        malformed = preview()
        if "Download album" in malformed["labels"]:
            raise AssertionError("Malformed capabilities fell back to readOnly false")
        screenshot("format-14c-malformed-capabilities")
        assert_mock_mutations(read_requests(), [], config["catalog_id"])
        checks.append({"check":"catalogue-preview-decline-capability-failclosed", "preview":preview_state,
                       "acquire_revoked":revoked, "health_unavailable":unavailable,
                       "missing_contract":missing, "malformed_capabilities":malformed, "mutations":[]})

        protected_health()
        preview()
        start_acquire()
        confirmation(True, "format-15-confirm-synthetic-acquisition")
        actual = wait_view("downloads", "downloads")
        queued_label = config["artist"] + " - " + config["catalog_title"] + " | Queued"
        find_label(queued_label, "Down", 8)
        screenshot("format-16-queued-download")
        expected = ["/api/acquire-album"]
        assert_mock_mutations(read_requests(), expected, config["catalog_id"])
        protected_health(acquire=False)
        press("l")
        wait_view("downloads", "downloads")
        queued_action()  # Escape out of the action picker must be a no-op.
        queued_action("Move to front")
        confirmation(False)
        wait_view("downloads", "downloads")
        assert_mock_mutations(read_requests(), expected, config["catalog_id"])
        queued_action("Move to front")
        confirmation(True)
        wait_view("downloads", "downloads")
        expected.append("/api/acquisitions/prioritize")
        assert_mock_mutations(read_requests(), expected, config["catalog_id"])
        queued_action("Cancel download")
        confirmation(True, "format-17-confirm-cancel-download")
        wait_view("downloads", "downloads")
        expected.append("/api/acquisitions/cancel")
        cancelled_label = config["artist"] + " - " + config["catalog_title"] + " | Cancelled"
        find_label(cancelled_label, "Down", 8)
        screenshot("format-18-cancelled-download")
        # Refresh and reopening Downloads must never replay a mutation URL.
        refresh_started = time.time()
        press("l")
        wait_view("downloads", "downloads")
        before = select_root("Downloads")
        wait_for("Reopen native Downloads", lambda s: s.get("dialog") == 9999
                 and route_is(s.get("folder", ""), "downloads"), after=before)
        actual = wait_view("downloads", "downloads")
        find_label(cancelled_label, "Down", 8)
        if not any(row["path"] == "/api/acquisitions" and row["status"] == 200
                   and row["time"] >= refresh_started for row in read_requests()):
            raise AssertionError("Downloads refresh did not fetch current status")
        mutations = assert_mock_mutations(read_requests(), expected, config["catalog_id"])
        items = json.loads((runtime / "format-fixture/acquisitions.json").read_text())
        if len(items) != 1 or items[0]["id"] != config["catalog_id"] or items[0]["status"] != "cancelled" or items[0].get("priority") != 100:
            raise AssertionError("Native confirmed actions did not update the synthetic queue correctly")
        checks.append({"check":"explicit-mock-acquisition-prioritize-cancel-and-no-replay",
                       "mutations":mutations, "acquisitions":items, "state":actual,
                       "health_cases":assert_protected_health_evidence(read_requests())})
        return_home()

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
        shelf_state = music()
        screenshot("format-01-albums")
        sequence = music()["sequence"]
        open_album_tracks(press, wait_for, settle_focus, find_label, config["album_id"])
        actual = find_title(config["expected_titles"][0], "album", after=sequence, album_id=config["album_id"])
        track_view = settled_music("Native track list, not the horizontal album shelf",
                                   lambda s: route_is(s.get("folder", ""), "album", album_id=config["album_id"])
                                   and view_is(s, "tracks"), after=actual["sequence"])
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
        restored_shelf = settled_music("Back restores the album shelf from the track list",
                                       lambda s: route_is(s.get("folder", ""), "albums") and view_is(s, "albums"))
        checks.append({"check":"native-shelf-list-and-back", "albums":shelf_state,
                       "tracks":track_view, "restored_albums":restored_shelf})
        screenshot("format-02b-back-to-album-shelf")
        # Normal Select/Enter, not a hidden context-menu action, must play the
        # complete album and enter the turntable.
        sequence = music()["sequence"]
        press("Return")
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
        checks.append({"check":"album-selection-ordered-playback", "queue":actual["queue"], "start_seconds":initial_clock, "later_seconds":clock(later)})
        wait_music("Native turntable opens for explicit album playback",
                   lambda s: s.get("window") == 12006 and s.get("nowplaying_visible") is True
                   and s.get("playing_title") == config["expected_titles"][0])
        wait_music("Secondary bottom-left album tracks match the ordered release",
                   lambda s: s.get("album_tracks_visible") is True
                   and [title for title in s.get("album_track_titles", []) if title] == config["expected_titles"])
        wait_music("Presentation yields to native playback overlay",
                   lambda s: s.get("native_seekbar_visible") is True
                   and s.get("presentation_header_visible") is False
                   and s.get("presentation_footer_visible") is False)
        screenshot("format-03-playback")
        time.sleep(1)
        screenshot("format-03b-record-rotated")
        moving = turntable_pixel_change(out / "screenshots/format-03-playback.png",
                                        out / "screenshots/format-03b-record-rotated.png")
        if moving < 0.5:
            raise AssertionError("Record artwork did not visibly rotate: " + str(moving))
        wait_music("Clean turntable after native playback overlay dismisses",
                   lambda s: s.get("native_seekbar_visible") is False
                   and s.get("presentation_header_visible") is True
                   and s.get("presentation_footer_visible") is True)
        screenshot("format-03j-clean-turntable")
        sequence = music()["sequence"]
        press("space")
        paused = wait_music("Pause stops actual audio and shows paused status", lambda s: s.get("player")
                            and s["player"]["properties"].get("speed") == 0 and s.get("paused_visible") is True,
                            after=sequence)
        screenshot("format-03c-paused")
        time.sleep(1)
        screenshot("format-03d-paused-still")
        still = turntable_pixel_change(out / "screenshots/format-03c-paused.png",
                                      out / "screenshots/format-03d-paused-still.png")
        if still > 0.15:
            raise AssertionError("Paused record continued moving: " + str(still))
        before = press("Return")
        wait_for("Native music playback controls", lambda s: s.get("dialog") == 10120, after=before)
        screenshot("format-03e-native-controls")
        before = press("Escape")
        wait_for("Music controls dismiss", lambda s: s.get("dialog") == 9999, after=before)
        before = press("Escape")
        wait_for("Back returns to same album shelf", lambda s: s.get("window") == 10502
                 and route_is(s.get("folder", ""), "albums"), after=before)
        sequence = music()["sequence"]
        before = press("Down")
        wait_for("Now playing button receives focus", lambda s: s.get("focus") == 65, after=before)
        before = press("Return")
        wait_for("Now playing reopens without a new stream", lambda s: s.get("window") == 12006, after=before)
        actual = wait_music("Reopened record remains paused", lambda s: s.get("player")
                            and s["player"]["properties"].get("speed") == 0 and s.get("nowplaying_visible") is True,
                            after=sequence)
        if actual["queue"] != paused["queue"] or abs(clock(actual) - clock(paused)) > 0.5:
            raise AssertionError("Back/reopen changed playback queue or paused position")
        sequence = actual["sequence"]
        press("space")
        wait_music("Resume native playback", lambda s: s.get("player")
                   and s["player"]["properties"].get("speed") == 1, after=sequence)
        screenshot("format-03h-resumed")
        time.sleep(1)
        screenshot("format-03i-resumed-rotating")
        resumed = turntable_pixel_change(out / "screenshots/format-03h-resumed.png",
                                        out / "screenshots/format-03i-resumed-rotating.png")
        if resumed < 0.5:
            raise AssertionError("Record did not resume rotation: " + str(resumed))
        checks.append({"check":"native-turntable-motion-pause-controls-back-reopen",
                       "playing_pixel_change":moving, "paused_pixel_change":still,
                       "resumed_pixel_change":resumed})
        sequence = music()["sequence"]
        press("period")
        actual = wait_music("Skip reaches second track", lambda s: s.get("player") is not None
                            and track_id(s["player"]["item"]) == config["expected_ids"][1], after=sequence)
        checks.append({"check":"skip-next", "player":actual["player"]})
        for expected_id in config["expected_ids"][2:]:
            sequence = music()["sequence"]
            press("period")
            actual = wait_music("Next native album track", lambda s: s.get("player") is not None
                                and track_id(s["player"]["item"]) == expected_id, after=sequence)
        screenshot("format-03f-missing-art-fallback")
        actual = music()
        sequence, previous_time = actual["sequence"], clock(actual)
        press("comma")
        actual = wait_music("Previous changes track or restarts current track", lambda s: s.get("player") is not None
                            and (track_id(s["player"]["item"]) == config["expected_ids"][2]
                                 or (track_id(s["player"]["item"]) == config["expected_ids"][3]
                                     and clock(s) < previous_time - 0.1)), after=sequence)
        if track_id(actual["player"]["item"]) == config["expected_ids"][3]:
            sequence = actual["sequence"]
            press("comma")
            actual = wait_music("Previous from restarted track returns to third", lambda s: s.get("player") is not None
                                and track_id(s["player"]["item"]) == config["expected_ids"][2], after=sequence)
        checks.append({"check":"turntable-skip-previous-and-missing-art", "player":actual["player"]})
        sequence = actual["sequence"]
        press("x")
        wait_music("Stop synthetic playback", lambda s: s.get("player") is None, after=sequence)
        return_home()
        opened_albums()
        sequence = music()["sequence"]
        open_album_tracks(press, wait_for, settle_focus, find_label, config["album_id"])
        find_title(config["expected_titles"][0], "album", after=sequence, album_id=config["album_id"])
        sequence = music()["sequence"]
        press("Return")
        wait_music("Direct native track plays", lambda s: s.get("player") is not None
                   and track_id(s["player"]["item"]) == config["expected_ids"][0], after=sequence)
        settled_music("Direct track ready for navigation after native busy dialog",
                      track_presentation_ready, after=sequence)
        before = press("Right")
        wait_for("Track list can reach Now playing", lambda s: s.get("focus") == 65, after=before)
        before = press("Return")
        wait_for("Direct track native turntable", lambda s: s.get("window") == 12006, after=before)
        screenshot("format-03g-selected-track")
        sequence = music()["sequence"]
        press("x")
        wait_music("Stop selected track", lambda s: s.get("player") is None, after=sequence)
        return_to_album_shelf(press, wait_for, settle_focus, config["album_id"])
        # HTTP 503 simulates server outage. No system networking is changed.
        find_title(album_title, "albums")
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
        # Failed endOfDirectory can return Kodi to Music root (folder="").
        # Refresh there cannot retry Format. Reopen its root and choose Albums.
        reopen_albums(press, wait_for, settle_focus, find_label)
        actual = find_title(album_title, "albums", after=sequence)
        settled_music("Reopened album metadata proves outage recovery",
                   lambda s: route_is(s.get("folder", ""), "albums") and s.get("focused_title") == album_title,
                   after=actual["sequence"])
        recovery_completed = time.time()
        requests = [json.loads(line) for line in (out / "format-requests.jsonl").read_text().splitlines()]
        if not successful_recovery_request(requests, recovery_started, recovery_completed):
            raise AssertionError("Recovery did not fetch a fresh library response")
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
        checks.append({"check":"offline-recovery-and-return", "recovered_title":album_title, "state":state()})
        unified_integration()
        assert_mock_mutations(read_requests(), ["/api/acquire-album", "/api/acquisitions/prioritize",
                                                "/api/acquisitions/cancel"], config["catalog_id"])
        # Multiple synthetic releases are required to see real perspective,
        # centering and edge navigation. The normal fixture has only one album.
        original_library = library_path.read_bytes()
        coverflow_library = json.loads(original_library)
        seed = coverflow_library["albums"][0]
        coverflow_library["albums"] = [dict(seed, id="coverflow-" + str(i),
            title="SYNTHETIC QA Coverflow " + str(i)) for i in range(1, 7)]
        try:
            temporary.write_text(json.dumps(coverflow_library))
            temporary.replace(library_path)
            return_home()
            before = press("j")
            wait_for("Coverflow fixture shelf", lambda s: route_is(s.get("folder", ""), "albums"), after=before)
            settled_music("Random entry chooses an actual record", lambda s: s.get("shelf_position") in [str(i) for i in range(1, 7)])
            baseline_queue = music().get("queue")
            press("Home")  # Deterministic sweep after verifying randomized entry.
            settle_focus()
            for i in range(1, 7):
                actual = find_title("SYNTHETIC QA Coverflow " + str(i), "albums")
                if actual.get("shelf_position") != str(i) or actual.get("queue") != baseline_queue or actual.get("player") is not None:
                    raise AssertionError("Coverflow navigation changed playback or lost order: " + repr(actual))
                if i in (1, 3, 6):
                    screenshot("format-06-coverflow-" + str(i))
            for i in (5, 4, 3):
                sequence = music()["sequence"]
                press("Left")
                actual = settled_music("Coverflow reverse focus", lambda s: s.get("focused_title") == "SYNTHETIC QA Coverflow " + str(i), after=sequence)
            screenshot("format-06-coverflow-reversed")
            checks.append({"check":"coverflow-six-albums-forward-backward-no-playback", "state":actual})
            return_home()
        finally:
            temporary.write_bytes(original_library)
            temporary.replace(library_path)
        result = {"status":"passed", "label":"SYNTHETIC QA", "checks":checks,
                  "scope":"Real Kodi unified Format root, artists/library search, native album shelf and track list, ordered playback, catalogue preview, cancelled prompts, protected per-action capabilities and malformed/unavailable health restrictions, explicit mock acquisition/priority/cancel, no mutation replay and HTTP-outage recovery",
                  "limitations":["Synthetic loopback server, not the user's Format server", "Mock acquisition queue only; no provider or downloaded media", "Clocked discard sink, not audible hardware output", "No physical Pi acceptance"]}
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

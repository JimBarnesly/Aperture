"""Regression tests for real-Kodi driver's observation and route barriers."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ci_format_driver", ROOT / "tools/ci_format_driver.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class DriverTest(unittest.TestCase):
    def test_exact_album_route_does_not_match_album_list(self):
        base = "plugin://plugin.audio.aperture.format/"
        self.assertTrue(driver.route_is(base + "?action=albums", "albums"))
        self.assertFalse(driver.route_is(base + "?action=albums", "album"))
        self.assertFalse(driver.route_is(base + "?action=album&album_id=1", "albums"))
        self.assertFalse(driver.route_is("https://example.test/?action=albums", "albums"))
        self.assertFalse(driver.route_is("plugin://other.addon/?action=albums", "albums"))
        self.assertFalse(driver.route_is(base + "?action=albums&action=album", "albums"))
        self.assertFalse(driver.route_is(base + "?action=albums&extra=", "albums"))

    def test_album_id_is_compared_after_decoding(self):
        album_id = "SYNTHETIC%00Album, A & B"
        route = "plugin://plugin.audio.aperture.format/?" + urlencode({"album_id": album_id, "action": "album"})
        self.assertTrue(driver.route_is(route, "album", album_id=album_id))
        self.assertFalse(driver.route_is(route, "album", album_id="different"))

    def test_sequence_barrier_rejects_previous_playback_observation(self):
        actual = {"pid": 42, "sequence": 10, "time": 99}
        self.assertFalse(driver.observation_is_fresh(actual, 42, 10, 100))
        self.assertTrue(driver.observation_is_fresh(actual, 42, 9, 100))
        self.assertFalse(driver.observation_is_fresh(actual, 43, 9, 100))
        self.assertFalse(driver.observation_is_fresh(actual, 42, 9, 103))
        self.assertFalse(driver.observation_is_fresh(actual, 42, 9, 98))

    def test_metadata_barrier_starts_after_focus_settles(self):
        events = []
        predicate = lambda actual: actual["focused_title"] == "Target"
        def settle():
            events.append("settle")
        def music():
            events.append("metadata")
            return {"sequence": 20}
        def wait(description, actual_predicate, after):
            events.append(("wait", after))
            self.assertIs(actual_predicate, predicate)
            return {"sequence": after + 1, "focused_title": "Target"}
        actual = driver.settled_observation(settle, music, wait, "focus", predicate, after=5)
        self.assertEqual(events, ["settle", "metadata", ("wait", 20)])
        self.assertEqual(actual["sequence"], 21)
        events.clear()
        driver.settled_observation(settle, music, wait, "focus", predicate, after=25)
        self.assertEqual(events[-1], ("wait", 25))

    def test_failed_settling_does_not_accept_or_sample_stale_metadata(self):
        music, wait = Mock(), Mock()
        with self.assertRaisesRegex(AssertionError, "animation"):
            driver.settled_observation(Mock(side_effect=AssertionError("animation")), music, wait,
                                       "focus", lambda actual: True)
        music.assert_not_called()
        wait.assert_not_called()

    def test_find_title_waits_for_prior_animation_before_pressing_arrow(self):
        # Exercise the real run's first folder transition. The old observer title
        # is wrong during animation, but settles onto the requested album. An
        # extra Down would overshoot it and must never be sent.
        with tempfile.TemporaryDirectory(prefix="aperture-kodi-smoke.") as directory:
            runtime = Path(directory)
            out = runtime / "out"
            out.mkdir()
            title = "SYNTHETIC QA Double"
            (out / "format-expected.json").write_text(json.dumps({"runtime": str(runtime), "album_title": title}))
            actual = {"sequence": 1, "time": time.time(), "pid": os.getpid(), "enabled": True,
                      "folder": "", "focused_title": "", "art": "/api/cover?id=fixture",
                      "format_view":"albums", "shelf_visible":True, "list_visible":False, "focus":"64"}
            gui = {"window": 10000, "dialog": 9999}
            keys = []
            def publish(*args):
                actual["sequence"] += 1
                actual["time"] = time.time()
                (out / "format-state.json").write_text(json.dumps(actual))
            publish()
            def settle():
                if keys:
                    actual["focused_title"] = title
                publish()
                return gui
            def press(key):
                keys.append(key)
                self.assertEqual(key, "j", "Do not overshoot the album while the prior animation settles")
                actual.update(folder="plugin://plugin.audio.aperture.format/?action=albums", focused_title="Previous animation frame")
                gui.update(window=10502, folder=actual["folder"])
                publish()
                return 1
            def wait_for(description, predicate, after):
                self.assertTrue(predicate(gui))
                return gui
            def screenshot(name):
                if name == "format-01-albums":
                    raise RuntimeError("First stable album reached")
            hooks = {"state": lambda: gui, "wait_for": wait_for, "press": press,
                     "screenshot": screenshot, "find_label": Mock(), "settle_focus": settle}
            env = {"APERTURE_SMOKE_OUT": str(out), "KODI_DATA": str(runtime / "data"),
                   "APERTURE_KODI_PID": str(os.getpid())}
            with patch.dict(os.environ, env), patch.object(driver.time, "sleep", side_effect=publish):
                with self.assertRaisesRegex(RuntimeError, "First stable album reached"):
                    driver.run(hooks)
            self.assertEqual(keys, ["j"])

    def test_album_parent_back_uses_backspace_not_previous_menu(self):
        # Model Kodi's distinct Back/PreviousMenu actions while exercising the
        # real driver through the ordered track list and album context menu.
        with tempfile.TemporaryDirectory(prefix="aperture-kodi-smoke.") as directory:
            runtime = Path(directory)
            out = runtime / "out"
            out.mkdir()
            title, tracks = "SYNTHETIC QA Double", ["Disc 1 Track 1", "Disc 2 Track 1"]
            config = {"runtime": str(runtime), "album_title": title, "album_id": "fixture-album",
                      "expected_titles": tracks, "expected_ids": ["track-1", "track-2"]}
            (out / "format-expected.json").write_text(json.dumps(config))
            albums = "plugin://plugin.audio.aperture.format/?action=albums"
            album = "plugin://plugin.audio.aperture.format/?action=album&album_id=fixture-album"
            actual = {"sequence": 1, "time": time.time(), "pid": os.getpid(), "enabled": True,
                      "folder": "", "focused_title": "", "art": "/api/cover?id=fixture",
                      "format_view":"albums", "shelf_visible":True, "list_visible":False, "focus":"64"}
            gui = {"window": 10000, "dialog": 9999}
            keys = []
            def publish(*args):
                actual["sequence"] += 1
                actual["time"] = time.time()
                (out / "format-state.json").write_text(json.dumps(actual))
            publish()
            def settle():
                publish()
                return gui
            def press(key):
                keys.append(key)
                if key in ("j", "BackSpace"):
                    actual.update(folder=albums, focused_title=title, format_view="albums",
                                  shelf_visible=True, list_visible=False, focus="64")
                    gui.update(window=10502, folder=albums)
                elif key == "Return":
                    actual.update(folder=album, focused_title=tracks[0], format_view="tracks",
                                  shelf_visible=False, list_visible=True, focus="63")
                    gui.update(window=10502, folder=album)
                elif key == "Down":
                    actual["focused_title"] = tracks[1]
                elif key == "Escape":
                    actual.update(folder="", focused_title="")
                    gui.update(window=10000, folder="")
                elif key == "c":
                    gui["dialog"] = 10106
                else:
                    raise AssertionError("Unexpected key: " + key)
                publish()
                return 1
            def wait_for(description, predicate, after):
                self.assertTrue(predicate(gui), description + ": " + repr(gui))
                return gui
            hooks = {"state": lambda: gui, "wait_for": wait_for, "press": press,
                     "screenshot": Mock(), "find_label": Mock(side_effect=RuntimeError("Album context reached")),
                     "settle_focus": settle}
            env = {"APERTURE_SMOKE_OUT": str(out), "KODI_DATA": str(runtime / "data"),
                   "APERTURE_KODI_PID": str(os.getpid())}
            with patch.dict(os.environ, env), patch.object(driver.time, "sleep", side_effect=publish):
                with self.assertRaisesRegex(RuntimeError, "Album context reached"):
                    driver.run(hooks)
            self.assertEqual(keys, ["j", "Return", "Down", "BackSpace", "c"])
            self.assertTrue(driver.route_is(gui["folder"], "albums"))

    def test_real_find_title_uses_right_to_leave_album_parent_card(self):
        with tempfile.TemporaryDirectory(prefix="aperture-kodi-smoke.") as directory:
            runtime = Path(directory)
            out = runtime / "out"
            out.mkdir()
            title = "SYNTHETIC QA Double"
            (out / "format-expected.json").write_text(json.dumps({"runtime":str(runtime), "album_title":title}))
            actual = {"sequence":1, "time":time.time(), "pid":os.getpid(), "enabled":True,
                      "folder":"", "focused_title":"", "art":"/api/cover?id=fixture",
                      "format_view":"albums", "shelf_visible":True, "list_visible":False, "focus":"64"}
            gui, keys = {"window":10000, "dialog":9999}, []
            def publish(*args):
                actual.update(sequence=actual["sequence"] + 1, time=time.time())
                (out / "format-state.json").write_text(json.dumps(actual))
            publish()
            def settle():
                publish()
                return gui
            def press(key):
                keys.append(key)
                if key == "j":
                    actual.update(folder="plugin://plugin.audio.aperture.format/?action=albums", focused_title="")
                    gui.update(window=10502, folder=actual["folder"])
                elif key == "Right":
                    actual["focused_title"] = title
                else:
                    raise AssertionError("Horizontal shelf cannot be navigated with " + key)
                publish()
                return 1
            def wait(description, predicate, after):
                self.assertTrue(predicate(gui))
                return gui
            def capture(name):
                if name == "format-01-albums":
                    raise RuntimeError("Horizontal target reached")
            hooks = {"state":lambda:gui, "wait_for":wait, "press":press, "screenshot":capture,
                     "find_label":Mock(), "settle_focus":settle}
            env = {"APERTURE_SMOKE_OUT":str(out), "KODI_DATA":str(runtime / "data"),
                   "APERTURE_KODI_PID":str(os.getpid())}
            with patch.dict(os.environ, env), patch.object(driver.time, "sleep", side_effect=publish):
                with self.assertRaisesRegex(RuntimeError, "Horizontal target reached"):
                    driver.run(hooks)
            self.assertEqual(keys, ["j", "Right"])

    def test_recovery_reopens_root_then_selects_albums_from_empty_music_root(self):
        current = {"window": 10502, "dialog": 9999, "folder": ""}
        keys, observed_labels = [], []
        def press(key):
            keys.append(key)
            if key == "Escape":
                current.update(window=10000, folder="")
            elif key == "k":
                self.assertNotEqual(current["window"], 10502)
                current.update(window=10502, folder="plugin://plugin.audio.aperture.format/")
            elif key == "Return":
                self.assertEqual(observed_labels, ["Albums"])
                current["folder"] = "plugin://plugin.audio.aperture.format/?action=albums"
            else:
                raise AssertionError("Recovery must navigate, not refresh the empty Music root")
            return len(keys)
        def wait(description, predicate, after):
            self.assertTrue(predicate(current), description)
        def find_label(label, direction, max_steps):
            self.assertTrue(driver.route_is(current["folder"], None))
            observed_labels.append(label)
        settle = Mock(return_value=current)
        driver.reopen_albums(press, wait, settle, find_label)
        self.assertEqual(keys, ["Escape", "k", "Return"])
        self.assertEqual(settle.call_count, 4)
        self.assertTrue(driver.route_is(current["folder"], "albums"))

    def test_recovery_root_does_not_accept_unrelated_music_root(self):
        def wait(description, predicate, after):
            if not predicate({"window": 10502, "dialog": 9999, "folder": ""}):
                raise AssertionError("Still unrelated Music root")
        find = Mock()
        with self.assertRaisesRegex(AssertionError, "unrelated Music root"):
            driver.reopen_albums(Mock(return_value=1), wait,
                                 Mock(return_value={"window":10502, "dialog":9999, "folder":""}), find)
        find.assert_not_called()

    def test_root_navigation_uses_back_when_active_music_ignores_activatewindow(self):
        root = "plugin://plugin.audio.aperture.format/"
        artists = root + "?action=artists"
        artist = root + "?action=artist&artist=A%20SYNTHETIC%20QA"
        current = {"window":10502, "dialog":9999, "folder":artist, "focus":64, "sequence":1}
        keys, transitions = [], []
        def press(key):
            keys.append(key)
            before = current["sequence"]
            current["sequence"] += 1
            if key == "k":
                # Real Kodi ignores ActivateWindow for the already-active Music
                # window. Fresh sequence is not a successful root transition.
                return before
            self.assertEqual(key, "BackSpace")
            current.update(folder=artists if current["folder"] == artist else root, focus=63)
            return before
        def wait(description, predicate, after):
            self.assertTrue(predicate(current), description + ": " + repr(current))
            self.assertGreater(current["sequence"], after)
            transitions.append(current["folder"])
            return dict(current)
        result = driver.navigate_root(press, wait, lambda:dict(current))
        self.assertEqual(keys, ["BackSpace", "BackSpace"])
        self.assertEqual(transitions, [artists, root])
        self.assertTrue(driver.route_is(result["folder"], None))
        self.assertEqual(result["focus"], 63)

    def test_root_navigation_already_at_exact_root_does_not_press_any_key(self):
        current = {"window":10502, "dialog":9999, "folder":"plugin://plugin.audio.aperture.format/"}
        press, wait = Mock(), Mock()
        self.assertEqual(driver.navigate_root(press, wait, lambda:dict(current)), current)
        press.assert_not_called()
        wait.assert_not_called()

    def test_root_navigation_rejects_unchanged_back_despite_new_observation(self):
        current = {"window":10502, "dialog":9999,
                   "folder":"plugin://plugin.audio.aperture.format/?action=artists", "sequence":1}
        keys = []
        def press(key):
            keys.append(key)
            current["sequence"] += 1
            return current["sequence"] - 1
        def wait(description, predicate, after):
            self.assertGreater(current["sequence"], after)
            if not predicate(current):
                raise AssertionError("Back did not change the folder")
        with self.assertRaisesRegex(AssertionError, "did not change"):
            driver.navigate_root(press, wait, lambda:dict(current))
        self.assertEqual(keys, ["BackSpace"])

    def test_root_navigation_never_silently_dismisses_an_unexpected_dialog(self):
        press = Mock()
        with self.assertRaisesRegex(AssertionError, "Unexpected dialog"):
            driver.navigate_root(press, Mock(), lambda:{"window":10502, "dialog":10100})
        press.assert_not_called()

    def test_recovery_http_evidence_must_belong_to_recovery_interval(self):
        def row(at, status=200, path="/api/library"):
            return {"time": at, "status": status, "path": path}
        self.assertFalse(driver.successful_recovery_request([row(9), row(13)], 10, 12))
        self.assertFalse(driver.successful_recovery_request([row(11, 503), row(11, path="/api/cover")], 10, 12))
        self.assertTrue(driver.successful_recovery_request([row(11)], 10, 12))

    def test_new_sequence_alone_is_not_a_gui_transition(self):
        original = {"window": 10502, "folder": "albums", "focus": 55, "list_item": "Album", "sequence": 1}
        self.assertEqual(driver.gui_position(original), driver.gui_position(dict(original, sequence=2)))
        for change in ({"folder": "tracks"}, {"window": 10000}, {"list_item": "Second album"}, {"focus": 56}):
            with self.subTest(change=change):
                self.assertNotEqual(driver.gui_position(original), driver.gui_position(dict(original, **change)))

    def test_view_requires_property_visibility_and_actual_focus(self):
        shelf = {"format_view":"albums", "shelf_visible":True, "list_visible":False, "focus":"64"}
        self.assertTrue(driver.view_is(shelf, "albums"))
        for change in ({"focus":"63"}, {"list_visible":True}, {"shelf_visible":False}, {"format_view":"menu"}):
            with self.subTest(change=change):
                self.assertFalse(driver.view_is(dict(shelf, **change), "albums"))
        for mode in ("menu", "tracks", "catalog", "downloads"):
            actual = {"format_view":mode, "shelf_visible":False, "list_visible":True, "focus":63}
            self.assertTrue(driver.view_is(actual, mode))
            self.assertFalse(driver.view_is(dict(actual, shelf_visible=True), mode))
            self.assertFalse(driver.view_is(dict(actual, focus=64), mode))

    def test_album_shelf_navigation_is_horizontal_and_track_navigation_vertical(self):
        self.assertEqual(driver.title_direction("albums"), "Right")
        for mode in ("tracks", "menu", "catalog", "downloads"):
            self.assertEqual(driver.title_direction(mode), "Down")

    def test_mutation_proof_rejects_any_unexpected_repeated_or_failed_write(self):
        read = {"method":"GET", "path":"/api/library", "status":200}
        acquire = {"method":"POST", "path":"/api/acquire-album", "status":202, "id":["synthetic"]}
        self.assertEqual(driver.assert_mock_mutations([read], [], "synthetic"), [])
        self.assertEqual(driver.assert_mock_mutations([read, acquire], ["/api/acquire-album"], "synthetic"), [acquire])
        for rows in ([acquire], [read, dict(acquire, method="DELETE")], [dict(acquire, status=403)],
                     [dict(acquire, id=["another"])], [acquire, acquire]):
            with self.subTest(rows=rows), self.assertRaisesRegex(AssertionError, "mutation"):
                driver.assert_mock_mutations(rows, [] if rows == [acquire] else ["/api/acquire-album"], "synthetic")


if __name__ == "__main__":
    unittest.main()

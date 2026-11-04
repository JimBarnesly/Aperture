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
                      "folder": "", "focused_title": "", "art": "/api/cover?id=fixture"}
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

    def test_new_sequence_alone_is_not_a_gui_transition(self):
        original = {"window": 10502, "folder": "albums", "focus": 55, "list_item": "Album", "sequence": 1}
        self.assertEqual(driver.gui_position(original), driver.gui_position(dict(original, sequence=2)))
        for change in ({"folder": "tracks"}, {"window": 10000}, {"list_item": "Second album"}, {"focus": 56}):
            with self.subTest(change=change):
                self.assertNotEqual(driver.gui_position(original), driver.gui_position(dict(original, **change)))


if __name__ == "__main__":
    unittest.main()

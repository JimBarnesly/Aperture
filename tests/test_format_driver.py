"""Regression tests for real-Kodi driver's observation and route barriers."""
import importlib.util
from pathlib import Path
import unittest
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

    def test_new_sequence_alone_is_not_a_gui_transition(self):
        original = {"window": 10502, "folder": "albums", "focus": 55, "list_item": "Album", "sequence": 1}
        self.assertEqual(driver.gui_position(original), driver.gui_position(dict(original, sequence=2)))
        for change in ({"folder": "tracks"}, {"window": 10000}, {"list_item": "Second album"}, {"focus": 56}):
            with self.subTest(change=change):
                self.assertNotEqual(driver.gui_position(original), driver.gui_position(dict(original, **change)))


if __name__ == "__main__":
    unittest.main()

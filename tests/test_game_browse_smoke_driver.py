"""Pure safety/navigation contracts, not a Kodi runtime acceptance claim."""

import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("game_browse_smoke_driver", ROOT / "tools/game_browse_smoke_driver.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def row(label, action="", system="", parent=False, folder=True):
    query = "action=" + action if action else ""
    if system:
        query += "&system=" + system
    return {"list_item": label, "item_path": "plugin://plugin.games.apeture/?" + query,
            "item_is_folder": folder, "item_is_parent": parent, "item_system": system,
            "item_game_count": "1", "game_playing": False, "window": 10821,
            "dialog": 9999, "focus": 50, "directory": "root"}


class FakeListDriver:
    def __init__(self, rows):
        self.rows, self.index, self.sequence = rows, 0, 0
        self.keys = []

    def state(self):
        return dict(self.rows[self.index], sequence=self.sequence, time=self.sequence * 0.2)

    def wait(self, description, predicate, after=0, timeout=30):
        for _ in range(40):
            self.sequence += 1
            state = self.state()
            if self.sequence > after and predicate(state):
                return state
        raise AssertionError("Fake wait failed: " + description)

    def key(self, key):
        before = self.sequence
        self.keys.append(key)
        if key != "Down":
            raise AssertionError("Enumeration tried an activation key")
        self.index = (self.index + 1) % len(self.rows)
        return before


class BrowseNavigationTests(unittest.TestCase):
    def test_system_return_uses_native_back_not_previous_window(self):
        source = (ROOT / "tools/game_browse_smoke_driver.py").read_text()
        self.assertIn('driver.key("BackSpace")', source)
        self.assertEqual(module.OK_DIALOG, 12002)

    def test_native_list_cycle_uses_down_only_and_exact_expected_systems(self):
        rows = [row("..", parent=True), row("Game Boy Advance", "system", "gba"),
                row("Nintendo Entertainment System", "system", "nes"),
                row("Configure ROM folder…", "settings"), row("Playback help", "help")]
        driver = FakeListDriver(rows)
        actual = module.list_rows(driver)
        self.assertEqual(len(actual), 5)
        self.assertEqual(driver.keys, ["Down"] * 5)
        expected = {"systems": [{"id": "gba", "label": "Game Boy Advance", "game_count": 1},
                                {"id": "nes", "label": "Nintendo Entertainment System", "game_count": 1}]}
        module.assert_root_rows(actual, expected)
        with self.assertRaises(AssertionError):
            module.assert_root_rows(actual + [row("Unknown", "system", "unknown")], expected)

    def test_only_exact_verified_system_folder_may_be_activated(self):
        system = {"id": "nes", "label": "Nintendo Entertainment System"}
        valid = row(system["label"], "system", "nes")
        module.require_system_activation(valid, system)
        for changes in ({"item_is_folder": False}, {"game_playing": True},
                        {"item_is_parent": True}, {"focus": 9401}, {"dialog": 10101},
                        {"item_path": "plugin://plugin.games.apeture/?action=play&system=nes"},
                        {"item_path": "plugin://plugin.games.apeture/?action=system&system=nes&action=play"},
                        {"item_path": "plugin://other/?action=system&system=nes"},
                        {"list_item": "SYNTHETIC QA - DO NOT PLAY"}):
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                module.require_system_activation(dict(valid, **changes), system)

    def test_game_rows_are_verified_without_activation_and_extras_fail(self):
        system = {"id": "nes", "games": [{"title": "SYNTHETIC QA - DO NOT PLAY"}]}
        game = row(system["games"][0]["title"], "play", "nes", folder=False)
        rows = [row("..", parent=True), game, row("Settings", "settings"), row("Help", "help")]
        module.assert_game_rows(rows, system)
        with self.assertRaises(AssertionError):
            module.assert_game_rows(rows + [row("Unsupported file.txt", "play", "nes", folder=False)], system)

    def test_missing_playback_observer_is_not_treated_as_false(self):
        with self.assertRaises(AssertionError):
            module.no_game({})
        with self.assertRaises(AssertionError):
            module.no_game({"game_playing": "false"})


class SettingsIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="apeture-kodi-smoke.")
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name)
        target = self.runtime / "fresh-zip"
        (target / "data/userdata").mkdir(parents=True)
        (target / "data/userdata/guisettings.xml").write_text("<settings/>")
        self.driver = types.SimpleNamespace(target=target, process=None)
        self.settings = target / "data/userdata/addon_data/plugin.games.apeture/settings.xml"

    def test_exact_original_bytes_and_other_settings_restored(self):
        original = b'<?xml version="1.0"?>\n<settings version="2"><!--keep--><setting id="other">123</setting><setting id="rom_root" default="true"></setting></settings>\n'
        self.settings.parent.mkdir(parents=True)
        self.settings.write_bytes(original)
        snapshot = module.SettingsSnapshot(self.driver, self.runtime)
        snapshot.set_root(self.runtime / "synthetic-game-browse")
        tree = ET.parse(self.settings)
        self.assertEqual(tree.findtext("./setting[@id='other']"), "123")
        self.assertEqual(tree.findtext("./setting[@id='rom_root']"), str(self.runtime / "synthetic-game-browse"))
        self.assertNotIn("default", tree.find("./setting[@id='rom_root']").attrib)
        snapshot.restore()
        self.assertEqual(self.settings.read_bytes(), original)
        self.assertTrue(snapshot.is_restored())

    def test_missing_file_and_new_directories_are_restored_to_absence(self):
        snapshot = module.SettingsSnapshot(self.driver, self.runtime)
        snapshot.set_root(self.runtime / "synthetic-game-browse")
        self.assertTrue(self.settings.is_file())
        snapshot.restore()
        self.assertFalse(self.settings.parent.parent.exists())
        self.assertTrue(snapshot.is_restored())

    def test_live_process_edits_and_nonfresh_target_are_rejected(self):
        snapshot = module.SettingsSnapshot(self.driver, self.runtime)
        self.driver.process = types.SimpleNamespace(poll=lambda: None)
        with self.assertRaises(AssertionError):
            snapshot.set_root("/never-written")
        with self.assertRaises(AssertionError):
            snapshot.restore()
        self.assertFalse(self.settings.exists())
        self.driver.process = None
        self.driver.target = self.runtime / "wrong-profile"
        with self.assertRaises(ValueError):
            module.SettingsSnapshot(self.driver, self.runtime)

    def test_existing_nonempty_root_and_symlinks_are_rejected(self):
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text('<settings><setting id="rom_root">/some-existing-root</setting></settings>')
        with self.assertRaises(ValueError):
            module.SettingsSnapshot(self.driver, self.runtime)

    def test_run_failure_still_stops_and_restores_exact_original_file(self):
        self.settings.parent.mkdir(parents=True)
        original = b'<settings version="2"><setting id="rom_root" default="true" /></settings>\n'
        self.settings.write_bytes(original)
        self.driver.checks = []
        self.driver.start = Mock(side_effect=RuntimeError("synthetic startup failure"))
        self.driver.stop = Mock()
        manifest = {"root": str(self.runtime / "synthetic-game-browse"), "expected": {}}
        with patch.object(module, "prepare", return_value=manifest), self.assertRaises(RuntimeError):
            module.run(self.driver, self.runtime)
        self.driver.stop.assert_called_once()
        self.assertEqual(self.settings.read_bytes(), original)
        self.settings.unlink()
        self.settings.symlink_to(self.driver.target / "data/userdata/guisettings.xml")
        with self.assertRaises(ValueError):
            module.SettingsSnapshot(self.driver, self.runtime)


class LogScopeTests(unittest.TestCase):
    def test_only_one_exact_scanerror_in_designated_session_is_allowed(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            (out / "logs").mkdir()
            paths = [out / ("logs/session-{}.log".format(index)) for index in (4, 5, 6)]
            for path in paths:
                path.write_text("normal log\n")
            paths[1].write_text("prefix " + module.EXPECTED_ERROR + "\n")
            driver = types.SimpleNamespace(out=out)
            expected = module.check_session_logs(driver, [4, 5, 6], 5)
            self.assertEqual(expected, [{"session": 5, "log": "logs/session-5.log", "marker": module.EXPECTED_ERROR, "count": 1}])
            paths[0].write_text(module.EXPECTED_ERROR)
            with self.assertRaises(AssertionError):
                module.check_session_logs(driver, [4, 5, 6], 5)
            paths[0].write_text("normal log\n")
            paths[1].write_text((module.EXPECTED_ERROR + "\n") * 2)
            with self.assertRaises(AssertionError):
                module.check_session_logs(driver, [4, 5, 6], 5)
            paths[1].write_text("Apeture: operation failed (RuntimeError)\n")
            with self.assertRaises(AssertionError):
                module.check_session_logs(driver, [4, 5, 6], 5)


if __name__ == "__main__":
    unittest.main()

"""Test-only fixture isolation/content assertions, never emulator acceptance."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("game_browse_smoke_fixture", ROOT / "tools/game_browse_smoke_fixture.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
sys.path.insert(0, str(ROOT / "addons/plugin.games.apeture/resources/lib"))
from apeture_library.scanner import scan_library  # noqa: E402


class GameBrowseFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="apeture-kodi-smoke.")
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name)
        (self.runtime / "system/system").mkdir(parents=True)
        (self.runtime / "data/userdata").mkdir(parents=True)
        self.manifest_path = self.runtime / "system/system/addon-manifest.xml"
        self.settings_path = self.runtime / "data/userdata/guisettings.xml"
        self.manifest_path.write_text("<addons><addon>skin.estuary</addon></addons>")
        self.settings_path.write_text('<settings version="2"/>')

    def test_prepare_matches_actual_scanner_and_excludes_unknown_empty_files(self):
        data = fixture.prepare(self.runtime)
        result = scan_library(data["root"])
        self.assertFalse(result.issues)
        self.assertEqual([library.system.id for library in result.libraries], ["gba", "nes"])
        self.assertEqual(sum(len(library.games) for library in result.libraries), 3)
        for library, expected in zip(result.libraries, data["expected"]["systems"]):
            self.assertEqual(library.system.name, expected["label"])
            self.assertEqual(len(library.games), expected["game_count"])
            self.assertEqual([game.title for game in library.games], [game["title"] for game in expected["games"]])
        self.assertFalse(Path(data["unavailable_root"]).exists())

    def test_payloads_are_short_explicit_non_rom_text_and_never_launch_contract(self):
        data = fixture.prepare(self.runtime)
        self.assertTrue(data["never_launch"])
        self.assertEqual(data["status"], "prepared_not_run")
        for system in data["expected"]["systems"]:
            for game in system["games"]:
                self.assertIn("SYNTHETIC QA - DO NOT PLAY", game["title"])
                payload = (Path(data["root"]) / game["relative_path"]).read_bytes()
                self.assertEqual(payload, fixture.PAYLOAD)
                self.assertLess(len(payload), 192)  # Too short for a GBA header.
                self.assertNotEqual(payload[:4], b"NES\x1a")
                self.assertIn(b"NOT A ROM", payload)
        self.assertTrue(any("NEVER select" in step for step in data["runtime_assertions"]))

    def test_prepare_leaves_system_profile_and_no_database_untouched(self):
        before = (self.manifest_path.read_bytes(), self.settings_path.read_bytes())
        data = fixture.prepare(self.runtime)
        self.assertEqual(before, (self.manifest_path.read_bytes(), self.settings_path.read_bytes()))
        self.assertFalse((self.runtime / "data/userdata/addon_data").exists())
        self.assertFalse((self.runtime / "data/userdata/Database").exists())
        self.assertEqual(json.loads((Path(data["root"]) / "expected.json").read_text()), data)
        self.assertEqual({path.name for path in self.runtime.iterdir()}, {"system", "data", fixture.DIRECTORY})

    def test_repeated_prepare_never_overwrites_existing_fixture(self):
        data = fixture.prepare(self.runtime)
        metadata = Path(data["root"]) / "expected.json"
        before = metadata.read_bytes()
        with self.assertRaises(ValueError):
            fixture.prepare(self.runtime)
        self.assertEqual(metadata.read_bytes(), before)

    def test_regular_folder_missing_markers_and_unavailable_existing_path_rejected(self):
        with tempfile.TemporaryDirectory() as ordinary:
            with self.assertRaises(ValueError):
                fixture.prepare(Path(ordinary))
        self.settings_path.unlink()
        with self.assertRaises(ValueError):
            fixture.prepare(self.runtime)
        self.assertFalse((self.runtime / fixture.DIRECTORY).exists())
        self.settings_path.write_text("<settings/>")
        (self.runtime / (fixture.DIRECTORY + "-unavailable")).mkdir()
        with self.assertRaises(ValueError):
            fixture.prepare(self.runtime)
        self.assertFalse((self.runtime / fixture.DIRECTORY).exists())

    def test_symlink_destination_or_profile_is_rejected(self):
        destination = self.runtime / fixture.DIRECTORY
        destination.symlink_to(self.runtime / "nonexistent", target_is_directory=True)
        with self.assertRaises(ValueError):
            fixture.prepare(self.runtime)
        destination.unlink()
        self.settings_path.unlink()
        self.settings_path.symlink_to(self.manifest_path)
        with self.assertRaises(ValueError):
            fixture.prepare(self.runtime)
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()

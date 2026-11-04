import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("format_fixture", ROOT / "tests/kodi_format_fixture.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class FixtureTest(unittest.TestCase):
    def test_range_requests(self):
        self.assertEqual(fixture.byte_range(None, 100), (0, 99, False))
        self.assertEqual(fixture.byte_range("bytes=10-19", 100), (10, 19, True))
        self.assertEqual(fixture.byte_range("bytes=10-", 100), (10, 99, True))
        self.assertEqual(fixture.byte_range("bytes=-10", 100), (90, 99, True))
        self.assertEqual(fixture.byte_range("bytes=10-199", 100), (10, 99, True))
        for value in ("bytes=101-", "bytes=19-10", "bytes=-0", "bytes=1-2,3-4", "items=0-1", "bytes=invalid"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                fixture.byte_range(value, 100)

    def test_original_wav_and_png(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tone.wav"
            fixture.write_wav(path, 220)
            with wave.open(str(path)) as stream:
                self.assertEqual(stream.getnchannels(), 1)
                self.assertEqual(stream.getsampwidth(), 2)
                self.assertEqual(stream.getnframes() / stream.getframerate(), 30)
        self.assertTrue(fixture.cover_png().startswith(b"\x89PNG\r\n\x1a\n"))

    def test_fixture_requires_sorting_and_encodes_real_path_edge_cases(self):
        library = fixture.fixture_library()
        self.assertNotEqual(library["albums"][0]["trackIds"], fixture.TRACK_IDS)
        ordered = sorted(library["tracks"], key=lambda t: (t["disc"], t["track"]))
        self.assertEqual([item["id"] for item in ordered], fixture.TRACK_IDS)
        self.assertIn(",", fixture.TRACK_IDS[0])
        self.assertIn("&", fixture.TRACK_IDS[0])

    def test_guarded_prepare_and_observer_syntax(self):
        with tempfile.TemporaryDirectory(prefix="aperture-kodi-smoke.") as directory:
            runtime = Path(directory)
            for suffix in ("home", "system/system", "system/addons", "data/userdata", "out"):
                (runtime / suffix).mkdir(parents=True, exist_ok=True)
            (runtime / "system/system/addon-manifest.xml").write_text("<addons/>")
            (runtime / "data/userdata/guisettings.xml").write_text('<settings version="2"/>')
            env = {"HOME":str(runtime / "home"), "KODI_HOME":str(runtime / "system"),
                   "KODI_DATA":str(runtime / "data"), "APERTURE_SMOKE_OUT":str(runtime / "out")}
            with patch.dict(os.environ, env):
                config = fixture.prepare(runtime, runtime / "out")
                self.assertEqual(config["expected_ids"], fixture.TRACK_IDS)
                self.assertEqual(config["album_title"], fixture.fixture_library()["albums"][0]["title"])
                self.assertIn('"focused_title":xbmc.getInfoLabel("ListItem.Title")', fixture.OBSERVER_SOURCE)
                self.assertTrue((runtime / "system/addons" / fixture.ADDON / "addon.py").is_file())
                self.assertFalse((runtime / "out/format-ready.json").exists())
                self.assertEqual(json.loads((runtime / "out/format-result.json").read_text())["status"], "not_run")
                ET.parse(runtime / "data/userdata/keymaps/format-ci.xml")
                compile((runtime / "system/addons" / fixture.OBSERVER / "service.py").read_text(), "service.py", "exec")
                with self.assertRaises(ValueError):
                    fixture.prepare(runtime, runtime / "out")

    def test_rejects_non_disposable_profile(self):
        with tempfile.TemporaryDirectory(prefix="ordinary-profile.") as directory:
            with self.assertRaises(ValueError):
                fixture.validated_runtime(Path(directory))


if __name__ == "__main__":
    unittest.main()

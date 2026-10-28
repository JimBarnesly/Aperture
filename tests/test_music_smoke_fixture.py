"""Synthetic fixture/setup tests; not native Kodi renderer/player tests."""
import importlib.util
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("music_smoke_fixture", ROOT / "tools/music_smoke_fixture.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class SyntheticFixtureTests(unittest.TestCase):
    def test_actual_flac_tags_hashes_and_ordered_multidisc_manifest(self):
        expected = fixture.verify()
        self.assertEqual(len(expected["albums"]), 7)
        self.assertEqual(sum(len(a["tracks"]) for a in expected["albums"]), 10)
        double = expected["albums"][3]
        self.assertEqual([(t["disc"], t["track"]) for t in double["tracks"]], [(1, 1), (1, 2), (2, 1), (2, 2)])
        files = [t["file"] for t in double["tracks"]]
        self.assertNotEqual(files, sorted(files))
        for album in expected["albums"]:
            for track in album["tracks"]:
                payload = (fixture.FIXTURES / track["file"]).read_bytes()
                self.assertEqual(payload[:4], b"fLaC")
                self.assertEqual(payload[4] & 127, 0)  # STREAMINFO is first.
                block = payload[8:42]
                packed = int.from_bytes(block[10:18], "big")
                rate, samples = packed >> 44, packed & ((1 << 36) - 1)
                self.assertEqual(rate, 11025)
                self.assertEqual(samples / rate, 20)
                self.assertIn("SYNTHETIC QA", fixture.flac_tags(fixture.FIXTURES / track["file"])["TITLE"])

    def test_prepare_only_targets_marked_disposable_system_and_profile(self):
        with tempfile.TemporaryDirectory(prefix="apeture-kodi-smoke.") as temp:
            runtime = Path(temp)
            (runtime / 'system/system').mkdir(parents=True)
            (runtime / 'system/addons').mkdir()
            (runtime / 'home').mkdir()
            (runtime / 'data/userdata').mkdir(parents=True)
            (runtime / 'system/system/addon-manifest.xml').write_text('<addons><addon>skin.estuary</addon></addons>')
            (runtime / 'data/userdata/guisettings.xml').write_text('<settings version="2"><setting id="services.webserver">false</setting></settings>')
            out = runtime / 'out'
            with patch.dict(os.environ, {'KODI_HOME': str(runtime / 'system'), 'KODI_DATA': str(runtime / 'data'), 'HOME': str(runtime / 'home')}):
                config = fixture.prepare(runtime, out)
                with self.assertRaises(ValueError): fixture.prepare(runtime, out)
            self.assertEqual(config['label'], 'SYNTHETIC QA')
            self.assertEqual(json.loads((runtime / '.apeture-music-smoke.json').read_text()), config)
            self.assertTrue((runtime / 'system/addons/script.apeture.music/default.py').is_file())
            self.assertTrue((runtime / 'system/addons/service.apeture.musicsmoke/service.py').is_file())
            settings = ET.parse(runtime / 'data/userdata/guisettings.xml')
            self.assertEqual(settings.findtext("./setting[@id='musiclibrary.downloadinfo']"), 'false')
            self.assertEqual(settings.findtext("./setting[@id='services.webserver']"), 'false')
            self.assertEqual(settings.findtext("./setting[@id='audiooutput.audiodevice']"), 'ALSA:default')
            alsa = (runtime / 'home/.asoundrc').read_text()
            self.assertIn('pcm.!default', alsa)
            self.assertIn('type null', alsa)
            self.assertIn('show on', alsa)
            self.assertIn('SYNTHETIC QA', alsa)
            self.assertIn('not audible output', (out / 'music-audio-sink.txt').read_text())
            self.assertFalse((runtime / 'data/userdata/Database').exists())  # No SQLite seeding.
            self.assertEqual(json.loads((out / 'music-result.json').read_text())['status'], 'not_run')

    def test_existing_alsa_configuration_is_never_replaced(self):
        with tempfile.TemporaryDirectory(prefix="apeture-kodi-smoke.") as temp:
            runtime = Path(temp)
            (runtime / 'system/system').mkdir(parents=True)
            (runtime / 'data/userdata').mkdir(parents=True)
            (runtime / 'home').mkdir()
            (runtime / 'system/system/addon-manifest.xml').write_text('<addons/>')
            (runtime / 'data/userdata/guisettings.xml').write_text('<settings/>')
            config = runtime / 'home/.asoundrc'
            config.write_text('existing configuration')
            with patch.dict(os.environ, {'KODI_HOME': str(runtime / 'system'),
                    'KODI_DATA': str(runtime / 'data'), 'HOME': str(runtime / 'home')}):
                with self.assertRaises(ValueError): fixture.prepare(runtime, runtime / 'out')
            self.assertEqual(config.read_text(), 'existing configuration')
            self.assertFalse((runtime / 'synthetic-music').exists())

    def test_regular_folder_and_mismatched_runtime_environment_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError): fixture.prepare(Path(temp), Path(temp) / 'out')
        with tempfile.TemporaryDirectory(prefix="apeture-kodi-smoke.") as temp:
            runtime = Path(temp)
            (runtime / 'system/system').mkdir(parents=True)
            (runtime / 'data/userdata').mkdir(parents=True)
            (runtime / 'system/system/addon-manifest.xml').write_text('<addons/>')
            (runtime / 'data/userdata/guisettings.xml').write_text('<settings/>')
            with patch.dict(os.environ, {'KODI_HOME': '/not-the-fixture'}):
                with self.assertRaises(ValueError): fixture.prepare(runtime, runtime / 'out')
            self.assertFalse((runtime / 'synthetic-music').exists())


if __name__ == '__main__': unittest.main()

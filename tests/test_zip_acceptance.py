"""Unit safeguards for the separate real-Kodi fresh-ZIP acceptance phase.

These tests validate the harness, not the live installer. Live acceptance is
reported only by tools/zip_smoke_driver.py in an isolated Kodi 21.3 runtime.
"""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('zip_smoke_fixture', ROOT / 'tools/zip_smoke_fixture.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
sys.modules.setdefault('zip_smoke_fixture', fixture)
spec = importlib.util.spec_from_file_location('zip_smoke_driver', ROOT / 'tools/zip_smoke_driver.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def make_packages(root):
    dist = root / 'dist'
    dist.mkdir()
    checksums = {}
    for addon in fixture.SUBJECTS:
        path = dist / f'{addon}-1.2.3.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr(addon + '/addon.xml', f'<addon id="{addon}" version="1.2.3"/>')
            archive.writestr(addon + '/resource.txt', 'known package bytes')
        checksums[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (dist / 'checksums.json').write_text(json.dumps(checksums))
    return dist, checksums


def change_zip(dist, checksums, mutate):
    filename = next(iter(checksums))
    path = dist / filename
    with zipfile.ZipFile(path, 'a') as archive:
        mutate(archive)
    checksums[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
    (dist / 'checksums.json').write_text(json.dumps(checksums))


class PackageTest(unittest.TestCase):
    def test_current_checksum_mapping_and_install_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist, _ = make_packages(Path(tmp))
            rows = fixture.packages(dist)
            self.assertEqual([row['addon'] for row in rows], list(fixture.SUBJECTS))
            self.assertEqual(rows[0]['addon'], 'plugin.audio.aperture.format')
            self.assertTrue(all(row['version'] == '1.2.3' for row in rows))

    def test_rejects_legacy_manifest_shape_and_extra_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist, checksums = make_packages(Path(tmp))
            for invalid in ([{'addon': 'skin.aperture'}], {**checksums, 'other.zip': 'a' * 64}):
                (dist / 'checksums.json').write_text(json.dumps(invalid))
                with self.assertRaises(ValueError):
                    fixture.packages(dist)

    def test_rejects_checksum_mismatch_and_zip_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist, checksums = make_packages(Path(tmp))
            path = dist / next(iter(checksums))
            original = path.read_bytes()
            path.write_bytes(original + b'corruption')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                fixture.packages(dist)
            path.unlink()
            elsewhere = Path(tmp) / 'original.zip'
            elsewhere.write_bytes(original)
            path.symlink_to(elsewhere)
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                fixture.packages(dist)

    def test_rejects_traversal_member_and_member_symlink(self):
        for kind in ('traversal', 'symlink', 'wrong-root'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                dist, checksums = make_packages(Path(tmp))
                def mutate(archive):
                    if kind == 'traversal':
                        archive.writestr(fixture.SUBJECTS[0] + '/../escape', 'bad')
                    elif kind == 'wrong-root':
                        archive.writestr('other/addon.xml', 'bad')
                    else:
                        entry = zipfile.ZipInfo(fixture.SUBJECTS[0] + '/link')
                        entry.external_attr = 0o120777 << 16
                        archive.writestr(entry, 'resource.txt')
                change_zip(dist, checksums, mutate)
                with self.assertRaises(ValueError):
                    fixture.packages(dist)

    def test_rejects_unsafe_manifest_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist, checksums = make_packages(Path(tmp))
            digest = checksums.pop(next(iter(checksums)))
            for bad in ('../file.zip', '/file.zip', 'path\\file.zip'):
                (dist / 'checksums.json').write_text(json.dumps({**checksums, bad: digest}))
                with self.assertRaisesRegex(ValueError, 'Unsafe package filename'):
                    fixture.packages(dist)

    def test_verifies_all_installed_bytes_and_rejects_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist, _ = make_packages(root)
            rows = fixture.packages(dist)
            data = root / 'data'
            for row in rows:
                with zipfile.ZipFile(dist / row['file']) as archive:
                    archive.extractall(data / 'addons')
            verified = fixture.verify_installed(dist, data, rows)
            self.assertEqual([row['files_verified'] for row in verified], [2, 2])
            target = data / 'addons' / fixture.SUBJECTS[0] / 'resource.txt'
            target.write_text('changed')
            with self.assertRaisesRegex(AssertionError, 'installed bytes differ'):
                fixture.verify_installed(dist, data, rows)


class FreshFixtureTest(unittest.TestCase):
    def test_fresh_subjects_absent_and_native_entry_hotkeys(self):
        with tempfile.TemporaryDirectory(prefix='aperture-kodi-smoke.') as tmp:
            runtime = Path(tmp)
            root = runtime / 'repo'
            root.mkdir()
            make_packages(root)
            (root / 'tools').mkdir()
            shutil.copy2(ROOT / 'tools/zip_smoke_observer.py', root / 'tools/zip_smoke_observer.py')
            base = runtime / 'system'
            (base / 'system').mkdir(parents=True)
            subjects = (*fixture.SUBJECTS, 'service.aperture.cismoke', 'service.aperture.formatqa')
            for addon in (*subjects, 'skin.estuary'):
                (base / 'addons' / addon).mkdir(parents=True)
            (base / 'system/addon-manifest.xml').write_text('<addons>' + ''.join(f'<addon>{x}</addon>' for x in (*subjects, 'skin.estuary')) + '</addons>')
            # Even the old runtime's profile must not be copied into the new one.
            (runtime / 'data/userdata/Database').mkdir(parents=True)
            (runtime / 'data/userdata/Database/Addons33.db').write_text('do not copy')
            target, rows = fixture.prepare(root, runtime, base, runtime / 'out')
            self.assertEqual(len(rows), 2)
            self.assertFalse((target / 'data/addons').exists())
            self.assertFalse((target / 'data/userdata/Database').exists())
            for addon in subjects:
                self.assertFalse((target / 'system/addons' / addon).exists())
            manifest = ET.parse(target / 'system/system/addon-manifest.xml')
            self.assertEqual({node.text for node in manifest.getroot()}, {'skin.estuary', fixture.OBSERVER})
            settings = {node.get('id'): node.text for node in ET.parse(target / 'data/userdata/guisettings.xml').getroot()}
            self.assertEqual(settings['addons.unknownsources'], 'false')
            self.assertEqual(settings['lookandfeel.skin'], 'skin.estuary')
            self.assertEqual(settings['audiooutput.audiodevice'], 'PULSE:aperture_format_qa')
            self.assertTrue(all(value == 'false' for key, value in settings.items() if key and key.startswith('services.')))
            keymap = ET.parse(target / 'data/userdata/keymaps/zip-smoke.xml')
            self.assertEqual({node.tag: node.text for node in keymap.findall('./global/keyboard/*')}, {
                'm': 'ActivateWindow(10040)', 'i': 'ActivateWindow(10032,lookandfeel.skin)',
                'n': 'ActivateWindow(10016,addons.unknownsources)', 'h': 'ActivateWindow(10000)'})
            with self.assertRaisesRegex(ValueError, 'existing ZIP-test profile'):
                fixture.prepare(root, runtime, base, runtime / 'out')

    def test_rejects_non_disposable_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'disposable CI runtime'):
                fixture.prepare(ROOT, tmp, Path(tmp) / 'system', Path(tmp) / 'out')


class DriverSafetyTest(unittest.TestCase):
    def test_label_match_is_exact_except_radio_suffix(self):
        for actual in ('Unknown sources', 'Unknown sources ( )', 'Unknown sources (*)', ' Unknown sources (x) '):
            self.assertTrue(driver.label_matches(actual, 'Unknown sources'))
        for actual in ('Unknown sources extra', 'Unknown sources (*) extra', 'Sources'):
            self.assertFalse(driver.label_matches(actual, 'Unknown sources'))

    def test_setting_reads_must_start_after_action_and_be_fresh(self):
        with patch.object(driver.time, 'time', return_value=100):
            valid = {'unknown_sources': False, 'unknown_sources_read_started': 98,
                     'unknown_sources_read_completed': 99}
            self.assertTrue(driver.setting_matches(valid, False, after=97))
            self.assertFalse(driver.setting_matches(valid, False, after=98))
            self.assertFalse(driver.setting_matches(valid, True))
            self.assertFalse(driver.setting_matches({**valid, 'unknown_sources_read_completed': 96}, False))

    def test_direct_child_and_no_legacy_game_music_or_function_keys(self):
        source = (ROOT / 'tools/zip_smoke_driver.py').read_text()
        self.assertIn('self.kodi_pid = self.process.pid', source)
        self.assertIn('self.focus_home(103)', source)
        self.assertIn("'plugin://plugin.audio.aperture.format/'", source)
        for forbidden in ('gdb', 'debugger_commands', 'ctrl+F', 'game_browse', 'plugin.games', 'script.aperture.music'):
            self.assertNotIn(forbidden, source)

    def test_observer_has_no_window_proxies_or_mutating_rpc(self):
        source = (ROOT / 'tools/zip_smoke_observer.py').read_text()
        tree = ast.parse(source)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        for call in calls:
            if isinstance(call.func, ast.Attribute):
                self.assertNotIn(call.func.attr, ('Window', 'getControl', 'getFocusId', 'setSetting', 'executebuiltin'))
        self.assertIn("System.CurrentControlId", source)
        self.assertIn("Settings.GetSettingValue", source)
        self.assertNotIn('Settings.SetSettingValue', source)

    def test_modal_setting_read_cannot_block_gui_observation(self):
        entered, release = threading.Event(), threading.Event()
        def rpc(_):
            entered.set()
            release.wait(2)
            return json.dumps({'result': {'value': False}})
        fake_xbmc = SimpleNamespace(executeJSONRPC=rpc, getInfoLabel=lambda name: '103' if name == 'System.CurrentControlId' else '',
                                    getCondVisibility=lambda _: False, getSkinDir=lambda: 'skin.estuary')
        fake_gui = SimpleNamespace(getCurrentWindowId=lambda: 10016, getCurrentWindowDialogId=lambda: 10100,
                                  getScreenWidth=lambda: 1920, getScreenHeight=lambda: 1080)
        modules = {'xbmc': fake_xbmc, 'xbmcgui': fake_gui, 'xbmcaddon': SimpleNamespace()}
        spec = importlib.util.spec_from_file_location('zip_observer_test', ROOT / 'tools/zip_smoke_observer.py')
        observer = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(observer)
        monitor = SimpleNamespace(abortRequested=lambda: False, waitForAbort=lambda _: True)
        settings = observer.SettingsReader(monitor)
        settings.thread.start()
        try:
            self.assertTrue(entered.wait(1))
            value = observer.observe(1, settings)
            self.assertEqual(value['dialog'], 10100)
            self.assertEqual(value['focus'], 103)
            self.assertIsNone(value['unknown_sources'])
        finally:
            release.set()
            settings.thread.join(2)
        self.assertFalse(settings.thread.is_alive())
        self.assertIs(settings.snapshot()['unknown_sources'], False)


if __name__ == '__main__':
    unittest.main()

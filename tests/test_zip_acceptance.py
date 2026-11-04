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
from unittest.mock import Mock, patch
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
EXPECTED_SUBJECTS = ('plugin.audio.aperture.format', 'plugin.video.aperture.movies', 'skin.aperture')


def make_packages(root):
    dist = root / 'dist'
    dist.mkdir()
    checksums = {}
    for addon in EXPECTED_SUBJECTS:
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
            self.assertEqual(fixture.SUBJECTS, EXPECTED_SUBJECTS)
            self.assertEqual([row['addon'] for row in rows], list(EXPECTED_SUBJECTS))
            self.assertTrue(all(row['version'] == '1.2.3' for row in rows))

    def test_rejects_legacy_manifest_shape_and_extra_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist, checksums = make_packages(Path(tmp))
            for invalid in ([{'addon': 'skin.aperture'}], {**checksums, 'other.zip': 'a' * 64}):
                (dist / 'checksums.json').write_text(json.dumps(invalid))
                with self.assertRaises(ValueError):
                    fixture.packages(dist)

    def test_rejects_old_two_package_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist, checksums = make_packages(Path(tmp))
            checksums.pop('plugin.video.aperture.movies-1.2.3.zip')
            (dist / 'checksums.json').write_text(json.dumps(checksums))
            with self.assertRaisesRegex(ValueError, 'exact built Format, Movies and skin'):
                fixture.packages(dist)

    def test_rejects_substituted_subject_and_duplicate_subject_version(self):
        for replacement, version in (('plugin.games.aperture', '1.2.3'),
                                     ('plugin.unexpected', '1.2.3'),
                                     ('plugin.audio.aperture.format', '0.1.0')):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as tmp:
                dist, checksums = make_packages(Path(tmp))
                old = 'plugin.video.aperture.movies-1.2.3.zip'
                checksums.pop(old)
                (dist / old).unlink()
                path = dist / f'{replacement}-{version}.zip'
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr(replacement + '/addon.xml',
                                     f'<addon id="{replacement}" version="{version}"/>')
                checksums[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
                (dist / 'checksums.json').write_text(json.dumps(checksums))
                with self.assertRaisesRegex(ValueError, 'Unexpected|Duplicated'):
                    fixture.packages(dist)

    def test_rejects_unlisted_stale_zip_and_duplicate_checksum_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist, checksums = make_packages(Path(tmp))
            stale = dist / 'plugin.video.aperture.movies-0.0.1.zip'
            stale.write_bytes(b'stale package')
            with self.assertRaisesRegex(ValueError, 'Unexpected or stale ZIP'):
                fixture.packages(dist)
            stale.unlink()
            filename, digest = next(iter(checksums.items()))
            payload = json.dumps(checksums)[:-1] + ',' + json.dumps(filename) + ':' + json.dumps(digest) + '}'
            (dist / 'checksums.json').write_text(payload)
            with self.assertRaisesRegex(ValueError, 'Duplicated package checksum entry'):
                fixture.packages(dist)

    def test_rejects_filename_version_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist, checksums = make_packages(Path(tmp))
            old = 'plugin.video.aperture.movies-1.2.3.zip'
            renamed = 'plugin.video.aperture.movies-0.0.1.zip'
            (dist / old).rename(dist / renamed)
            checksums[renamed] = checksums.pop(old)
            (dist / 'checksums.json').write_text(json.dumps(checksums))
            with self.assertRaisesRegex(ValueError, 'metadata differs'):
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
            self.assertEqual([row['files_verified'] for row in verified], [2, 2, 2])
            self.assertEqual([row['addon'] for row in verified], list(EXPECTED_SUBJECTS))
            target = data / 'addons' / 'plugin.video.aperture.movies' / 'resource.txt'
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
            self.assertEqual([row['addon'] for row in rows], list(EXPECTED_SUBJECTS))
            self.assertFalse((target / 'data/addons').exists())
            self.assertFalse((target / 'data/userdata/Database').exists())
            for addon in subjects:
                self.assertFalse((target / 'system/addons' / addon).exists())
            self.assertEqual({path.name for path in (target / 'packages').iterdir()},
                             {row['file'] for row in rows})
            report = json.loads((runtime / 'out/fixture.json').read_text())
            self.assertEqual(report['subjects'], list(EXPECTED_SUBJECTS))
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
    def test_home_navigation_waits_for_reveal_and_routes_from_settled_focus(self):
        home = ET.parse(ROOT / 'skin/xml/Home.xml').getroot()
        reveal_ms = max(int(node.get('time', '0')) + int(node.get('delay', '0'))
                        for node in home.iter('animation') if node.text == 'WindowOpen')
        with tempfile.TemporaryDirectory() as tmp:
            subject = driver.Driver.__new__(driver.Driver)
            subject.target = Path(tmp)
            installed = subject.target / 'data/addons/skin.aperture/xml'
            installed.mkdir(parents=True)
            shutil.copy2(ROOT / 'skin/xml/Home.xml', installed / 'Home.xml')
            now = [0]
            # A transition can briefly report the destination focus before
            # restoring the previous menu focus that actually receives the next key.
            state = {'skin': 'skin.aperture', 'window': 10000, 'dialog': 9999,
                     'focus': 103, 'sequence': 10}
            events = []
            def sleep(seconds):
                now[0] += seconds
                events.append('reveal')
            def settle():
                self.assertGreater(now[0] * 1000, reveal_ms)
                events.append('settled')
                state['focus'] = 102
                return dict(state)
            def key(value):
                events.append(value)
                self.assertEqual(value, 'Up')
                self.assertEqual(state['focus'], 102)
                before = state['sequence']
                if now[0] * 1000 > reveal_ms:
                    state.update(focus=103, sequence=before + 1)
                return before
            def wait(description, predicate, after=0, **_):
                self.assertTrue(predicate(state), description)
                self.assertGreater(state['sequence'], after)
                return dict(state)
            subject.state = lambda: dict(state)
            subject.wait = Mock(side_effect=wait)
            subject.key = Mock(side_effect=key)
            subject.settle_focus = Mock(side_effect=settle)
            with patch.object(driver.time, 'sleep', side_effect=sleep):
                subject.focus_home(103)
            self.assertEqual(events, ['reveal', 'settled', 'Up'])
            self.assertEqual(state['focus'], 103)
            self.assertEqual(subject.wait.call_args.kwargs['after'], 10)

    def test_home_navigation_still_rejects_an_unconsumed_arrow(self):
        with tempfile.TemporaryDirectory() as tmp:
            subject = driver.Driver.__new__(driver.Driver)
            subject.target = Path(tmp)
            installed = subject.target / 'data/addons/skin.aperture/xml'
            installed.mkdir(parents=True)
            shutil.copy2(ROOT / 'skin/xml/Home.xml', installed / 'Home.xml')
            state = {'skin': 'skin.aperture', 'window': 10000, 'dialog': 9999, 'focus': 102}
            def wait(description, predicate, **_):
                if not predicate(state):
                    raise AssertionError(description)
                return dict(state)
            subject.wait = Mock(side_effect=wait)
            subject.key = Mock(return_value=1)
            subject.settle_focus = Mock(return_value=state)
            with patch.object(driver.time, 'sleep'), self.assertRaisesRegex(AssertionError, 'installed Home focus 103'):
                subject.focus_home(103)
            subject.key.assert_called_once_with('Up')

    def test_home_navigation_rejects_a_modal_during_settle(self):
        with tempfile.TemporaryDirectory() as tmp:
            subject = driver.Driver.__new__(driver.Driver)
            subject.target = Path(tmp)
            installed = subject.target / 'data/addons/skin.aperture/xml'
            installed.mkdir(parents=True)
            shutil.copy2(ROOT / 'skin/xml/Home.xml', installed / 'Home.xml')
            subject.wait = Mock()
            subject.key = Mock()
            subject.settle_focus = Mock(return_value={
                'skin': 'skin.aperture', 'window': 10000, 'dialog': 10100, 'focus': 102})
            with patch.object(driver.time, 'sleep'), self.assertRaisesRegex(AssertionError, 'Home changed'):
                subject.focus_home(103)
            subject.key.assert_not_called()

    def test_observer_subjects_match_complete_build_set(self):
        tree = ast.parse((ROOT / 'tools/zip_smoke_observer.py').read_text())
        subjects = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                        and any(isinstance(target, ast.Name) and target.id == 'SUBJECTS' for target in node.targets))
        self.assertEqual(ast.literal_eval(subjects), EXPECTED_SUBJECTS)
        self.assertEqual(driver.SUBJECTS, EXPECTED_SUBJECTS)

    def test_all_installed_subjects_need_matching_version_path_and_enabled(self):
        data = Path('/tmp/aperture-test/data')
        rows = [{'addon': addon, 'version': '1.2.3'} for addon in EXPECTED_SUBJECTS]
        installed = {row['addon']: {'version': row['version'], 'enabled': True,
                     'path': str(data / 'addons' / row['addon'])} for row in rows}
        self.assertTrue(driver.installed_matches({'installed': installed}, rows, data))
        for addon in EXPECTED_SUBJECTS:
            for change in ({'version': '0.0.1'}, {'enabled': False}, {'path': '/system/addons/' + addon}, {'path': ''}):
                with self.subTest(addon=addon, change=change):
                    changed = {**installed, addon: {**installed[addon], **change}}
                    self.assertFalse(driver.installed_matches({'installed': changed}, rows, data))
            self.assertFalse(driver.installed_matches({'installed': {k: v for k, v in installed.items() if k != addon}}, rows, data))

    def test_movies_guidance_rejects_error_or_unrelated_dialog(self):
        guidance = {'dialog': 12002, 'dialog_text': 'Movies Add your existing movie folder in Kodi'}
        self.assertTrue(driver.movies_guidance(guidance))
        self.assertFalse(driver.movies_guidance({**guidance, 'dialog': 10100}))
        self.assertFalse(driver.movies_guidance({**guidance, 'dialog_text': 'Movies Could not read the movie source.'}))
        self.assertFalse(driver.movies_guidance({}))

    def test_music_runs_direct_open_controller_back_and_reopen(self):
        subject = driver.Driver.__new__(driver.Driver)
        subject.focus_home = Mock()
        subject.key = Mock(return_value=42)
        subject.wait = Mock()
        subject.capture = Mock()
        subject.settle_focus = Mock()
        subject.record = Mock()
        subject.check_music()
        self.assertEqual([call.args[0] for call in subject.focus_home.call_args_list], [103, 103])
        self.assertEqual([call.args[0] for call in subject.key.call_args_list],
                         ['Return', 'BackSpace', 'Return', 'BackSpace'])
        self.assertEqual(subject.settle_focus.call_count, 2)
        predicates = [call.args[1] for call in subject.wait.call_args_list]
        for root, home in (predicates[:2], predicates[2:]):
            valid = {'window': 10502, 'dialog': 9999, 'folder': 'plugin://plugin.audio.aperture.format/'}
            self.assertTrue(root(valid))
            for folder in ('library://music/', 'plugin://plugin.audio.aperture.format/?action=albums',
                           'plugin://plugin.audio.aperture.format.other/', ''):
                self.assertFalse(root({**valid, 'folder': folder}))
            self.assertFalse(root({**valid, 'dialog': 12002}))
            self.assertFalse(root({**valid, 'window': 10000}))
            self.assertTrue(home({'window': 10000, 'dialog': 9999, 'focus': 103}))
            self.assertFalse(home({'window': 10000, 'dialog': 12002, 'focus': 103}))
            self.assertFalse(home({'window': 10000, 'dialog': 9999, 'focus': 102}))
        self.assertTrue(all(call.kwargs['after'] == 42 for call in subject.wait.call_args_list))
        self.assertEqual([call.kwargs['attempt'] for call in subject.record.call_args_list], [0, 1])

    def test_movies_runs_native_open_dismiss_back_and_reopen(self):
        subject = driver.Driver.__new__(driver.Driver)
        subject.focus_home = Mock()
        subject.key = Mock(return_value=42)
        subject.wait = Mock()
        subject.capture = Mock()
        subject.record = Mock()
        subject.check_movies()
        self.assertEqual([call.args[0] for call in subject.focus_home.call_args_list], [100, 100])
        self.assertEqual([call.args[0] for call in subject.key.call_args_list],
                         ['Return', 'Return', 'BackSpace', 'Return', 'BackSpace', 'BackSpace'])
        predicates = [call.args[1] for call in subject.wait.call_args_list]
        for guidance, empty, home in (predicates[:3], predicates[3:]):
            self.assertIs(guidance, driver.movies_guidance)
            valid = {'window': 10025, 'dialog': 9999, 'folder': 'plugin://plugin.video.aperture.movies/'}
            self.assertTrue(empty(valid))
            self.assertFalse(empty({**valid, 'folder': 'sources://video/'}))
            self.assertFalse(empty({**valid, 'dialog': 12002}))
            self.assertTrue(home({'window': 10000, 'dialog': 9999, 'focus': 100}))
            self.assertFalse(home({'window': 10000, 'dialog': 12002, 'focus': 100}))
        self.assertTrue(all(call.kwargs['after'] == 42 for call in subject.wait.call_args_list))

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

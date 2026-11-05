"""Fail-closed unit coverage for the diagnostic's acceptance evidence."""
import importlib.util
from pathlib import Path
import tempfile
import json
import os
import subprocess
from unittest.mock import patch
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('labwc_relaunch_driver', ROOT / 'tools/labwc_relaunch_driver.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DiagnosticTests(unittest.TestCase):
    def mapping(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'menu.xml'
            path.write_text('<window><controls>' + content + '</controls></window>')
            return module.exit_mapping(path)

    def test_exact_quit_item(self):
        self.assertEqual(self.mapping('<control id="9000"><content><item><label>$LOCALIZE[13012]</label><onclick>Quit()</onclick></item></content></control>'), 9000)

    def test_powerdown_is_rejected(self):
        with self.assertRaises(module.DiagnosticFailure):
            self.mapping('<control id="9000"><content><item><label>$LOCALIZE[13012]</label><onclick>Powerdown()</onclick></item></content></control>')

    def test_multiple_actions_rejected(self):
        with self.assertRaises(module.DiagnosticFailure):
            self.mapping('<control id="9000"><content><item><label>$LOCALIZE[13012]</label><onclick>Quit()</onclick><onclick>Reset()</onclick></item></content></control>')

    def test_duplicate_exit_rejected(self):
        item = '<item><label>$LOCALIZE[13012]</label><onclick>Quit()</onclick></item>'
        with self.assertRaises(module.DiagnosticFailure):
            self.mapping('<control id="9000"><content>' + item * 2 + '</content></control>')

    def test_stale_or_wrong_home_rejected(self):
        state = dict(pid=99, skin='skin.estuary', window=10000, dialog=9999, home_visible=True, width=1920, height=1080)
        self.assertTrue(module.home_state(state, 'skin.estuary', 99))
        for key, value in [('pid', 98), ('skin', 'skin.aperture'), ('window', 10004), ('dialog', 10111), ('width', 1280), ('home_visible', False)]:
            self.assertFalse(module.home_state(dict(state, **{key:value}), 'skin.estuary', 99))

    def test_black_frame_never_passes_even_with_text(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'black.png'
            Image.new('RGB', (1920,1080)).save(path)
            result = module.pixel_evidence(path, 'Movies Music Games Settings')
            self.assertFalse(result['home_pixels'])
            self.assertTrue(result['black_frame'])

    def test_noise_without_home_text_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'noise.png'
            Image.effect_noise((1920,1080), 80).convert('RGB').save(path)
            self.assertFalse(module.pixel_evidence(path, 'DEBUG FPS CPU')['home_pixels'])
            self.assertTrue(module.pixel_evidence(path, 'Movies Music Games')['home_pixels'])

    def test_no_mutating_observer_calls(self):
        source = (ROOT / 'tools/labwc_relaunch_observer.py').read_text()
        for forbidden in ('executebuiltin', 'executeJSONRPC', 'setProperty', 'setSetting', 'activateWindow', 'Player(', 'getControl('):
            self.assertNotIn(forbidden, source)

    def test_native_exit_has_no_signal_fallback(self):
        import inspect
        source = inspect.getsource(module.Driver.exit_native)
        for forbidden in ('terminate(', '.kill(', 'os.kill', 'Quit()', 'executeJSONRPC'):
            # Quit() is recorded evidence, never executed by this driver.
            if forbidden == 'Quit()':
                continue
            self.assertNotIn(forbidden, source)
        self.assertIn("self.key('Return')", source)
        self.assertIn('child.wait(', source)


class SourceProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        self.out = Path(self.temp.name) / 'artifacts'
        self.root.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'diagnostic@example.invalid')
        self.git('config', 'user.name', 'Diagnostic test')
        (self.root / 'tracked.txt').write_text('clean source')
        self.git('add', 'tracked.txt')
        self.git('commit', '-qm', 'fixture')
        self.commit = self.git('rev-parse', 'HEAD')
        source = importlib.util.spec_from_file_location('labwc_source_provenance', ROOT / 'tools/labwc_source_provenance.py')
        self.provenance = importlib.util.module_from_spec(source)
        source.loader.exec_module(self.provenance)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True).strip()

    def test_actual_checkout_overrides_github_merge_sha(self):
        with patch.dict(os.environ, GITHUB_SHA='a' * 40):
            evidence = self.provenance.record_source(self.root, self.out, self.commit)
        self.assertEqual((self.out / 'commit.txt').read_text().strip(), self.commit)
        self.assertEqual((self.out / 'tree.txt').read_text().strip(), self.git('rev-parse', 'HEAD^{tree}'))
        self.assertEqual(evidence['github_event_sha'], 'a' * 40)
        self.assertEqual(evidence['expected_commit'], self.commit)
        self.assertTrue(evidence['tracked_worktree_clean'])

    def test_expected_commit_mismatch_rejected_and_actual_preserved(self):
        with self.assertRaisesRegex(ValueError, 'differs from expected'):
            self.provenance.record_source(self.root, self.out, 'b' * 40)
        self.assertEqual((self.out / 'commit.txt').read_text().strip(), self.commit)

    def test_modified_tracked_source_rejected(self):
        (self.root / 'tracked.txt').write_text('changed source')
        with self.assertRaisesRegex(ValueError, 'Tracked source differs'):
            self.provenance.record_source(self.root, self.out, self.commit)

    def test_cli_mismatch_writes_harness_failure_before_runtime(self):
        result = subprocess.run(['python3', str(ROOT / 'tools/labwc_source_provenance.py'), str(self.root), str(self.out)],
            env=dict(os.environ, APERTURE_EXPECTED_COMMIT='b' * 40), capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        evidence = json.loads((self.out / 'result.json').read_text())
        self.assertEqual(evidence['status'], 'harness_failure')
        self.assertEqual(evidence['stage'], 'source_provenance')

    def test_workflow_uses_custom_expected_commit_and_checks_before_gui(self):
        workflow = (ROOT / '.github/workflows/labwc-relaunch.yml').read_text()
        self.assertNotIn('GITHUB_SHA:', workflow)
        self.assertEqual(workflow.count('APERTURE_EXPECTED_COMMIT:'), 2)
        shell = (ROOT / 'tools/ci_labwc_relaunch.sh').read_text()
        self.assertNotIn('GITHUB_SHA', shell)
        self.assertLess(shell.index('labwc_source_provenance.py'), shell.index('export APERTURE_WAYLAND_ROOT'))


if __name__ == '__main__':
    unittest.main()

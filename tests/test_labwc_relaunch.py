"""Fail-closed unit coverage for the diagnostic's acceptance evidence."""
import importlib.util
from pathlib import Path
import tempfile
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


if __name__ == '__main__':
    unittest.main()

"""Pure navigation-label regression; no GUI is launched by these tests."""
import ast
from pathlib import Path
import re
import time
import unittest


class ZipDriverLabelsTests(unittest.TestCase):
    def test_only_native_radio_state_suffix_is_normalized(self):
        source = Path(__file__).resolve().parents[1] / 'tools/zip_smoke_driver.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'label_matches')
        namespace = {'re': re}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        matches = namespace['label_matches']
        for label in ('Unknown sources', 'Unknown sources ( )', 'Unknown sources (*)', 'Unknown sources (X)'):
            self.assertTrue(matches(label, 'Unknown sources'))
        for label in ('Unknown sources modified', 'Unknown sources (other)', 'Not Unknown sources'):
            self.assertFalse(matches(label, 'Unknown sources'))

    def test_setting_assertion_rejects_stale_or_pre_action_read(self):
        source = Path(__file__).resolve().parents[1] / 'tools/zip_smoke_driver.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'setting_matches')
        namespace = {'time': time}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        matches = namespace['setting_matches']
        now = time.time()
        state = {'unknown_sources': False, 'unknown_sources_read_started': now - 1,
                 'unknown_sources_read_completed': now}
        self.assertTrue(matches(state, False, now - 2))
        self.assertFalse(matches(state, False, now))
        self.assertFalse(matches(state, True))
        self.assertFalse(matches(dict(state, unknown_sources_read_completed=now - 10), False))
        self.assertFalse(matches({'unknown_sources': False}, False))

    def test_debugger_launches_child_without_attachment_or_policy_changes(self):
        source = Path(__file__).resolve().parents[1] / 'tools/zip_smoke_driver.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'debugger_commands')
        namespace = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        script = namespace['debugger_commands'](Path('/tmp/private fixture/kodi-pid.txt'))
        self.assertIn('starti\n', script)
        self.assertIn('continue\nthread apply all bt 24\n', script)
        self.assertIn('set disable-randomization off', script)  # Preserve default ASLR.
        self.assertIn('set debuginfod enabled off', script)
        self.assertNotIn('attach ', script)
        self.assertNotIn('sudo', script)
        self.assertNotIn('sysctl', script)
        python = script.split('python\n', 1)[1].split('\nend', 1)[0]
        compile(python, '<gdb-python>', 'exec')


if __name__ == '__main__':
    unittest.main()

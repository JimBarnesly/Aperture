"""Pure navigation-label regression; no GUI is launched by these tests."""
import ast
from pathlib import Path
import re
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


if __name__ == '__main__':
    unittest.main()

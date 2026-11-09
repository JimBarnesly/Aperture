"""Exercise the actual smoke driver's log gate without starting Kodi."""
import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class KodiFontLogGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / 'tools/ci_kodi_smoke.sh').read_text()
        # Parse the embedded driver, then execute only its log-check statements.
        # This tests the real predicate and failure, not a duplicated matcher.
        blocks = re.findall(r"<<'PY'\n(.*?)\nPY", source, re.S)
        drivers = [ast.parse(block) for block in blocks if 'fatal_markers=' in block]
        assert len(drivers) == 1, 'Expected one native smoke log gate'
        statements = []
        for node in ast.walk(drivers[0]):
            if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id in ('fatal_markers', 'errors')
                    for target in node.targets):
                statements.append(node)
            elif isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == 'errors':
                statements.append(node)
        assert len(statements) == 3, 'Expected markers, filtering and failure assertion'
        module = ast.Module(body=sorted(statements, key=lambda node: node.lineno), type_ignores=[])
        cls.gate = compile(module, str(ROOT / 'tools/ci_kodi_smoke.sh'), 'exec')

    def check_log(self, text):
        scope = {'log': text}
        exec(self.gate, scope)
        return scope['errors']

    def test_actual_omega_font_errors_fail(self):
        messages = (
            "GUIFontManager::LoadTTF: Couldn't load font name: font13(notosans-regular.ttf), trying arial.ttf",
            "GUIFontManager::LoadTTF: Couldn't load font name:font13 file:/fixture/media/Fonts/arial.ttf",
            "GUIFontManager::ReloadTTFFonts: Couldn't re-load font file: '/fixture/fonts/NotoSans-Regular.ttf'",
        )
        for message in messages:
            for variant in (message, message.upper()):
                with self.subTest(message=variant):
                    with self.assertRaises(AssertionError) as raised:
                        self.check_log('info: normal startup\nerror: ' + variant + '\ninfo: still running')
                    self.assertIn(variant, str(raised.exception))

    def test_existing_fatal_markers_still_fail(self):
        for message in ('Error loading skin', 'failed to load skin',
                        'EXCEPTION Thrown (PythonToCppException)', 'unable to load font'):
            with self.subTest(message=message), self.assertRaises(AssertionError):
                self.check_log(message)

    def test_successful_loading_and_reload_do_not_fail(self):
        self.assertEqual(self.check_log("""info: Loading skin file: Home.xml
info: Loading <fontset> with name 'Default' from '/fixture/xml/Font.xml'
debug: GUIFontManager::ReloadTTFFonts
info: Skin loaded
"""), [])
        self.assertEqual(self.check_log(''), [])


if __name__ == '__main__':
    unittest.main()

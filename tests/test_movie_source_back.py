"""Replay Kodi 21.3 window-history semantics at the real route/XML seam.

AddToWindowHistory truncates at an existing ID; `return` only sets the media
start directory. This models the retained native run, not a Python stack push.
"""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlsplit
import test_movie_plugin as plugin_tests

ROOT = Path(__file__).resolve().parents[1]
BASE = 'plugin://plugin.video.aperture.movies/'


class WindowHistory:
    def __init__(self, history):
        self.history = list(history)
        self.path = ''

    def execute(self, command):
        name, args = command.split('(', 1)
        params = args[:-1].split(',')
        window = {'Videos': 10025, '1120': 11120}[params[0]]
        if name == 'ReplaceWindow':
            self.history.pop()
        if window in self.history:
            self.history = self.history[:self.history.index(window) + 1]
        else:
            self.history.append(window)
        if window == 10025:
            self.path = params[1]
            assert params[2] == 'return'

    def back(self):
        # Omega CGUIControlGroup::OnAction returns false: groups cannot catch
        # Back. Exercise the actual patched native list, including the numeric
        # navigation that consumes Back while the guarded plugin runs.
        import sys
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            skin = Path(tmp)
            (skin / 'xml').mkdir()
            path = skin / 'xml/View_50_List.xml'
            path.write_text('<includes><include name="ListContainer"><definition>'
                            '<control type="fixedlist" id="$PARAM[list_id]"/>'
                            '</definition></include></includes>')
            with patch('sys.path', [str(ROOT / 'tools')] + sys.path):
                try:
                    import movie_source_return
                except ImportError:
                    movie_source_return = None
                if movie_source_return:
                    movie_source_return.apply(skin)
            control = ET.parse(path).find('.//control')
            assert control is not None
            actions = control.findall('onback')
        if self.path.startswith(BASE + '?action=torrentio_sources&home=1&') and actions:
            assert [node.text for node in actions] == [
                'RunPlugin(' + BASE + '?action=home_source_back)', '9000']
            assert actions[0].get('condition') == actions[1].get('condition')
            test = plugin_tests.PluginTests()
            test.setUp()
            try:
                _,_,_,_,commands = test.run_plugin([], window_ids=[10025],
                    folder_paths=[self.path], query='?action=home_source_back')
                for command in commands:
                    self.execute(command)
            finally:
                test.doCleanups()
            return
        self.history.pop()


class SourceBackTests(unittest.TestCase):
    setUp = plugin_tests.PluginTests.setUp
    run_plugin = plugin_tests.PluginTests.run_plugin

    def test_home_source_back_after_videos_visit_returns_home_not_main(self):
        for initial in ([10000, 11120], [10000, 10025, 11120]):
            for resume in ('0', '1'):
                with self.subTest(initial=initial, resume=resume):
                    trace = []
                    c,e,d,x,commands = self.run_plugin([], window_ids=[11120],
                        query='?action=home_sources&id=tt1234567&resume=' + resume,
                        http_trace=trace)
                    state = WindowHistory(initial)
                    for command in commands:
                        state.execute(command)
                    self.assertEqual(state.history[-1], 10025)
                    query = parse_qs(urlsplit(state.path).query)
                    self.assertEqual(query['id'], ['tt1234567'])
                    self.assertEqual(query.get('resume'), ['1'] if resume == '1' else None)
                    self.assertEqual((c,e,d,x,trace), ([],[],[],[],[]))
                    state.back()
                    self.assertEqual(state.history[-1], 11120,
                        'Native run42820458960: previously visited Videos trims Movies home')
                    self.assertEqual(state.history, [10000, 11120], 'No source-directory Back loop')
                    # Search keeps its ordinary native return, without a sticky
                    # override leaking from the prior source-directory visit.
                    _,_,_,_,search = self.run_plugin([], window_ids=[11120],
                        query='?action=home_search', search='Example')
                    for command in search:
                        state.execute(command)
                    state.back()
                    self.assertEqual(state.history, [10000, 11120])

    def test_normal_source_and_search_back_do_not_redirect_to_home(self):
        for path in (BASE + '?action=torrentio_sources&id=tt1234567',
                     BASE + '?mode=online&search=Example',
                     'plugin://unrelated/?action=torrentio_sources&home=1&id=tt1234567'):
            with self.subTest(path=path):
                state = WindowHistory([10000, 10025])
                state.path = path
                state.back()
                self.assertEqual(state.history, [10000])

    def test_source_return_patch_is_in_both_install_paths_after_xml_copy(self):
        build = (ROOT / 'tools/build_skin.py').read_text()
        install = (ROOT / 'install.sh').read_text()
        self.assertIn('movie_source_return(staged)', build)
        self.assertGreater(build.index('movie_source_return(staged)'),
                           build.index("shutil.copy2(movies, staged / 'xml/MyVideoNav.xml')"))
        self.assertIn('python3 "$SOURCE_DIR/tools/movie_source_return.py" "$TMP"', install)
        self.assertGreater(install.index('tools/movie_source_return.py'),
                           install.index('cp "$SOURCE_DIR/skin/xml/MyVideoNav.xml"'))

    def test_return_handler_rejects_stale_unrelated_aborted_or_wrong_window(self):
        source = BASE + '?action=torrentio_sources&home=1&id=tt1234567&resume=1'
        for paths, windows, abort in [
                ([source, BASE + '?mode=online'], [10025], False),
                ([source], [10025, 10000], False),
                ([source], [11120], False),
                ([source], [10025], True),
                ([BASE + '?action=torrentio_sources&id=tt1234567'], [10025], False)]:
            with self.subTest(paths=paths, windows=windows, abort=abort):
                trace = []
                result = self.run_plugin([], query='?action=home_source_back',
                    folder_paths=paths, window_ids=windows, abort=abort, http_trace=trace)
                self.assertEqual(result, ([],[],[],[],[]))
                self.assertEqual(trace, [])

    def test_patch_preserves_normal_actions_and_is_idempotent(self):
        import sys
        import tempfile
        from unittest.mock import patch
        with patch('sys.path', [str(ROOT / 'tools')] + sys.path):
            import movie_source_return as patcher
        with tempfile.TemporaryDirectory() as tmp:
            skin = Path(tmp)
            (skin / 'xml').mkdir()
            path = skin / 'xml/View_50_List.xml'
            original = ('<includes><control type="fixedlist" id="50">'
                        '<onback condition="Control.HasFocus(50)">PreviousMenu</onback>'
                        '<onleft>9000</onleft></control></includes>')
            path.write_text(original)
            home = skin / 'xml/Home.xml'
            home.write_text(original)
            patcher.apply(skin)
            first = path.read_bytes()
            patcher.apply(skin)
            self.assertEqual(path.read_bytes(), first)
            self.assertEqual(home.read_text(), original)
            node = ET.parse(path).find('.//control')
            assert node is not None
            self.assertEqual(node.findtext('onleft'), '9000')
            actions = node.findall('onback')
            self.assertEqual(actions[0].text, 'PreviousMenu')
            self.assertEqual(actions[0].get('condition'), '![' + patcher.CONDITION + '] + [Control.HasFocus(50)]')
            self.assertIn('!System.HasVisibleModalDialog', patcher.CONDITION)
            self.assertIn('Window.IsActive(videos)', patcher.CONDITION)
            self.assertEqual([a.text for a in actions[1:]], [patcher.ACTION, '9000'])

    def test_details_source_back_uses_same_home_return_contract(self):
        _,_,_,_,commands = self.run_plugin([], window_ids=[11120],
            query='?action=online_details&id=tt1234567', selection=0,
            catalog_payload={'meta': {'id': 'tt1234567', 'name': 'Example', 'type': 'movie'}})
        state = WindowHistory([10000, 10025, 11120])
        for command in commands:
            state.execute(command)
        state.back()
        self.assertEqual(state.history, [10000, 11120])

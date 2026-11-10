"""Harness regressions only; native acceptance still requires disposable Kodi."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]


def service_functions(*names):
    tree = ast.parse((ROOT / 'tools/movies_online_qa_service.py').read_text())
    return compile(ast.Module(body=[node for node in tree.body
                                   if isinstance(node, ast.FunctionDef) and node.name in names],
                              type_ignores=[]), '<online-qa>', 'exec')


class OnlineTransportTests(unittest.TestCase):
    def test_disposable_transport_exercises_real_clients_without_network(self):
        import importlib.util
        import json
        import os
        import shutil
        import sys
        import tempfile
        from unittest.mock import patch
        sys.path.insert(0, str(ROOT / 'tools'))
        import movies_fixture
        with tempfile.TemporaryDirectory(prefix='aperture-movies-qa.') as tmp:
            runtime = Path(tmp)
            out = runtime / 'out'
            out.mkdir()
            lib = runtime / 'addon/resources/lib'
            shutil.copytree(ROOT / 'movies-kodi/resources/lib', lib)
            self.assertTrue(hasattr(movies_fixture, 'install_online_mocks'), 'Missing isolated Torrentio transport wiring')
            movies_fixture.install_online_mocks(ROOT, lib)
            def load(name, path):
                spec = importlib.util.spec_from_file_location(name, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
            with patch.dict(os.environ, APERTURE_MOVIES_RUNTIME=tmp, APERTURE_MOVIES_OUT=str(out)):
                qa = load('qa', lib / 'qa_provider.py')
                with patch.dict(sys.modules, {'resources.lib.qa_provider': qa}):
                    rd = load('qa_rd', lib / 'debrid.py')
                    t = load('qa_torrentio', lib / 'torrentio.py')
                    catalog = load('qa_catalog', lib / 'catalog.py')
                    movies, state, _ = catalog.browse({'search': ['Synthetic Online Horizon']})
                    self.assertEqual(movies[0]['title'], 'Synthetic Online Horizon')
                    self.assertEqual(state['search'], 'Synthetic Online Horizon')
                    self.assertIn('catalogue-search', (out / 'mock-events.jsonl').read_text())
                    with patch.dict(sys.modules, {'resources.lib.debrid': rd}):
                        with patch('socket.getaddrinfo', side_effect=AssertionError('Live DNS forbidden')):
                            store = rd.Store(str(runtime / 'profile'))
                            now = [1000]
                            client = rd.Client(store, clock=lambda: now[0])
                            session = client.begin(rd.PUBLIC_CLIENT_ID)
                            with self.assertRaises(rd.DebridError):
                                qa.debrid('GET', rd.OAUTH + 'device/credentials')
                            (out / 'approve-synthetic-device').touch()
                            def wait(seconds):
                                now[0] += seconds
                                return False
                            with store.locked():
                                client.connect(session, wait, lambda: False)
                            provider = t.Client(t.Config.from_token(client.token()))
                            provider.check()
                            sources = provider.streams('tt1234567')
                            self.assertEqual(len(sources), 1)
                            media = runtime / 'movies/Amber Horizon.mkv'
                            media.parent.mkdir()
                            media.write_bytes(b'unit-test placeholder; native fixture generates actual video')
                            path = provider.playback('tt1234567', sources[0].id)
                            self.assertEqual(path, str(media))
                            with self.assertRaises(t.ProviderError):
                                provider.playback('tt1234567', sources[0].id, cancelled=lambda: True)
                            with self.assertRaises(AssertionError):
                                qa.torrentio('https://attacker.example/manifest.json')
                            with self.assertRaises(AssertionError):
                                qa.debrid('GET', rd.API + 'downloads')
                            with self.assertRaises(AssertionError):
                                qa.playback_file('https://attacker.example/video.mkv')
            events = [json.loads(line)['event'] for line in (out / 'mock-events.jsonl').read_text().splitlines()]
            for event in ('fake-device-approved', 'fake-token-exchange', 'torrentio-manifest', 'torrentio-streams', 'torrentio-resolve', 'torrentio-local-handoff'):
                self.assertIn(event, events)
            self.assertEqual(events.count('torrentio-streams'), 2, 'Playback must refetch via the real client')
            self.assertEqual(events.count('torrentio-resolve'), 1)
            log = (out / 'mock-events.jsonl').read_text()
            self.assertNotIn(qa.ACCESS_TOKEN, log)
            self.assertNotIn(qa.REFRESH_TOKEN, log)


class OnlineHarnessTests(unittest.TestCase):
    def test_native_journey_no_longer_waits_for_removed_rights_prompt(self):
        source = (ROOT / 'tools/movies_online_qa_service.py').read_text()
        self.assertNotIn('Find streams with Torrentio?', source)
        self.assertNotIn('Play selected source?', source)

    def test_native_journey_requires_wizard_search_source_and_real_player(self):
        tree = ast.parse((ROOT / 'tools/movies_online_qa_service.py').read_text())
        functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.assertIn('torrentio_journey', functions, 'Online scenario must exercise Torrentio, not just dismiss actions')
        journey = ast.unparse(functions['torrentio_journey'])
        for evidence in ('Connect with Real-Debrid (no token copying)',
                         'Share access with Torrentio', 'approve-synthetic-device',
                         'Check saved connection (no playback)', 'Input.SendText',
                         'Choose source', 'Choose a source',
                         'automatic movie selection', 'Player.GetActivePlayers',
                         'getPlayingFile', 'ImageStat.Stat', 'Player.Stop',
                         'torrentio-resolve', 'torrentio-local-handoff'):
            self.assertIn(evidence, journey)
        for bypass in ('RunPlugin(', 'Player.Open', '.play(', 'Container.Update('):
            self.assertNotIn(bypass, journey, 'Must use the native UI, not bypass the wizard/player handoff')
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'torrentio_journey']
        self.assertEqual(len(calls), 1, 'The native scenario must actually run the journey')

    def test_details_assert_actions_before_return_to_browsing(self):
        state = {'dialog': 12002, 'choice': 0}
        choices = ['Find streams (Torrentio)', 'Set up online playback', 'Back to browsing']
        inputs = []
        def rpc(action):
            inputs.append(action)
            if action == 'Input.Select':
                if state['dialog'] == 12002:
                    state['dialog'] = 12000
                else:
                    self.assertEqual(state['choice'], 2, 'Must select Back to browsing')
                    state['dialog'] = 0
            elif action == 'Input.Down':
                state['choice'] += 1
        def label(key):
            if key == 'Control.GetLabel(1)':
                return 'Movie actions'
            if key == 'System.CurrentControl':
                return choices[state['choice']]
            return ''
        def until(description, predicate, *args):
            self.assertTrue(predicate(), description)
        ns = dict(rpc=rpc, until=until, capture=Mock(),
                  xbmc=SimpleNamespace(getInfoLabel=label),
                  xbmcgui=SimpleNamespace(getCurrentWindowDialogId=lambda: state['dialog']),
                  monitor=Mock())
        exec(service_functions('select_choice', 'movie_actions'), ns)
        self.assertIn('movie_actions', ns, 'Native QA needs an explicit Movie actions transition')
        ns['movie_actions']('Back to browsing')
        self.assertEqual(state['dialog'], 0)
        self.assertEqual(inputs, ['Input.Select', 'Input.Down', 'Input.Down', 'Input.Select'])

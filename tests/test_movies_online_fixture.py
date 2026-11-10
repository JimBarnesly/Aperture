"""Harness regressions only; native acceptance still requires disposable Kodi."""
import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any
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
    def test_until_persists_pending_stage_before_native_predicate(self):
        import json
        import tempfile
        import time
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            ns: dict[str, Any] = dict(OUT=out, json=json, time=time, checks=[{'check': 'prior-stage'}],
                      xbmcgui=SimpleNamespace(getCurrentWindowId=lambda: 11120,
                                              getCurrentWindowDialogId=lambda: 0),
                      xbmc=SimpleNamespace(getInfoLabel=lambda key: 'synthetic',
                          getCondVisibility=lambda key: False,
                          Window=lambda key: None),
                      monitor=SimpleNamespace(waitForAbort=lambda seconds: False))
            exec(service_functions('until', 'checkpoint'), ns)
            def native_fault():
                self.assertTrue((out / 'progress.json').exists(),
                                'Native crash loses pending stage and completed assertions')
                progress = json.loads((out / 'progress.json').read_text())
                self.assertEqual(progress['stage'], 'browse after home resume')
                self.assertEqual(progress['status'], 'waiting')
                self.assertEqual(progress['window'], 11120)
                self.assertEqual(progress['checks'], [{'check': 'prior-stage'}])
                raise RuntimeError('simulated native boundary')
            with self.assertRaisesRegex(RuntimeError, 'simulated native boundary'):
                ns['until']('browse after home resume', native_fault)
            ns['until']('completed-stage', lambda: True)
            self.assertEqual(json.loads((out / 'progress.json').read_text())['stage'], 'completed-stage')

    def test_online_navigation_rejects_visible_closing_modals(self):
        ns: dict[str, Any] = dict(xbmcgui=SimpleNamespace(getCurrentWindowId=lambda: 10025),
                  xbmc=SimpleNamespace(getCondVisibility=lambda condition:
                                       condition == 'System.HasVisibleModalDialog'))
        exec(service_functions('settled'), ns)
        self.assertFalse(ns['settled'](), 'Closing dialogs still consume input in Omega')
        tree = ast.parse((ROOT / 'tools/movies_online_qa_service.py').read_text())
        conditions = [n.args[0].value for n in ast.walk(tree)
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                      and n.func.attr == 'getCondVisibility' and n.args
                      and isinstance(n.args[0], ast.Constant)]
        self.assertNotIn('System.HasModalDialog', conditions,
                         'Every online/home transition must use a supported Kodi condition')

    def test_home_search_reopens_only_after_keyboard_close_and_focus_restore(self):
        # Replay native run 42818993595: the removed HasModalDialog is false
        # while the keyboard still owns input during its closing animation.
        state: dict[str, Any] = dict(window=10000, keyboard=False, closing=False, now=0,
                                    opens=0, cancels=0, focus='Movies')
        inputs = []

        class FinishedSearchChecks(Exception):
            pass

        def rpc(action):
            inputs.append(action)
            if state['closing']:
                self.fail('Kodi ignores input while the modal closing animation runs')
            if action == 'Input.Select':
                if state['window'] == 10000:
                    state.update(window=11120, focus='Search')
                else:
                    self.assertEqual(state['focus'], 'Search')
                    state.update(keyboard=True, focus='Keyboard')
                    state['opens'] += 1
            elif action == 'Input.Back':
                state.update(keyboard=False, closing=True)
                state['cancels'] += 1
            elif action == 'Input.Down':
                self.assertEqual(state['focus'], 'Search')
                raise FinishedSearchChecks()

        def condition(expression):
            return {
                'Window.IsActive(virtualkeyboard)': state['keyboard'],
                'System.HasVisibleModalDialog': state['keyboard'] or state['closing'],
                'Control.HasFocus(720)': state['focus'] == 'Search',
                # Unsupported Omega conditions, including HasModalDialog, are false.
            }.get(expression, False)

        def wait(_):
            state['now'] += .15
            if state['closing']:
                state.update(closing=False, focus='Search')
            return False

        def label(key):
            return {'System.CurrentControl': state['focus'],
                    'Container(730).NumItems': '0',
                    'Container(731).NumItems': '1',
                    'Container(732).NumItems': '1'}.get(key, '')

        ns = dict(rpc=rpc, capture=Mock(), checkpoint=Mock(), json=__import__('json'),
                  time=SimpleNamespace(monotonic=lambda: state['now']),
                  monitor=SimpleNamespace(waitForAbort=wait),
                  xbmc=SimpleNamespace(getInfoLabel=label, getCondVisibility=condition,
                                       executebuiltin=Mock()),
                  xbmcgui=SimpleNamespace(getCurrentWindowId=lambda: state['window'],
                                         getCurrentWindowDialogId=lambda: 9999))
        exec(service_functions('until', 'movies_home_journey'), ns)
        with self.assertRaises(FinishedSearchChecks):
            ns['movies_home_journey']()
        self.assertEqual((state['opens'], state['cancels']), (2, 2))
        self.assertEqual(inputs, ['Input.Select', 'Input.Select', 'Input.Back',
                                  'Input.Select', 'Input.Back', 'Input.Down'])

    def test_home_source_journey_uses_row_buttons_and_native_directory(self):
        tree = ast.parse((ROOT / 'tools/movies_online_qa_service.py').read_text())
        functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.assertIn('home_source_journey', functions)
        source = ast.unparse(functions['home_source_journey'])
        for evidence in ('730', '731', '732', '740', '741', '742', 'Input.Right',
                         'Input.Select', 'Input.Back', 'torrentio_sources', 'resume=1',
                         'torrentio-resolve', 'home-source-directory-cancel'):
            self.assertIn(evidence, source)
        for bypass in ('RunPlugin(', 'SetFocus(', 'Container.Update(', 'Player.Open'):
            self.assertNotIn(bypass, source)
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == 'home_source_journey']
        self.assertEqual(len(calls), 1)

    def test_online_harness_budget_includes_history_wait(self):
        source = (ROOT / 'tools/movies_smoke.sh').read_text()
        self.assertIn('240s', source, 'Online journey now includes a 22-second stale-write observation')
        self.assertIn('{1..2400}', source)

    def test_history_acceptance_keeps_immediate_back_and_checks_transient_controls(self):
        tree = ast.parse((ROOT / 'tools/movies_online_qa_service.py').read_text())
        journey = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'history_journey')
        source = ast.unparse(journey)
        for evidence in ('Input.ShowOSD', 'Player.Seek', 'return fullscreen stays paused',
                         'OSD dismissed without pause', 'Back pauses after controls'):
            self.assertIn(evidence, source)
        # Never hide the sub-poll exit by waiting after fullscreen becomes ready.
        statements = journey.body
        ready = next(i for i, n in enumerate(statements) if "until('fullscreen resume'" in ast.unparse(n))
        self.assertEqual(ast.unparse(statements[ready + 1]), "rpc('Input.Back')")

    def test_native_history_journey_checks_record_resume_pause_clear_and_suggestions(self):
        tree = ast.parse((ROOT / 'tools/movies_online_qa_service.py').read_text())
        functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.assertIn('history_journey', functions, 'Native QA must exercise actual session/history plumbing')
        journey = ast.unparse(functions['history_journey'])
        for evidence in ('history-private', 'resume_seconds', 'Continue watching', 'History',
                         'Suggested for you', 'Clear history', 'Input.Back', 'Player.Paused',
                         'torrentio-resolve', 'getTime', 'catalogue suggestions only'):
            self.assertIn(evidence, journey)
        for bypass in ('RunPlugin(', 'Player.Open', '.play(', 'write_text', 'record_playback'):
            self.assertNotIn(bypass, journey)
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == 'history_journey']
        self.assertEqual(len(calls), 1)

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
                         'Automatic movie playback', 'autoplay-effects-v1',
                         'aperture_session',
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
        choices = ['Choose source', 'Set up online playback', 'Back to browsing']
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

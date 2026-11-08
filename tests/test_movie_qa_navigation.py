"""Synthetic timing regressions for the harness, not real Kodi acceptance."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]


class MovieIdleTests(unittest.TestCase):
    def setUp(self):
        self.tree = ast.parse((ROOT / 'tools/movies_qa_service.py').read_text())
        names = {'settled', 'cinematic', 'wait_for_movie_idle'}
        functions = [node for node in self.tree.body
                     if isinstance(node, ast.FunctionDef) and node.name in names]
        self.now = 0.0
        self.conditions = {'Control.IsVisible(61)': True}
        self.labels = {'Container.FolderPath': 'source-root',
                       'ListItem.Label': 'Amber Horizon', 'Container.NumItems': '3'}
        self.until = Mock()
        namespace = {
            'time': SimpleNamespace(monotonic=lambda: self.now),
            'xbmc': SimpleNamespace(
                getInfoLabel=lambda label: self.labels.get(label, ''),
                getCondVisibility=lambda condition: self.conditions.get(condition, False)),
            'xbmcgui': SimpleNamespace(getCurrentWindowId=lambda: 10025),
            'until': self.until,
        }
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<movie-idle>', 'exec'), namespace)
        namespace['wait_for_movie_idle']('poster reset', 'source-root')
        self.ready = self.until.call_args.args[1]

    def sample(self, now):
        self.now = now
        return self.ready()

    def test_visible_cinematic_view_is_not_immediately_ready(self):
        self.assertFalse(self.sample(0))
        self.assertFalse(self.sample(.9))
        self.assertTrue(self.sample(1.1))

    def test_delayed_reset_refresh_restarts_quiet_interval(self):
        self.assertFalse(self.sample(0))
        self.assertFalse(self.sample(.3))
        self.conditions['Container.IsUpdating'] = True
        self.assertFalse(self.sample(.6))
        self.conditions['Container.IsUpdating'] = False
        self.assertFalse(self.sample(.8))
        self.assertFalse(self.sample(1.2))
        self.assertTrue(self.sample(1.9))

    def test_dialog_or_busy_overlay_restarts_quiet_interval(self):
        for condition in ('System.HasModalDialog', 'Window.IsActive(busydialog)',
                          'Window.IsActive(busydialognocancel)'):
            with self.subTest(condition=condition):
                self.setUp()
                self.assertFalse(self.sample(0))
                self.conditions[condition] = True
                self.assertFalse(self.sample(.8))
                self.conditions[condition] = False
                self.assertFalse(self.sample(1))
                self.assertFalse(self.sample(1.8))
                self.assertTrue(self.sample(2.1))

    def test_listing_or_focus_change_restarts_quiet_interval(self):
        for label, value in (('ListItem.Label', 'Collections'), ('Container.NumItems', '4')):
            with self.subTest(label=label):
                self.setUp()
                self.assertFalse(self.sample(0))
                self.labels[label] = value
                self.assertFalse(self.sample(.8))
                self.assertFalse(self.sample(1.2))
                self.assertTrue(self.sample(1.9))

    def test_wrong_folder_or_view_never_passes(self):
        self.labels['Container.FolderPath'] = 'other-folder'
        self.assertFalse(self.sample(0))
        self.assertFalse(self.sample(100))
        self.labels['Container.FolderPath'] = 'source-root'
        self.conditions['Control.IsVisible(61)'] = False
        self.assertFalse(self.sample(101))
        self.assertFalse(self.sample(200))

    def test_poster_cancel_and_reset_use_guard_before_more_input(self):
        calls = [node for node in ast.walk(self.tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                 and node.func.id == 'wait_for_movie_idle'
                 and isinstance(node.args[0], ast.Constant)
                 and node.args[0].value.startswith('poster')]
        self.assertCountEqual([node.args[0].value for node in calls],
                         ['poster reset returns to movies', 'poster picker cancelled'])
        self.assertTrue(all(isinstance(node.args[1], ast.Name)
                            and node.args[1].id == 'root_path' for node in calls))


if __name__ == '__main__':
    unittest.main()


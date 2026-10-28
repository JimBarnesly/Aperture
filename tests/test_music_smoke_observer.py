"""Observer startup-identity regression; not GUI/player runtime acceptance."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class ObserverIdentityTests(unittest.TestCase):
    def setUp(self):
        modules = {name: types.ModuleType(name) for name in ('xbmc', 'xbmcaddon', 'xbmcgui')}
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location('music_observer', ROOT / 'tools/music_smoke_observer.py')
            self.observer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.observer)

    def test_missing_startup_metadata_is_pending_not_a_verified_player(self):
        item = {'type': 'unknown', 'label': '', 'albumid': -1, 'id': -1, 'file': ''}
        self.assertFalse(self.observer.player_identity_ready(item, '/tmp/fixture', {4}, {7}))
        class Window:
            def getFocusId(self): return 100
            def getProperty(self, name): return ''
        self.observer.xbmcgui.getCurrentWindowId = lambda: 13000
        self.observer.xbmcgui.getCurrentWindowDialogId = lambda: 9999
        self.observer.xbmcgui.Window = lambda *args: Window()
        self.observer.xbmc.getCondVisibility = lambda *args: False
        self.observer.xbmc.getSkinDir = lambda: 'skin.apeture'
        replies = {'AudioLibrary.GetAlbums': {'albums': [{'albumid': 4, 'title': 'Fixture'}]},
                   'AudioLibrary.GetSongs': {'songs': [{'songid': 7, 'file': '/tmp/fixture/test.flac'}]},
                   'Player.GetActivePlayers': [{'type': 'audio', 'playerid': 0}],
                   'Player.GetItem': {'item': item}, 'Playlist.GetItems': {'items': []}}
        self.observer.rpc = lambda method, **kwargs: replies[method]
        state = self.observer.snapshot({'fixture': '/tmp/fixture', 'expected': {'albums': [{'title': 'Fixture'}]}}, 1, None)
        self.assertTrue(state['active_audio'])
        self.assertIsNone(state['player'])
        self.assertEqual(state['player_pending'], item)

    def test_identified_fixture_player_is_ready(self):
        item = {'albumid': 4, 'id': 7, 'file': '/tmp/fixture/test.flac'}
        self.assertTrue(self.observer.player_identity_ready(item, '/tmp/fixture', {4}, {7}))

    def test_foreign_path_or_positive_ids_are_still_rejected(self):
        for item in ({'albumid': 4, 'id': 7, 'file': '/tmp/not-fixture/test.flac'},
                     {'albumid': 99}, {'id': 99}):
            with self.subTest(item=item), self.assertRaises(RuntimeError):
                self.observer.player_identity_ready(item, '/tmp/fixture', {4}, {7})


if __name__ == '__main__': unittest.main()

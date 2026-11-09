import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from test_movie_torrentio import t, MANIFEST, TOKEN

ROOT = Path(__file__).resolve().parents[1]


class TorrentioUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dialog, self.xbmc, self.gui, self.plugin = Mock(), Mock(), Mock(), Mock()
        self.dialog.select.return_value = -1
        self.dialog.yesno.return_value = False
        self.gui.Dialog.return_value = self.dialog
        self.xbmc.getInfoLabel.return_value = 'plugin://movies/?mode=online'
        self.xbmc.Monitor.return_value.abortRequested.return_value = False
        path = ROOT / 'movies-kodi/resources/lib/torrentio_ui.py'
        self.assertTrue(path.exists(), 'Torrentio wizard/UI is missing')
        with patch.dict(sys.modules, {'xbmc': self.xbmc, 'xbmcgui': self.gui, 'xbmcplugin': self.plugin, 'resources.lib.torrentio': t}):
            spec = importlib.util.spec_from_file_location('torrentio_ui_test', path)
            self.ui = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.ui)
        self.client = Mock()
        self.ui.Client = Mock(return_value=self.client)

    def run_ui(self, query=None):
        self.ui.run(query or {'action': ['torrentio_setup']}, self.temp.name, 'plugin://movies/', 3)

    def connect(self):
        source = Path(self.temp.name) / 'input.txt'
        source.write_text(MANIFEST)
        source.chmod(0o600)
        t.Store(self.temp.name).import_file(str(source))
        return str(source)

    def test_cancel_and_decline_setup_never_connect(self):
        self.run_ui()
        self.assertEqual(self.client.mock_calls, [])
        self.xbmc.executebuiltin.assert_not_called()
        self.assertIn('Set up online playback', self.dialog.select.call_args.args[0])
        self.dialog.select.return_value = 0
        self.run_ui()
        self.assertEqual(self.client.mock_calls, [])
        self.xbmc.executebuiltin.assert_not_called()

    def test_browser_handoff_is_public_and_honest_not_connected(self):
        self.dialog.select.return_value = 0
        self.dialog.yesno.return_value = True
        with patch.object(self.ui.webbrowser, 'open', return_value=True) as browser:
            self.run_ui()
        browser.assert_called_once_with('https://torrentio.strem.fun/configure', new=2)
        self.assertIsNone(t.Store(self.temp.name).load())
        self.assertIn('not connected', self.dialog.ok.call_args.args[1])
        self.assertEqual(self.client.mock_calls, [])

    def test_import_requires_all_consents_and_no_network(self):
        source = self.connect()
        t.Store(self.temp.name).clear()
        self.dialog.select.return_value = 1
        self.dialog.browseSingle.return_value = source
        self.dialog.yesno.side_effect = [True, False]
        self.run_ui()
        self.assertIsNone(t.Store(self.temp.name).load())
        self.dialog.yesno.side_effect = None
        self.dialog.yesno.return_value = True
        self.run_ui()
        self.assertIsNotNone(t.Store(self.temp.name).load())
        self.assertEqual(self.client.mock_calls, [])
        self.assertNotIn(TOKEN, repr(self.dialog.mock_calls))

    def test_find_requires_consent_and_explicit_selection_then_refetches(self):
        self.connect()
        source = Mock(id='a' * 64, label='Real-Debrid · 1080p')
        self.client.streams.return_value = [source]
        query = {'action': ['torrentio_find'], 'id': ['tt1234567']}
        self.run_ui(query)
        self.client.streams.assert_not_called()
        self.dialog.yesno.return_value = True
        self.run_ui(query)
        self.client.streams.assert_called_once_with('tt1234567')
        self.client.playback.assert_not_called()
        self.dialog.select.return_value = 0
        self.client.playback.return_value = 'https://seed.download.real-debrid.com/file.mkv|redirect-limit=0'
        self.run_ui(query)
        self.assertEqual(self.client.playback.call_args.args, ('tt1234567', 'a' * 64))
        self.assertIn('cancelled', self.client.playback.call_args.kwargs)
        self.xbmc.Player.return_value.play.assert_called_once()
        self.assertNotIn(TOKEN, repr(self.xbmc.mock_calls))

    def test_stale_navigation_or_cancel_prevents_network(self):
        self.connect()
        self.dialog.yesno.return_value = True
        self.xbmc.getInfoLabel.side_effect = ['original', 'new']
        self.run_ui({'action': ['torrentio_find'], 'id': ['tt1234567']})
        self.assertEqual(self.client.mock_calls, [])

    def test_disconnect_and_status_do_not_contact_provider(self):
        self.connect()
        self.dialog.select.return_value = 3
        self.run_ui()
        self.assertIn('not verified', self.dialog.ok.call_args.args[1])
        self.dialog.select.return_value = 4
        self.dialog.yesno.return_value = True
        self.run_ui()
        self.assertIsNone(t.Store(self.temp.name).load())
        self.assertEqual(self.client.mock_calls, [])

    def test_connection_check_is_explicit_and_does_not_claim_account_valid(self):
        self.connect()
        self.dialog.select.return_value = 2
        self.run_ui()
        self.client.check.assert_not_called()
        self.dialog.yesno.return_value = True
        self.run_ui()
        self.client.check.assert_called_once()
        self.assertIn('not verified', self.dialog.ok.call_args.args[1])

from pathlib import Path
import importlib.util
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from test_movie_debrid import rd

ROOT = Path(__file__).resolve().parents[1]


class DebridUITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dialog = Mock()
        self.dialog.select.return_value = -1
        self.dialog.yesno.return_value = False
        self.xbmc = Mock()
        self.xbmc.getInfoLabel.return_value = 'plugin://plugin.video.aperture.movies/?mode=discover'
        self.plugin = Mock()
        self.gui = Mock()
        self.gui.Dialog.return_value = self.dialog
        self.addon = Mock()
        self.addon.getSetting.return_value = 'public-app'
        mods = {'xbmc': self.xbmc, 'xbmcgui': self.gui, 'xbmcplugin': self.plugin, 'resources.lib.debrid': rd}
        with patch.dict(sys.modules, mods):
            spec = importlib.util.spec_from_file_location('debrid_ui_test', ROOT / 'movies-kodi/resources/lib/debrid_ui.py')
            self.ui = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.ui)
        self.client = Mock()
        self.ui.Client = Mock(return_value=self.client)

    def run_ui(self, query=None):
        self.ui.run(query or {'action': ['providers']}, self.addon, self.tmp.name, 'plugin://plugin.video.aperture.movies/', 3)

    def sign_in(self):
        rd.Store(self.tmp.name).save({'client_id': 'fixture', 'client_secret': 'secret', 'access_token': 'access', 'refresh_token': 'refresh', 'expires_at': 2000000000})

    def test_cancel_sources_no_network_or_navigation(self):
        self.run_ui()
        self.assertEqual(self.client.mock_calls, [])
        self.xbmc.executebuiltin.assert_not_called()

    def test_browse_releases_lock_before_navigation(self):
        self.sign_in()
        self.dialog.select.return_value = 0
        def navigate(command):
            with rd.Store(self.tmp.name).locked():
                self.assertIn('?mode=rd', command)
        self.xbmc.executebuiltin.side_effect = navigate
        self.run_ui()
        self.xbmc.executebuiltin.assert_called_once()
        self.dialog.ok.assert_not_called()

    def test_decline_connect_no_network(self):
        self.dialog.select.return_value = 0
        self.run_ui()
        self.client.begin.assert_not_called()

    def test_configured_id_required(self):
        self.dialog.select.return_value = 0
        self.addon.getSetting.return_value = ''
        self.run_ui()
        self.client.begin.assert_not_called()
        self.dialog.ok.assert_called_once()

    def test_configure_only_opens_settings(self):
        self.dialog.select.return_value = 1
        self.run_ui()
        self.addon.openSettings.assert_called_once()
        self.assertEqual(self.client.mock_calls, [])

    def test_connect_prompt_contains_storage_and_access_disclosure(self):
        self.dialog.select.return_value = 0
        self.run_ui()
        text = self.dialog.yesno.call_args.args[1]
        self.assertIn('not encrypted', text)
        self.assertIn('refresh credentials', text)
        self.assertIn('account downloads', text)

    def test_download_routes_contain_only_id_and_page(self):
        self.client.downloads.return_value = [{'id': 'ONE', 'filename': 'Owned.mp4', 'download': 'https://cdn.example/secret-signed-url'}]
        self.run_ui({'mode': ['rd']})
        call = self.plugin.addDirectoryItem.call_args.args
        self.assertIn('action=rd_play&id=ONE&page=1', call[1])
        self.assertNotIn('secret', str(self.plugin.mock_calls))
        self.plugin.endOfDirectory.assert_called_once_with(3, succeeded=True, cacheToDisc=False)

    def test_playback_fail_resolves_false_not_directory(self):
        self.client.playback.side_effect = rd.DebridError('missing')
        self.run_ui({'action': ['rd_play'], 'id': ['ONE'], 'page': ['1']})
        self.assertFalse(self.plugin.setResolvedUrl.call_args.args[1])
        self.plugin.endOfDirectory.assert_not_called()

    def test_playback_passes_signed_url_only_at_resolution(self):
        self.client.playback.return_value = 'https://cdn.example/secret'
        self.run_ui({'action': ['rd_play'], 'id': ['ONE'], 'page': ['1']})
        self.gui.ListItem.assert_called_with(path='https://cdn.example/secret')
        self.assertTrue(self.plugin.setResolvedUrl.call_args.args[1])
        self.xbmc.executebuiltin.assert_not_called()

    def test_decline_resolve_no_post(self):
        self.sign_in()
        self.dialog.select.return_value = 1
        self.dialog.input.return_value = 'https://host.example/owned'
        self.run_ui()
        self.client.resolve_link.assert_not_called()
        self.xbmc.Player.assert_not_called()

    def test_navigation_change_prevents_action(self):
        self.dialog.select.return_value = 0
        self.xbmc.getInfoLabel.side_effect = ['original', 'new']
        self.run_ui()
        self.client.begin.assert_not_called()

    def test_disconnect_decline_preserves_credentials(self):
        self.sign_in()
        self.dialog.select.return_value = 2
        self.run_ui()
        self.assertIsNotNone(rd.Store(self.tmp.name).load())

    def test_disconnect_confirmation_clears_only_local(self):
        self.sign_in()
        self.dialog.select.return_value = 2
        self.dialog.yesno.return_value = True
        self.run_ui()
        self.assertIsNone(rd.Store(self.tmp.name).load())
        self.assertEqual(self.client.mock_calls, [])

    def test_cancelled_oauth_closes_progress(self):
        self.dialog.select.return_value = 0
        self.dialog.yesno.return_value = True
        self.client.begin.return_value = {'user_code': 'ABC123'}
        self.client.connect.side_effect = rd.DebridError('cancelled')
        self.run_ui()
        self.gui.DialogProgress.return_value.close.assert_called_once()
        self.dialog.ok.assert_not_called()


if __name__ == '__main__':
    unittest.main()

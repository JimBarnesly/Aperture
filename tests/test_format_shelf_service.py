import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


class ShelfServiceTests(unittest.TestCase):
    def setUp(self):
        self.home, self.shelf = Mock(), Mock()
        self.xbmc = Mock()
        self.gui = types.SimpleNamespace(getCurrentWindowId=lambda:10502,
            Window=lambda window:self.home if window == 10000 else self.shelf)
        spec = importlib.util.spec_from_file_location('shelf_service', Path(__file__).resolve().parents[1] / 'format-kodi/shelf_service.py')
        self.service = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, xbmc=self.xbmc, xbmcgui=self.gui):
            spec.loader.exec_module(self.service)

    def test_selected_position_is_global_and_updates_on_reverse(self):
        item = self.xbmc
        for position in ('1', '5', '3'):
            item.getInfoLabel.return_value = position
            self.service.update_focus()
            self.home.setProperty.assert_called_with(self.service.PROPERTY, position)

    def test_other_window_and_non_format_item_do_not_change_property(self):
        self.gui.getCurrentWindowId=lambda:10000
        self.service.update_focus()
        self.home.setProperty.assert_not_called()
        self.gui.getCurrentWindowId=lambda:10502
        self.xbmc.getInfoLabel.return_value=''
        self.service.update_focus()
        self.home.setProperty.assert_not_called()

    def test_missing_control_is_harmless(self):
        self.xbmc.getInfoLabel.side_effect=RuntimeError('not in this skin')
        self.service.update_focus()
        self.home.setProperty.assert_not_called()

    def test_service_syncs_skin_changes_and_cleans_up_on_abort(self):
        keymap = Mock()
        constructor = Mock(return_value=keymap)
        monitor = self.xbmc.Monitor.return_value
        monitor.abortRequested.return_value = False
        monitor.waitForAbort.side_effect = [False, True]
        self.xbmc.getSkinDir.side_effect = ['skin.aperture', 'skin.estuary']
        with patch.dict(sys.modules, xbmcvfs=Mock(),
                        turntable_keymap=types.SimpleNamespace(TurntableKeymap=constructor)), \
                patch.object(self.service.time, 'monotonic', side_effect=[0, 2]), \
                patch.object(self.service.IdleShelfReturn, 'update'):
            self.service.run()
        self.assertEqual([call.args for call in keymap.sync.call_args_list], [(True,), (False,)])
        keymap.close.assert_called_once_with()
        # Reload is the sole built-in, and is delegated to changed keymap state.
        constructor.call_args.args[2]()
        self.xbmc.executebuiltin.assert_called_once_with('Action(reloadkeymaps)')

    def test_service_removes_owned_binding_if_an_unexpected_error_stops_it(self):
        keymap = Mock()
        self.xbmc.Monitor.return_value.abortRequested.return_value = False
        with patch.dict(sys.modules, xbmcvfs=Mock(),
                        turntable_keymap=types.SimpleNamespace(TurntableKeymap=Mock(return_value=keymap))), \
                patch.object(self.service, 'update_focus', side_effect=ValueError('test error')):
            with self.assertRaisesRegex(ValueError, 'test error'):
                self.service.run()
        keymap.close.assert_called_once_with()

    def test_long_album_liner_notes_keep_every_track_and_current_marker(self):
        titles = ['Track ' + str(i) for i in range(1, 25)]
        lines = self.service.album_lines(titles, 12).splitlines()
        self.assertEqual(len(lines), 24)
        self.assertEqual(lines[0], '1.  Track 1')
        self.assertEqual(lines[12], '> 13.  Track 13')
        self.assertEqual(lines[-1], '24.  Track 24')

    def test_liner_notes_do_not_render_title_markup(self):
        self.assertEqual(self.service.album_lines(['[COLOR red]Title'], 0), '> 1.  (COLOR red)Title')

    def setup_idle(self):
        self.gui.getCurrentWindowDialogId = lambda: 9999
        self.xbmc.getSkinDir.return_value = 'skin.aperture'
        self.eligible = True
        self.idle = False
        self.xbmc.getCondVisibility.side_effect = lambda condition: (
            self.idle if condition == 'System.IdleTime(60)' else self.eligible)
        return self.service.IdleShelfReturn()

    def test_idle_shelf_returns_at_sixty_seconds_without_touching_playback(self):
        timer = self.setup_idle()
        self.idle = True
        for now in (100, 159.99):
            timer.update(now)
        self.xbmc.executebuiltin.assert_not_called()
        timer.update(160)
        self.xbmc.executebuiltin.assert_called_once_with('ActivateWindow(visualisation)')
        timer.update(161)
        self.xbmc.executebuiltin.assert_called_once()
        self.xbmc.Player.assert_not_called()
        self.xbmc.PlayList.assert_not_called()

    def test_browsing_input_resets_native_idle_clock(self):
        timer = self.setup_idle()
        timer.update(0)
        timer.update(65)
        self.xbmc.executebuiltin.assert_not_called()
        self.idle = True
        timer.update(120)
        self.xbmc.executebuiltin.assert_called_once_with('ActivateWindow(visualisation)')

    def test_leaving_shelf_or_opening_dialog_requires_fresh_minute(self):
        for blocked in ('window', 'dialog', 'skin', 'playback_or_view'):
            with self.subTest(blocked=blocked):
                self.xbmc.reset_mock()
                timer = self.setup_idle()
                self.gui.getCurrentWindowId = lambda: 10502
                self.idle = True
                timer.update(0)
                if blocked == 'window': self.gui.getCurrentWindowId = lambda: 10000
                if blocked == 'dialog': self.gui.getCurrentWindowDialogId = lambda: 10120
                if blocked == 'skin': self.xbmc.getSkinDir.return_value = 'skin.estuary'
                if blocked == 'playback_or_view': self.eligible = False
                timer.update(61)
                self.xbmc.executebuiltin.assert_not_called()
                self.gui.getCurrentWindowId = lambda: 10502
                self.gui.getCurrentWindowDialogId = lambda: 9999
                self.xbmc.getSkinDir.return_value = 'skin.aperture'
                self.eligible = True
                timer.update(62)
                timer.update(121)
                self.xbmc.executebuiltin.assert_not_called()
                timer.update(122)
                self.xbmc.executebuiltin.assert_called_once()

    def test_idle_gate_requires_playing_audio_only_and_format_shelf(self):
        timer = self.setup_idle()
        timer.update(0)
        condition = self.xbmc.getCondVisibility.call_args.args[0]
        for guard in ('Player.HasAudio', '!Player.HasVideo', 'Player.Playing',
                      'Control.IsVisible(64)', 'plugin.audio.aperture.format',
                      'Aperture.FormatView),albums'):
            self.assertIn(guard, condition)

    def test_idle_api_failure_is_safe(self):
        timer = self.setup_idle()
        self.xbmc.getCondVisibility.side_effect = RuntimeError('window closing')
        timer.update(100)
        self.assertIsNone(timer.entered_at)
        self.xbmc.executebuiltin.assert_not_called()

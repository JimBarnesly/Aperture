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
                patch.object(self.service.time, 'monotonic', side_effect=[0, 0, 2, 2]):
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

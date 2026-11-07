import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


class ShelfServiceTests(unittest.TestCase):
    def setUp(self):
        self.home, self.shelf = Mock(), Mock()
        self.gui = types.SimpleNamespace(getCurrentWindowId=lambda:10502,
            Window=lambda window:self.home if window == 10000 else self.shelf)
        spec = importlib.util.spec_from_file_location('shelf_service', Path(__file__).resolve().parents[1] / 'format-kodi/shelf_service.py')
        self.service = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, xbmc=Mock(), xbmcgui=self.gui):
            spec.loader.exec_module(self.service)

    def test_selected_position_is_global_and_updates_on_reverse(self):
        item = self.shelf.getControl.return_value.getSelectedItem.return_value
        for position in ('1', '5', '3'):
            item.getProperty.return_value = position
            self.service.update_focus()
            self.home.setProperty.assert_called_with(self.service.PROPERTY, position)

    def test_other_window_and_non_format_item_do_not_change_property(self):
        self.gui.getCurrentWindowId=lambda:10000
        self.service.update_focus()
        self.home.setProperty.assert_not_called()
        self.gui.getCurrentWindowId=lambda:10502
        self.shelf.getControl.return_value.getSelectedItem.return_value.getProperty.return_value=''
        self.service.update_focus()
        self.home.setProperty.assert_not_called()

    def test_missing_control_is_harmless(self):
        self.shelf.getControl.side_effect=RuntimeError('not in this skin')
        self.service.update_focus()
        self.home.setProperty.assert_not_called()

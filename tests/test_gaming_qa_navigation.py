"""Test CI navigation choices without pretending these are real Kodi tests."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = 'plugin://plugin.games.aperture/'


class GamingNavigationTests(unittest.TestCase):
    def setUp(self):
        source = ast.parse((ROOT / 'tools/gaming_qa_service.py').read_text())
        function = next(node for node in source.body
                        if isinstance(node, ast.FunctionDef)
                        and node.name == 'open_console_cards')
        self.xbmc = SimpleNamespace(executebuiltin=Mock(), getInfoLabel=Mock(),
                                    getCondVisibility=Mock())
        self.gui = SimpleNamespace(getCurrentWindowId=Mock(return_value=10000))
        self.rpc, self.until = Mock(), Mock()
        namespace = {'xbmc': self.xbmc, 'xbmcgui': self.gui,
                     'rpc': self.rpc, 'until': self.until}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<navigation>', 'exec'), namespace)
        self.navigate = namespace['open_console_cards']

    def test_first_entry_activates_games(self):
        self.navigate()
        self.xbmc.executebuiltin.assert_called_once_with(
            'ActivateWindow(Games,' + PLUGIN_ROOT + ',return)')
        self.rpc.assert_not_called()

    def test_open_system_directory_uses_real_back(self):
        self.gui.getCurrentWindowId.return_value = 10821
        self.xbmc.getInfoLabel.return_value = PLUGIN_ROOT + '?action=system&system=nes'
        self.navigate()
        self.rpc.assert_called_once_with('Input.Back')
        self.xbmc.executebuiltin.assert_not_called()

    def test_already_at_root_does_not_reactivate_or_leave(self):
        self.gui.getCurrentWindowId.return_value = 10821
        self.xbmc.getInfoLabel.return_value = PLUGIN_ROOT
        self.navigate()
        self.rpc.assert_not_called()
        self.xbmc.executebuiltin.assert_not_called()

    def test_acceptance_requires_root_cards_without_modal(self):
        self.gui.getCurrentWindowId.return_value = 10821
        self.xbmc.getInfoLabel.return_value = PLUGIN_ROOT
        self.xbmc.getCondVisibility.side_effect = lambda condition: condition == 'Control.IsVisible(59)'
        self.navigate()
        predicate = self.until.call_args.args[1]
        self.assertTrue(predicate())
        self.xbmc.getInfoLabel.return_value = PLUGIN_ROOT + '?action=system&system=nes'
        self.assertFalse(predicate())
        self.xbmc.getInfoLabel.return_value = PLUGIN_ROOT
        self.xbmc.getCondVisibility.side_effect = lambda condition: False
        self.assertFalse(predicate())
        self.xbmc.getCondVisibility.side_effect = lambda condition: True
        self.assertFalse(predicate())


if __name__ == '__main__':
    unittest.main()

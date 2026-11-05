"""Initial-focus guards; actual history restoration is checked in native CI."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "games-kodi/resources/lib"))
from apeture_library.focus import READY_ROOT, focus_initial_system


class InitialFocusTests(unittest.TestCase):
    def setUp(self):
        self.xbmc = Mock()
        self.xbmc.getCondVisibility.return_value = True
        self.xbmc.getInfoLabel.return_value = "nes"
        self.monitor = Mock()
        self.monitor.waitForAbort.return_value = False
        self.monitor.abortRequested.return_value = False

    def test_first_parent_focus_moves_to_real_system_after_settle(self):
        self.assertTrue(focus_initial_system(self.xbmc, self.monitor))
        self.monitor.waitForAbort.assert_any_call(.4)
        self.xbmc.executebuiltin.assert_called_once_with("SetFocus(59,1,absolute)")

    def test_restored_system_or_utility_is_never_reset(self):
        self.xbmc.getCondVisibility.side_effect = lambda condition: condition != "ListItem.IsParentFolder"
        self.assertFalse(focus_initial_system(self.xbmc, self.monitor))
        self.xbmc.executebuiltin.assert_not_called()

    def test_later_user_selection_wins(self):
        self.xbmc.getCondVisibility.side_effect = [True, True, True, False]
        self.assertFalse(focus_initial_system(self.xbmc, self.monitor))
        self.xbmc.executebuiltin.assert_not_called()

    def test_new_navigation_or_modal_wins(self):
        self.xbmc.getCondVisibility.side_effect = [True, True, False]
        self.assertFalse(focus_initial_system(self.xbmc, self.monitor))
        self.xbmc.executebuiltin.assert_not_called()

    def test_wrong_window_or_view_never_receives_focus(self):
        self.xbmc.getCondVisibility.return_value = False
        self.assertFalse(focus_initial_system(self.xbmc, self.monitor))
        self.assertLessEqual(self.monitor.waitForAbort.call_count, 21)
        self.xbmc.executebuiltin.assert_not_called()

    def test_unknown_or_empty_library_never_selects_a_utility(self):
        for system in ("", "settings", "fake"):
            self.xbmc.getInfoLabel.return_value = system
            self.assertFalse(focus_initial_system(self.xbmc, self.monitor))
        self.xbmc.executebuiltin.assert_not_called()

    def test_abort_returns_without_focus(self):
        self.monitor.waitForAbort.return_value = True
        self.assertFalse(focus_initial_system(self.xbmc, self.monitor))
        self.xbmc.executebuiltin.assert_not_called()

    def test_guards_include_active_games_ready_systems_view_and_no_modal(self):
        for guard in ("Window.IsActive(10821)", "Aperture.View),systems", "Aperture.LibraryState),ready",
                      "Control.IsVisible(59)", "!System.HasModalDialog"):
            self.assertIn(guard, READY_ROOT)


if __name__ == "__main__":
    unittest.main()

"""Bounded asynchronous initial focus, after Kodi restores directory history.

Do not attach queued focus actions to the skin container: those can be evaluated
before history restoration and then overwrite a correctly restored selection.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from .catalog import SYSTEM_BY_ID

READY_ROOT = ("Window.IsActive(10821) + "
              "String.IsEqual(Container.PluginName,plugin.games.aperture) + "
              "String.IsEqual(Container.Property(Aperture.View),systems) + "
              "String.IsEqual(Container.Property(Aperture.LibraryState),ready) + "
              "Control.IsVisible(59) + !System.HasModalDialog")


def focus_initial_system(xbmc, monitor):
    # endOfDirectory wakes the GUI before its history/focus restoration ends.
    # This separate script never delays the plugin's directory callback.
    if monitor.waitForAbort(.4):
        return False
    for _ in range(20):
        if monitor.abortRequested():
            return False
        if xbmc.getCondVisibility(READY_ROOT):
            if not xbmc.getCondVisibility("ListItem.IsParentFolder"):
                return False  # Keep restored systems and intentional utilities.
            system = xbmc.getInfoLabel("Container(59).ListItem(1).Property(Aperture.System)")
            if system not in SYSTEM_BY_ID:
                return False
            # Do not override a newer navigation, modal or user selection.
            if monitor.waitForAbort(.1):
                return False
            if (xbmc.getCondVisibility(READY_ROOT)
                    and xbmc.getCondVisibility("ListItem.IsParentFolder")
                    and xbmc.getInfoLabel("Container(59).ListItem(1).Property(Aperture.System)") == system):
                xbmc.executebuiltin("SetFocus(59,1,absolute)")
                return True
            return False
        if monitor.waitForAbort(.1):
            return False
    return False

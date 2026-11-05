"""Quiet background refresh; navigation only reads durable local snapshots.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import xbmc
import xbmcaddon
import xbmcvfs

from .cache import LibraryCache, refresh
from .kodi import ADDON_ID, BASE_URL, configured_source
from .scanner import ScanCancelled, scan_library


def tick(addon, monitor):
    root, filesystem = configured_source(addon.getSetting("rom_root"))
    if not root:
        return False
    cache = LibraryCache(xbmcvfs.translatePath(addon.getAddonInfo("profile")), root)
    try:
        changed = refresh(cache, lambda: scan_library(root, filesystem, cancelled=monitor.abortRequested),
                          cancelled=monitor.abortRequested)
    except Exception:
        refresh_placeholder(addon, root, ("indexing",))
        raise
    if changed or cache.status() == "ready":
        refresh_placeholder(addon, root, ("indexing", "unavailable"))
    return changed


def refresh_placeholder(addon, root, states):
    # Only update a first-run placeholder that is still open on this source.
    # Never steal focus, reset a populated list, or navigate back after the user.
    if (configured_source(addon.getSetting("rom_root"))[0] == root
            and xbmc.getInfoLabel("Container.FolderPath").startswith(BASE_URL)
            and xbmc.getInfoLabel("Container.Property(Aperture.LibraryState)") in states
            and not xbmc.getCondVisibility("System.HasModalDialog")):
        xbmc.executebuiltin("Container.Refresh")


def run_service():
    monitor = xbmc.Monitor()
    addon = xbmcaddon.Addon(ADDON_ID)
    while not monitor.abortRequested():
        try:
            tick(addon, monitor)
        except ScanCancelled:
            break
        except Exception as exc:
            # No paths, share credentials, blocking dialogs, or repeated toasts.
            xbmc.log("Aperture: background library refresh deferred ({})".format(type(exc).__name__), xbmc.LOGWARNING)
        if monitor.waitForAbort(5):
            break

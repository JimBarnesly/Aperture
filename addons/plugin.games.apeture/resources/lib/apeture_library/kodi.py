"""Thin Kodi 21 adapter; Kodi owns RetroPlayer and game-core selection.

SPDX-License-Identifier: GPL-3.0-or-later
"""

import hashlib
import os
from urllib.parse import parse_qs, unquote, urlencode, urlsplit

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from .catalog import SYSTEM_BY_ID
from .scanner import LocalFileSystem, ScanCancelled, ScanError, filename, is_uri, scan_library

ADDON_ID = "plugin.games.apeture"
BASE_URL = "plugin://" + ADDON_ID + "/"


def game_key(game):
    # URLs/favourites must not contain configured SMB credentials or ROM paths.
    return hashlib.sha256(game.path.encode("utf-8")).hexdigest()


def url(**parameters):
    return BASE_URL + "?" + urlencode(parameters)


class KodiFileSystem:
    """SMB/NFS provider, deliberately not a downloader or archive crawler.

    Kodi VFS exposes no portable realpath or symlink flag. Confinement here is
    lexical; entry/depth budgets bound provider-side aliases and cycles.
    """

    def listdir(self, path):
        if not xbmcvfs.exists(path.rstrip("/") + "/"):
            raise OSError("VFS directory unavailable")
        return xbmcvfs.listdir(path)

    def read_text(self, path, limit):
        with xbmcvfs.File(path) as stream:
            content = bytes(stream.readBytes(limit + 1))
        if len(content) > limit:
            raise ValueError("Descriptor exceeds read limit")
        return content.decode("utf-8-sig")

    def safe(self, path, boundary):
        return path == boundary or path.startswith(boundary.rstrip("/") + "/")


def configured_source(setting):
    root = setting.strip()
    if not root:
        return "", LocalFileSystem()
    if any(ord(character) < 32 for character in root) or "|" in root:
        raise ScanError("Unsupported ROM root")
    if root.startswith("special://"):
        root = xbmcvfs.translatePath(root)
    if is_uri(root):
        parsed = urlsplit(root)
        if parsed.query or parsed.fragment:
            raise ScanError("ROM root must not contain URI options")
        if parsed.scheme == "file" and parsed.netloc in ("", "localhost"):
            root = unquote(parsed.path)
            if os.name == "nt" and len(root) > 2 and root[0] == "/" and root[2] == ":":
                root = root[1:]
        elif parsed.scheme in ("smb", "nfs") and parsed.netloc and parsed.path.strip("/"):
            if any(part in (".", "..") for part in unquote(parsed.path).split("/")):
                raise ScanError("ROM root must be a direct folder path")
            return root.rstrip("/"), KodiFileSystem()
        else:
            raise ScanError("Use a local, special://, SMB, or NFS ROM folder")
    if not os.path.isabs(root):
        raise ScanError("ROM root must be an absolute folder path")
    return os.path.normpath(root), LocalFileSystem()


class Plugin:
    def __init__(self, handle):
        self.handle = handle
        self.addon = xbmcaddon.Addon(ADDON_ID)
        self.monitor = xbmc.Monitor()

    def text(self, identifier):
        return self.addon.getLocalizedString(identifier)

    def scan(self, system_id=None):
        root, filesystem = configured_source(self.addon.getSetting("rom_root"))
        if not root:
            return scan_library("")
        progress = xbmcgui.DialogProgress()
        progress.create(self.text(32000), self.text(32010))
        try:
            return scan_library(root, filesystem,
                                cancelled=lambda: self.monitor.abortRequested() or progress.iscanceled(),
                                system_id=system_id)
        finally:
            progress.close()

    def action_item(self, label, action, special_sort=None):
        item = xbmcgui.ListItem(label=label, offscreen=True)
        item.setProperty("IsPlayable", "false")
        item.setArt({"icon": "DefaultAddonGame.png"})
        item.setProperty("Apeture.Action", action)
        item.setProperty("Apeture.Hint", self.text(32030 if action == "settings" else 32031))
        if special_sort:
            item.setProperty("SpecialSort", special_sort)
        # Game-window nonfolders are always played; actions are directories.
        return url(action=action), item, True

    def game_item(self, game, path=""):
        item = xbmcgui.ListItem(label=game.title, path=path, offscreen=True)
        item.setProperty("IsPlayable", "true")
        item.setContentLookup(False)
        tag = item.getGameInfoTag()
        tag.setTitle(game.title)
        tag.setPlatform(SYSTEM_BY_ID[game.system_id].name)
        item.setArt({"icon": "DefaultAddonGame.png"})
        item.setProperty("Apeture.System", game.system_id)
        item.setProperty("Apeture.DiscCount", str(len(game.discs) or 1))
        item.setProperty("Apeture.Hint", self.text(32032 if game.discs else 32033))
        # Do not hard-code a gameclient or invent a game MIME type. Kodi's
        # GameInfoTag marks this as a game and triggers its native core chooser.
        item.addContextMenuItems([
            (self.text(32006), "RunPlugin(" + url(action="settings") + ")"),
            (self.text(32007), "RunPlugin(" + url(action="help") + ")"),
        ])
        return item

    def directory(self, system_id=None, update=False):
        xbmcplugin.setContent(self.handle, "games")
        # A category is a location, not another copy of the add-on name.
        xbmcplugin.setPluginCategory(self.handle, self.text(32016))
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)
        items = []
        game_count = system_count = 0
        try:
            result = self.scan(system_id)
            game_count = sum(len(library.games) for library in result.libraries)
            system_count = len(result.libraries)
            state = "ready" if result.libraries else "empty"
            if not self.addon.getSetting("rom_root").strip():
                state = "unconfigured"
            if system_id:
                xbmcplugin.setPluginCategory(self.handle, SYSTEM_BY_ID[system_id].name)
                for library in result.libraries:
                    for game in library.games:
                        items.append((url(action="play", system=system_id, game=game_key(game)),
                                      self.game_item(game), False))
            else:
                for library in result.libraries:
                    item = xbmcgui.ListItem(label=library.system.name,
                                            label2=str(len(library.games)), offscreen=True)
                    item.setProperty("IsPlayable", "false")
                    item.setProperty("Apeture.System", library.system.id)
                    item.setProperty("Apeture.GameCount", str(len(library.games)))
                    item.setProperty("Apeture.Hint", self.text(32034).format(len(library.games)))
                    item.setArt({"icon": "DefaultAddonGame.png"})
                    items.append((url(action="system", system=library.system.id), item, True))
            if result.issues:
                xbmcgui.Dialog().notification(self.text(32000), self.text(32012),
                                             xbmcgui.NOTIFICATION_WARNING)
                # Never log a ROM path or an SMB URL (which may have credentials).
                xbmc.log("Apeture: {} scan issue(s); some entries skipped".format(len(result.issues)), xbmc.LOGWARNING)
            if state != "ready":
                items.append(self.action_item(self.text(32004 if state == "unconfigured" else 32005), "settings", "top"))
        except ScanCancelled:
            xbmcplugin.setProperty(self.handle, "Apeture.LibraryState", "cancelled")
            xbmcplugin.endOfDirectory(self.handle, succeeded=False, cacheToDisc=False)
            return
        except (ScanError, OSError, IOError, ValueError) as exc:
            state = "error"
            self.error(exc)
            items.append(self.action_item(self.text(32006), "settings", "top"))
        if state == "ready":
            items.append(self.action_item(self.text(32006), "settings", "bottom"))
        items.append(self.action_item(self.text(32007), "help", "bottom"))
        headings = {"unconfigured": 32017, "empty": 32019, "error": 32021, "ready": 32023}
        descriptions = {"unconfigured": 32018, "empty": 32020, "error": 32022, "ready": 32024}
        xbmcplugin.setProperty(self.handle, "Apeture.Heading", self.text(headings[state]))
        xbmcplugin.setProperty(self.handle, "Apeture.Description", self.text(descriptions[state]))
        xbmcplugin.setProperty(self.handle, "Apeture.Directory", "system" if system_id else "root")
        xbmcplugin.setProperty(self.handle, "Apeture.GameCount", str(game_count))
        xbmcplugin.setProperty(self.handle, "Apeture.SystemCount", str(system_count))
        summary = self.text(32025 if system_id else 32026).format(game_count, system_count)
        if state != "ready":
            summary = self.text({"unconfigured": 32027, "empty": 32028, "error": 32029}[state])
        xbmcplugin.setProperty(self.handle, "Apeture.Summary", summary)
        xbmcplugin.setProperty(self.handle, "Apeture.LibraryState", state)
        xbmcplugin.addDirectoryItems(self.handle, items, totalItems=len(items))
        xbmcplugin.endOfDirectory(self.handle, succeeded=True, updateListing=update, cacheToDisc=False)

    def error(self, exc):
        xbmc.log("Apeture: operation failed ({})".format(type(exc).__name__), xbmc.LOGERROR)
        xbmcgui.Dialog().ok(self.text(32000), self.text(32011))

    def play(self, system_id, key):
        try:
            result = self.scan(system_id)
            game = next((game for library in result.libraries for game in library.games
                         if game_key(game) == key), None)
            if game is None:
                xbmcgui.Dialog().ok(self.text(32000), self.text(32013))
                xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
                return
            path = game.path
            if game.discs:
                selected = xbmcgui.Dialog().select(self.text(32014),
                                                   [filename(disc) for disc in game.discs])
                if selected < 0:
                    raise ScanCancelled()
                path = game.discs[selected]
            xbmcplugin.setResolvedUrl(self.handle, True, self.game_item(game, path))
        except ScanCancelled:
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
        except (ScanError, OSError, IOError, ValueError) as exc:
            self.error(exc)
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())


def run(argv):
    handle = int(argv[1])
    plugin = Plugin(handle)
    action = "root"
    try:
        query = argv[2].lstrip("?") if len(argv) > 2 else ""
        if len(query) > 4096:
            raise ValueError("Plugin query is too long")
        parameters = parse_qs(query, max_num_fields=12)
        action = parameters.get("action", ["root"])[0]
        system_id = parameters.get("system", [""])[0]
        if action == "play":
            plugin.play(system_id, parameters.get("game", [""])[0])
        elif action == "system" and system_id in SYSTEM_BY_ID:
            plugin.directory(system_id)
        elif action == "settings":
            plugin.addon.openSettings()
            if handle >= 0:
                plugin.directory(update=True)
            else:
                # Skin/context actions run with no directory handle. Refresh
                # only after the modal settings editor has returned.
                xbmc.executebuiltin("Container.Refresh")
        elif action == "help":
            xbmcgui.Dialog().ok(plugin.text(32007), plugin.text(32008))
            if handle >= 0:
                plugin.directory(update=True)
        elif action == "root":
            plugin.directory()
        else:
            xbmcgui.Dialog().ok(plugin.text(32000), plugin.text(32015))
            if handle >= 0:
                plugin.directory(update=True)
    except Exception as exc:  # Kodi must always receive a terminal callback.
        plugin.error(exc)
        if handle >= 0:
            if action == "play":
                xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
            else:
                xbmcplugin.endOfDirectory(handle, succeeded=False, cacheToDisc=False)

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

from .cache import LibraryCache
from .catalog import SYSTEM_BY_ID
from .scanner import LocalFileSystem, ScanCancelled, ScanError, filename, is_uri, scan_library

ADDON_ID = "plugin.games.aperture"
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

    def exists(self, path):
        return xbmcvfs.exists(path)

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

    def cache(self):
        root, filesystem = configured_source(self.addon.getSetting("rom_root"))
        profile = xbmcvfs.translatePath(self.addon.getAddonInfo("profile"))
        return LibraryCache(profile, root), filesystem

    def library(self, system_id=None):
        cache, _ = self.cache()
        if not cache.root:
            from .scanner import ScanResult
            return ScanResult((), ()), "unconfigured"
        snapshot = cache.load()
        if snapshot is None:
            state = cache.status()
            if state == "ready":
                # Publication may have completed between the first read and
                # status read. Do not queue a duplicate scan for that race.
                snapshot = cache.load()
                if snapshot is None:
                    if not cache.request_path.exists():
                        cache.request_refresh()
                    state = "indexing"
            if snapshot is None:
                from .scanner import ScanResult
                return ScanResult((), ()), state
        result, _ = snapshot
        if system_id:
            from .scanner import ScanResult
            result = ScanResult(tuple(library for library in result.libraries
                                      if library.system.id == system_id), ())
        return result, "ready" if result.libraries else "empty"

    def action_item(self, label, action, special_sort=None):
        item = xbmcgui.ListItem(label=label, offscreen=True)
        item.setProperty("IsPlayable", "false")
        item.setProperty("Aperture.Action", action)
        item.setArt({"icon": "DefaultAddonGame.png"})
        if special_sort:
            item.setProperty("SpecialSort", special_sort)
        # Game-window nonfolders are always played; actions are directories.
        return url(action=action), item, True

    def game_item(self, game, path=""):
        item = xbmcgui.ListItem(label=game.title, path=path, offscreen=True)
        item.setProperty("IsPlayable", "true")
        item.setContentLookup(False)
        if path:
            tag = item.getGameInfoTag()
            tag.setTitle(game.title)
            tag.setPlatform(SYSTEM_BY_ID[game.system_id].name)
        item.setArt(dict({"icon": "DefaultAddonGame.png"}, **dict(game.artwork)))
        item.setProperty("Aperture.System", game.system_id)
        item.setProperty("Aperture.SystemName", SYSTEM_BY_ID[game.system_id].name)
        item.setProperty("Aperture.DiscCount", str(len(game.discs) or 1))
        # Do not hard-code a gameclient or invent a game MIME type. Kodi's
        # GameInfoTag marks this as a game and triggers its native core chooser.
        item.addContextMenuItems([
            (self.text(32006), "Addon.OpenSettings(" + ADDON_ID + ")"),
            (self.text(32007), "RunPlugin(" + url(action="help") + ")"),
        ])
        return item

    def launch_item(self, game):
        item = self.game_item(game)
        item.setProperty("IsPlayable", "false")
        return item

    def finish_action(self):
        if self.handle >= 0:
            xbmcplugin.endOfDirectory(self.handle, succeeded=False, cacheToDisc=False)

    def directory(self, system_id=None, update=False):
        xbmcplugin.setProperty(self.handle, "Aperture.View", "games" if system_id else "systems")
        xbmcplugin.setContent(self.handle, "games")
        xbmcplugin.setPluginCategory(self.handle, self.text(32000))
        items = []
        try:
            result, state = self.library(system_id)
            if system_id:
                xbmcplugin.setPluginCategory(self.handle, SYSTEM_BY_ID[system_id].name)
                for library in result.libraries:
                    for game in library.games:
                        items.append((url(action="play", system=system_id, game=game_key(game)),
                                      self.launch_item(game), True))
            else:
                for library in result.libraries:
                    item = xbmcgui.ListItem(label=library.system.name,
                                            label2="", offscreen=True)
                    item.setProperty("IsPlayable", "false")
                    item.setProperty("Aperture.System", library.system.id)
                    item.setProperty("Aperture.SystemName", library.system.name)
                    item.setProperty("Aperture.GameCount", str(len(library.games)))
                    item.setArt({"icon": "DefaultAddonGame.png"})
                    items.append((url(action="system", system=library.system.id), item, True))
            if state in ("indexing", "unavailable"):
                items.append(self.action_item(self.text(32017 if state == "indexing" else 32018), "root", "top"))
            if state in ("unconfigured", "empty"):
                items.append(self.action_item(self.text(32004 if state == "unconfigured" else 32005), "settings", "top"))
        except ScanCancelled:
            xbmcplugin.setProperty(self.handle, "Aperture.LibraryState", "cancelled")
            xbmcplugin.endOfDirectory(self.handle, succeeded=False, cacheToDisc=False)
            return
        except (ScanError, OSError, IOError, ValueError) as exc:
            state = "error"
            self.error(exc)
            items.append(self.action_item(self.text(32006), "settings", "top"))
        if state in ("ready", "unavailable", "indexing"):
            items.append(self.action_item(self.text(32006), "settings", "bottom"))
        if self.addon.getSetting("rom_root").strip():
            items.append(self.action_item(self.text(32016), "refresh", "bottom"))
        items.append(self.action_item(self.text(32007), "help", "bottom"))
        xbmcplugin.setProperty(self.handle, "Aperture.LibraryState", state)
        xbmcplugin.addDirectoryItems(self.handle, items, totalItems=len(items))
        xbmcplugin.endOfDirectory(self.handle, succeeded=True, updateListing=update, cacheToDisc=False)
        if xbmc.getSkinDir() == "skin.aperture":
            xbmc.executebuiltin("Container.SetViewMode({})".format(60 if system_id else 59))
            if not system_id and state == "ready":
                # A separate bounded script waits until Kodi has restored the
                # prior directory selection. Never queue this on container focus.
                script = os.path.join(self.addon.getAddonInfo("path"), "focus.py")
                xbmc.executebuiltin('RunScript("{}")'.format(script))

    def error(self, exc):
        xbmc.log("Aperture: operation failed ({})".format(type(exc).__name__), xbmc.LOGERROR)
        xbmcgui.Dialog().ok(self.text(32000), self.text(32011))

    def play(self, system_id, key):
        try:
            result, _ = self.library(system_id)
            game = next((game for library in result.libraries for game in library.games
                         if game_key(game) == key), None)
            if game is None:
                xbmcgui.Dialog().ok(self.text(32000), self.text(32013))
                self.finish_action()
                return
            path = game.path
            if game.discs:
                selected = xbmcgui.Dialog().select(self.text(32014),
                                                   [filename(disc) for disc in game.discs])
                if selected < 0:
                    raise ScanCancelled()
                path = game.discs[selected]
            cache, filesystem = self.cache()
            from .scanner import validate_launch
            if not validate_launch(path, cache.root, system_id, filesystem):
                xbmcgui.Dialog().ok(self.text(32000), self.text(32013))
                self.finish_action()
                return
            # Kodi 21's resolver keeps the plugin URL as Path; RetroPlayer
            # requires the actual local ROM as Path, not merely DynPath.
            self.finish_action()
            xbmc.Player().play(path, self.game_item(game, path))
        except ScanCancelled:
            self.finish_action()
        except (ScanError, OSError, IOError, ValueError) as exc:
            self.error(exc)
            self.finish_action()


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
        elif action == "refresh":
            cache, _ = plugin.cache()
            if cache.root:
                cache.request_refresh()
                xbmcgui.Dialog().notification(plugin.text(32000), plugin.text(32019))
            if handle >= 0:
                plugin.directory(update=True)
        elif action == "settings":
            plugin.addon.openSettings()
            if handle >= 0:
                plugin.directory(update=True)
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
            xbmcplugin.endOfDirectory(handle, succeeded=False, cacheToDisc=False)

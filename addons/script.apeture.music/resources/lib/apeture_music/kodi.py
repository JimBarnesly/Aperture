# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Kodi window and playback; all RPC stays inside the Kodi process."""
import random

import xbmc
import xbmcaddon
import xbmcgui

from .library import Library, LibraryError
from .model import Shelf

ADDON_ID = "script.apeture.music"
BACK = (9, 10, 92)
LEFT, RIGHT, PLAYER_PLAY = 1, 2, 79
SHELF, PREVIOUS, NEXT, LIBRARY, HOME, RETRY = 100, 101, 102, 200, 201, 202


def prepare_items(album, songs):
    """Prepare before replacing a queue. Paths are never interpolated in builtins."""
    prepared = []
    for song in songs:
        item = xbmcgui.ListItem(label=song.title, path=song.file, offscreen=True)
        item.setContentLookup(False)
        tag = item.getMusicInfoTag()
        tag.setDbId(song.id, "song")
        tag.setTitle(song.title)
        tag.setAlbum(album.title)
        tag.setArtist(" / ".join(song.artists) or album.artist)
        tag.setAlbumArtist(" / ".join(song.album_artists) or album.artist)
        tag.setDisc(song.disc)
        tag.setTrack(song.track)
        tag.setDuration(song.duration)
        if album.art:
            item.setArt({"thumb": album.art})
        prepared.append((song.file, item))
    return prepared


def play_album(album, library):
    songs = library.songs(album.id)
    if not songs:
        raise LibraryError("This album has no playable tracks. Check its source in Kodi Music.")
    if len({song.file for song in songs}) != len(songs):
        # JSON-RPC raw file URLs omit native cue offsets. Do not replay a whole
        # shared file for every cue track; let native Kodi Music handle it.
        raise LibraryError("Shared-file albums need native Kodi Music playback.")
    prepared = prepare_items(album, songs)
    playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
    # Only explicit OK/Play changes playback. Browsing and loading never do.
    playlist.clear()
    for path, item in prepared:
        playlist.add(path, item)
    playlist.unshuffle()
    xbmc.Player().play(playlist, startpos=0)
    return len(prepared)


class AlbumWindow(xbmcgui.WindowXML):
    def configure(self, library, rng):
        self.library = library
        self.rng = rng
        self.shelf = Shelf([], None, rng)
        self.initialized = False
        self.busy = False
        self.destination = None

    def onInit(self):
        if self.initialized:
            return
        self.initialized = True
        self.setProperty("Shelf.Backdrop", "special://skin/media/apeture/misty-stone-bridge.png"
                         if xbmc.getSkinDir() == "skin.apeture" else "shelf/background.png")
        self.load()

    def load(self):
        if self.busy:
            return
        self.busy = True
        self.setProperty("Shelf.Ready", "")
        self.setProperty("Shelf.Primary", "Open Kodi Music")
        self.setProperty("Shelf.Status", "Opening your record shelf…")
        self.setProperty("Shelf.Detail", "Reading albums already in your Kodi music library.")
        self.setProperty("Shelf.Error", "")
        try:
            albums = self.library.albums()
            current = self.library.playing_album()
            self.shelf = Shelf(albums, current, self.rng)
            if self.shelf.current:
                self.setProperty("Shelf.Ready", "true")
                self.setProperty("Shelf.Primary", "Play album")
                self.setProperty("Shelf.Status", "")
                self.setProperty("Shelf.Detail", "")
                self.render()
                self.setFocusId(SHELF)
            else:
                self.setProperty("Shelf.Status", "Your shelf is waiting.")
                self.setProperty("Shelf.Detail", "Add your music in Kodi Music, then scan it into the library.[CR]Come back when a few records have found their place.")
                self.setFocusId(LIBRARY)
        except Exception:
            # Callback exceptions do not reliably reach the doModal caller.
            self.shelf = Shelf([], None, self.rng)
            self.setProperty("Shelf.Ready", "")
            self.setProperty("Shelf.Primary", "Open Kodi Music")
            self.setProperty("Shelf.Error", "true")
            self.setProperty("Shelf.Status", "The shelf could not be opened.")
            self.setProperty("Shelf.Detail", "Your music has not been changed.[CR]Try again, open Kodi Music, or head back home.")
            self.setFocusId(RETRY)
        finally:
            self.busy = False

    def render(self):
        album = self.shelf.current
        if not album:
            return
        for offset in range(-3, 4):
            neighbor = self.shelf.neighbor(offset)
            prefix = "Shelf.Cover{}".format(offset + 3)
            self.setProperty(prefix + ".Visible", "true" if neighbor else "")
            self.setProperty(prefix + ".Art", neighbor.art or "shelf/placeholder.png" if neighbor else "")
        self.setProperty("Shelf.Title", album.title)
        self.setProperty("Shelf.Artist", album.artist)
        self.setProperty("Shelf.Year", str(album.year) if album.year else "")
        self.setProperty("Shelf.Position", "{} / {}".format(self.shelf.index + 1, len(self.shelf.albums)))

    def move(self, delta):
        if not self.busy:
            self.shelf.move(delta)
            self.render()

    def play(self):
        if self.busy or not self.shelf.current:
            return
        self.busy = True
        try:
            play_album(self.shelf.current, self.library)
        except LibraryError:
            xbmcgui.Dialog().ok("Apeture Album Shelf", "This album could not be played. Check its tracks and source in Kodi Music, then try again.")
        except Exception:
            xbmcgui.Dialog().ok("Apeture Album Shelf", "Kodi could not start this album. Open Kodi Music to check playback.")
        finally:
            self.busy = False

    def onClick(self, control_id):
        if control_id == SHELF:
            if self.shelf.current:
                self.play()
            else:
                self.destination = "library"
                self.close()
        elif control_id == PREVIOUS:
            self.move(-1)
        elif control_id == NEXT:
            self.move(1)
        elif control_id == RETRY:
            self.load()
        elif control_id in (HOME, LIBRARY):
            self.destination = "library" if control_id == LIBRARY else "home"
            self.close()

    def onAction(self, action):
        action_id = action.getId()
        if action_id in BACK:
            self.close()
            return
        if action_id == PLAYER_PLAY:
            self.play()
            return
        try:
            focus = self.getFocusId()
        except RuntimeError:
            return
        # The centre button self-targets left/right in XML. Kodi handles normal
        # focus navigation first, then this callback, with exactly one shelf step.
        if focus == SHELF:
            if action_id == LEFT:
                self.move(-1)
            elif action_id == RIGHT:
                self.move(1)


def run():
    home = xbmcgui.Window(10000)
    # Repeated RunScript presses must not stack modal copies of the shelf.
    if home.getProperty("Apeture.Music.Open"):
        return
    home.setProperty("Apeture.Music.Open", "true")
    window = None
    destination = None
    try:
        addon = xbmcaddon.Addon(ADDON_ID)
        monitor = xbmc.Monitor()
        library = Library(xbmc.executeJSONRPC, monitor.abortRequested)
        window = AlbumWindow("script-apeture-music.xml", addon.getAddonInfo("path"), "Default", "1080i")
        window.configure(library, random.SystemRandom())
        window.doModal()
        destination = window.destination
    except Exception:
        xbmcgui.Dialog().ok("Apeture Album Shelf", "The album shelf is unavailable. Your music is still accessible from Kodi Music.")
        destination = "library"
    finally:
        if window is not None:
            del window
        home.clearProperty("Apeture.Music.Open")
    if destination == "library":
        xbmc.executebuiltin("ActivateWindow(Music,root,return)")
    elif destination == "home":
        xbmc.executebuiltin("ActivateWindow(Home)")

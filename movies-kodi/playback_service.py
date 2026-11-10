"""Movies-only fullscreen exit policy; independent of Format and keymaps."""
import json

import xbmc
import xbmcgui


class MoviePauseOnExit:
    def __init__(self):
        self.was_fullscreen = False

    def update(self):
        window = xbmcgui.getCurrentWindowId()
        fullscreen = window == 12005
        # Use the underlying window, not focused dialogs/OSD. Fail closed for
        # unknown windows; only Home and native media browsing are exits.
        browsing = window in (10000, 10001, 10002, 10025, 10500, 10501, 10502, 10800)
        eligible = (xbmc.getCondVisibility('Player.HasVideo')
                    and xbmc.getCondVisibility('VideoPlayer.Content(movies)')
                    and xbmc.getCondVisibility('Player.Playing'))
        if self.was_fullscreen and browsing and eligible:
            # Explicit false is idempotent; never toggle a paused player to play.
            xbmc.executeJSONRPC(json.dumps({
                'jsonrpc': '2.0', 'id': 1, 'method': 'Player.PlayPause',
                'params': {'playerid': 1, 'play': False},
            }))
        if not eligible or browsing:
            self.was_fullscreen = False
        elif fullscreen:
            self.was_fullscreen = True
        # An intervening transient dialog/window neither arms nor disarms.


def history_monitor():
    import os
    import xbmcaddon
    import xbmcvfs
    from resources.lib.movie_history import HistoryStore
    from resources.lib.history_playback import HistoryMonitor
    profile = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
    return HistoryMonitor(HistoryStore(os.path.join(profile, 'history-private')),
                          xbmc.Player(), xbmcgui.Window(10000),
                          notify=lambda: xbmcgui.Dialog().notification(
                              'Movies', 'History unavailable; playback is unaffected.'))


def run():
    monitor = xbmc.Monitor()
    guard = MoviePauseOnExit()
    history = history_monitor()
    while not monitor.abortRequested():
        history.update()
        try:
            guard.update()
        except RuntimeError:
            # Kodi may tear down the player/window between samples. Disarm,
            # don't log private details or retry an uncertain pause command.
            guard = MoviePauseOnExit()
        if monitor.waitForAbort(0.1):
            break
    history.close()


if __name__ == '__main__':
    run()

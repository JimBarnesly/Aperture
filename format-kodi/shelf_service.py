"""Publish shelf focus outside Kodi's per-item rendering context.

Container integer infos can resolve against a neighbour while item layouts are
being rendered. A window property gives both sides one stable selected index.
This service never performs network requests or changes navigation/playback.
It also manages one dedicated turntable-only keymap while Aperture is selected.
"""
import time

import xbmc
import xbmcgui

PROPERTY = 'Aperture.FormatSelectedPosition'


def update_focus():
    home = xbmcgui.Window(10000)
    try:
        if xbmcgui.getCurrentWindowId() != 10502:
            return
        position = xbmc.getInfoLabel(
            'Container(64).ListItem.Property(Aperture.FormatPosition)')
        if position.isdigit() and home.getProperty(PROPERTY) != position:
            home.setProperty(PROPERTY, position)
    except (RuntimeError, AttributeError):
        # Other skins and non-Format music views need no shelf state.
        pass


def album_lines(titles, current):
    """Plain liner notes retain every track, with a current-track marker."""
    return '\n'.join(('> ' if i == current else '') + str(i + 1) + '.  '
                     + str(title).replace('[', '(').replace(']', ')')
                     for i, title in enumerate(titles))


def update_liner_notes():
    if xbmcgui.getCurrentWindowId() != 12006:
        return
    home = xbmcgui.Window(10000)
    try:
        count = int(xbmc.getInfoLabel('Playlist.Length(music)') or '0')
        if count <= 10:
            return
        current = xbmc.PlayList(xbmc.PLAYLIST_MUSIC).getposition()
        titles = [xbmc.getInfoLabel('MusicPlayer.Position({}).Title'.format(i))
                  for i in range(count)]
        text = album_lines(titles, current)
        if home.getProperty('Aperture.FormatAlbumTracks') != text:
            home.setProperty('Aperture.FormatAlbumTracks', text)
    except (ValueError, RuntimeError, AttributeError):
        pass


def run():
    # Import here so the shelf helpers remain independently testable.
    from pathlib import Path
    import xbmcvfs
    from turntable_keymap import TurntableKeymap
    keymap = TurntableKeymap(
        xbmcvfs.translatePath('special://profile/keymaps/'),
        Path(__file__).parent / 'resources/keymaps/aperture-turntable.xml',
        lambda: xbmc.executebuiltin('Action(reloadkeymaps)'),
        lambda message: xbmc.log(message, xbmc.LOGWARNING))
    monitor = xbmc.Monitor()
    next_liner_update = 0.0
    try:
        while not monitor.abortRequested():
            update_focus()
            keymap.sync(xbmc.getSkinDir() == 'skin.aperture')
            if time.monotonic() >= next_liner_update:
                update_liner_notes()
                next_liner_update = time.monotonic() + 1.0
            if monitor.waitForAbort(0.05):
                break
    finally:
        keymap.close()


if __name__ == '__main__':
    run()

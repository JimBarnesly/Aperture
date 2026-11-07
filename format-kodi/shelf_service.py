"""Publish shelf focus outside Kodi's per-item rendering context.

Container integer infos can resolve against a neighbour while item layouts are
being rendered. A window property gives both sides one stable selected index.
This service never performs network requests or changes navigation/playback.
"""
import xbmc
import xbmcgui

PROPERTY = 'Aperture.FormatSelectedPosition'


def update_focus():
    home = xbmcgui.Window(10000)
    try:
        if xbmcgui.getCurrentWindowId() != 10502:
            return
        shelf = xbmcgui.Window(10502).getControl(64)
        item = shelf.getSelectedItem()
        position = item.getProperty('Aperture.FormatPosition') if item else ''
        if position.isdigit() and home.getProperty(PROPERTY) != position:
            home.setProperty(PROPERTY, position)
    except (RuntimeError, AttributeError):
        # Other skins and non-Format music views need no shelf state.
        pass


def run():
    monitor = xbmc.Monitor()
    while not monitor.abortRequested():
        update_focus()
        if monitor.waitForAbort(0.05):
            break


if __name__ == '__main__':
    run()

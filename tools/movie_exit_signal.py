"""Latch native fullscreen exits; the Movies service still owns pause policy."""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

PROPERTY = 'Aperture.Movies.FullscreenExit'
BROWSERS = (10000, 10001, 10002, 10025, 10500, 10501, 10502, 10800, 11120)


def apply(skin):
    osd = Path(skin) / 'xml/VideoOSD.xml'
    if osd.exists():
        tree = ET.parse(osd)
        group = tree.getroot().find('.//control[@id="201"]')
        if group is not None:
            for old in group.findall('control[@id="699"]'):
                group.remove(old)
            button = ET.SubElement(group, 'control', type='button', id='699')
            fields = {'width': '240', 'height': '74', 'label': 'Change source', 'font': 'font20_title',
                      'texturefocus': 'aperture/movies/accent.png',
                      'texturenofocus': 'aperture/movies/plate.png',
                      'textcolor': 'FFE8F2F3', 'focusedcolor': 'FF102C35',
                      'visible': 'Player.HasVideo + VideoPlayer.Content(movies) + !String.IsEmpty(VideoPlayer.UniqueID(aperture_movie))',
                      'onclick': 'RunPlugin(plugin://plugin.video.aperture.movies/?action=torrentio_change)'}
            for name, value in fields.items():
                ET.SubElement(button, name).text = value
            tree.write(osd, encoding='utf-8', xml_declaration=True)
    path = Path(skin) / 'xml/VideoFullScreen.xml'
    # Minimal build fixtures can omit this inherited window.
    if not path.exists():
        return
    tree = ET.parse(path)
    root = tree.getroot()
    clear = 'ClearProperty(' + PROPERTY + ',home)'
    signal = 'SetProperty(' + PROPERTY + ',$INFO[VideoPlayer.UniqueID(aperture_session)],home)'
    for node in list(root):
        if node.tag in ('onload', 'onunload') and node.text in (clear, signal):
            root.remove(node)
    ET.SubElement(root, 'onload').text = clear
    condition = ('Player.HasVideo + VideoPlayer.Content(movies) + '
                 '!String.IsEmpty(VideoPlayer.UniqueID(aperture_session)) + [' +
                 ' | '.join('Window.Next(%d)' % window for window in BROWSERS) + ']')
    ET.SubElement(root, 'onunload', condition=condition).text = signal
    tree.write(path, encoding='utf-8', xml_declaration=True)


if __name__ == '__main__':
    apply(Path(sys.argv[1]))

"""Latch native fullscreen exits; the Movies service still owns pause policy."""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

PROPERTY = 'Aperture.Movies.FullscreenExit'
BROWSERS = (10000, 10001, 10002, 10025, 10500, 10501, 10502, 10800, 11120)


def apply(skin):
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

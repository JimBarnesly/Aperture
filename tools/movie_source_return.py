"""Scope native Back to Movies home only for its marked source directory."""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

PREFIX = 'plugin://plugin.video.aperture.movies/?action=torrentio_sources&home=1&'
CONDITION = ('Window.IsActive(videos) + !System.HasVisibleModalDialog + '
             'String.IsEqual(Container.PluginName,plugin.video.aperture.movies) + '
             'String.StartsWith(Container.FolderPath,' + PREFIX + ')')
ACTION = 'RunPlugin(plugin://plugin.video.aperture.movies/?action=home_source_back)'
# Includes can define controls in another XML file. Patch interactive controls,
# not groups (Omega's CGUIControlGroup::OnAction always returns false).
INTERACTIVE = {'list', 'fixedlist', 'wraplist', 'panel', 'scrollbar', 'button',
               'togglebutton', 'radiobutton', 'spincontrol', 'spincontrolex',
               'edit', 'slider', 'settingsslider'}


def apply(skin):
    xml = Path(skin) / 'xml'
    # Native views and their shared side-menu includes only. Do not rewrite
    # custom Home/Music/Games windows or modal dialogs.
    for path in sorted(set(xml.glob('View_*.xml')) | set(xml.glob('Includes*.xml'))):
        tree = ET.parse(path)
        changed = False
        for control in tree.iter('control'):
            if control.get('type') not in INTERACTIVE:
                continue
            if any(node.text == ACTION for node in control.findall('onback')):
                continue
            for node in control.findall('onback'):
                previous = node.get('condition')
                node.set('condition', '![' + CONDITION + ']' +
                         (' + [' + previous + ']' if previous else ''))
            ET.SubElement(control, 'onback', condition=CONDITION).text = ACTION
            # OnMove returns false for an action-only onback, falling through to
            # native PreviousWindow before the script runs. Focus the native
            # menu group to consume this key; the script then replaces Videos.
            ET.SubElement(control, 'onback', condition=CONDITION).text = '9000'
            changed = True
        if changed:
            tree.write(path, encoding='utf-8', xml_declaration=True)


if __name__ == '__main__':
    apply(Path(sys.argv[1]))

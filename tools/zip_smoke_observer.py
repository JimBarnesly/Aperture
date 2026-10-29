"""Read-only state for fresh ZIP acceptance. No setters, actions or listeners."""
import json
import os
from pathlib import Path
import time
import traceback
import xbmc
import xbmcaddon
import xbmcgui

SUBJECTS = ('plugin.games.apeture', 'script.apeture.music', 'skin.apeture')


def control_text(window, identifier):
    try:
        control = window.getControl(identifier)
        for method in ('getLabel', 'getText'):
            if hasattr(control, method):
                return getattr(control, method)()
    except (RuntimeError, TypeError, ValueError):
        pass
    return ''


def observe(sequence):
    current, dialog = xbmcgui.getCurrentWindowId(), xbmcgui.getCurrentWindowDialogId()
    window = xbmcgui.Window(dialog if dialog != 9999 else current)
    try:
        focus = window.getFocusId()
    except (RuntimeError, ValueError):
        focus = -1
    installed = {}
    for identifier in SUBJECTS:
        if not xbmc.getCondVisibility('System.HasAddon(' + identifier + ')'):
            continue
        try:
            addon = xbmcaddon.Addon(identifier)
            installed[identifier] = {'version': addon.getAddonInfo('version'), 'name': addon.getAddonInfo('name'), 'path': addon.getAddonInfo('path'),
                'enabled': bool(xbmc.getCondVisibility('System.AddonIsEnabled(' + identifier + ')'))}
        except RuntimeError:
            pass
    reply = json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1,
        'method': 'Settings.GetSettingValue', 'params': {'setting': 'addons.unknownsources'}})))
    if 'error' in reply:
        raise RuntimeError('Cannot observe Unknown sources setting')
    return {'sequence': sequence, 'time': time.time(), 'pid': os.getpid(),
        'skin': xbmc.getSkinDir(), 'window': current, 'dialog': dialog, 'focus': focus,
        'control_label': xbmc.getInfoLabel('System.CurrentControl'), 'list_item': xbmc.getInfoLabel('ListItem.Label'),
        'heading': control_text(window, 1) or control_text(window, 411), 'text': control_text(window, 9),
        'unknown_sources': reply['result']['value'], 'installed': installed,
        'folder': xbmc.getInfoLabel('Container.FolderPath'),
        'library_state': xbmc.getInfoLabel('Container.Property(Apeture.LibraryState)'),
        'music_open': xbmcgui.Window(10000).getProperty('Apeture.Music.Open'),
        'width': xbmcgui.getScreenWidth(), 'height': xbmcgui.getScreenHeight()}


def main():
    out = Path(os.environ['APETURE_ZIP_OUT'])
    monitor = xbmc.Monitor()
    sequence = 0
    with (out / 'states.jsonl').open('a', encoding='utf-8', buffering=1) as history:
        while not monitor.abortRequested():
            sequence += 1
            payload = json.dumps(observe(sequence), ensure_ascii=False)
            history.write(payload + '\n')
            temporary = out / 'state.tmp'
            temporary.write_text(payload, encoding='utf-8')
            temporary.replace(out / 'state.json')
            if monitor.waitForAbort(0.15):
                break


if __name__ == '__main__':
    try:
        main()
    except Exception:
        (Path(os.environ['APETURE_ZIP_OUT']) / 'observer-error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise

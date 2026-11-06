"""Read-only state for fresh ZIP acceptance. No setters, actions or listeners."""
import json
import os
from pathlib import Path
import time
import threading
import traceback
import xbmc
import xbmcaddon
import xbmcgui

SUBJECTS = ('plugin.audio.aperture.format', 'plugin.video.aperture.movies', 'skin.aperture')



class SettingsReader:
    """A setting read can wait behind Kodi's modal confirmation setting lock.

    Keep it off the GUI observation loop, so the driver can see and answer that
    native dialog. This is a read-only in-process RPC, not a network endpoint.
    Cached values carry their actual read timestamps and are never presumed fresh.
    """
    def __init__(self, monitor):
        self.monitor = monitor
        self.value = {'unknown_sources': None, 'unknown_sources_read_started': 0,
                      'unknown_sources_read_completed': 0}
        self.error = None
        self.thread = threading.Thread(target=self.run, name='zip-settings-reader', daemon=True)

    def run(self):
        try:
            while not self.monitor.abortRequested():
                started = time.time()
                reply = json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1,
                    'method': 'Settings.GetSettingValue', 'params': {'setting': 'addons.unknownsources'}})))
                if 'error' in reply or type(reply.get('result', {}).get('value')) is not bool:
                    raise RuntimeError('Cannot observe Unknown sources setting')
                self.value = {'unknown_sources': reply['result']['value'],
                              'unknown_sources_read_started': started,
                              'unknown_sources_read_completed': time.time()}
                if self.monitor.waitForAbort(0.15):
                    break
        except Exception:
            self.error = traceback.format_exc()

    def snapshot(self):
        if self.error:
            raise RuntimeError(self.error)
        return dict(self.value)


def observe(sequence, settings):
    current, dialog = xbmcgui.getCurrentWindowId(), xbmcgui.getCurrentWindowDialogId()
    # Native dialogs can be destroyed between observer calls. Holding a Python
    # Window/control proxy across that transition crashed Kodi GetControlById.
    # Resolve each read through the GUI info manager instead of raw proxies.
    try:
        focus = int(xbmc.getInfoLabel('System.CurrentControlId'))
    except (TypeError, ValueError):
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
    return {'sequence': sequence, 'time': time.time(), 'pid': os.getpid(),
        'skin': xbmc.getSkinDir(), 'window': current, 'dialog': dialog, 'focus': focus,
        'control_label': xbmc.getInfoLabel('System.CurrentControl'), 'list_item': xbmc.getInfoLabel('ListItem.Label'),
        'dialog_text': ' '.join(xbmc.getInfoLabel('Control.GetLabel(' + str(control) + ')')
                                for control in (1, 9, 10)) if dialog == 12002 else '',
        **settings.snapshot(), 'installed': installed,
        'folder': xbmc.getInfoLabel('Container.FolderPath'),
        'item_path': xbmc.getInfoLabel('ListItem.FileNameAndPath'),
        'item_is_folder': bool(xbmc.getCondVisibility('ListItem.IsFolder')),
        'item_is_parent': bool(xbmc.getCondVisibility('ListItem.IsParentFolder')),
        'width': xbmcgui.getScreenWidth(), 'height': xbmcgui.getScreenHeight()}


def main():
    out = Path(os.environ['APERTURE_ZIP_OUT'])
    monitor = xbmc.Monitor()
    sequence = 0
    settings = SettingsReader(monitor)
    settings.thread.start()
    with (out / 'states.jsonl').open('a', encoding='utf-8', buffering=1) as history:
        while not monitor.abortRequested():
            sequence += 1
            payload = json.dumps(observe(sequence, settings), ensure_ascii=False)
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
        (Path(os.environ['APERTURE_ZIP_OUT']) / 'observer-error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise


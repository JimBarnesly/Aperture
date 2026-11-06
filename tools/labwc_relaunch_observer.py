"""Read-only in-process GUI observation for disposable Wayland diagnostics."""
import json
import os
from pathlib import Path
import time
import traceback
import xbmc
import xbmcgui


def main():
    out = Path(os.environ['APERTURE_WAYLAND_SESSION'])
    monitor = xbmc.Monitor()
    sequence = 0
    with (out / 'states.jsonl').open('a', buffering=1) as history:
        while not monitor.abortRequested():
            sequence += 1
            try:
                focus = int(xbmc.getInfoLabel('System.CurrentControlId'))
            except ValueError:
                focus = -1
            state = dict(sequence=sequence, time=time.time(), pid=os.getpid(),
                skin=xbmc.getSkinDir(), window=xbmcgui.getCurrentWindowId(),
                dialog=xbmcgui.getCurrentWindowDialogId(), focus=focus,
                control_label=xbmc.getInfoLabel('System.CurrentControl'),
                list_item=xbmc.getInfoLabel('ListItem.Label'),
                window_label=xbmc.getInfoLabel('System.CurrentWindow'),
                exit_label=xbmc.getLocalizedString(13012),
                width=xbmcgui.getScreenWidth(), height=xbmcgui.getScreenHeight(),
                home_visible=bool(xbmc.getCondVisibility('Window.IsVisible(home)')),
                show_exit=bool(xbmc.getCondVisibility('System.ShowExitButton')))
            payload = json.dumps(state)
            history.write(payload + '\n')
            temporary = out / 'state.tmp'
            temporary.write_text(payload)
            temporary.replace(out / 'state.json')
            if monitor.waitForAbort(0.15):
                break


if __name__ == '__main__':
    try:
        main()
    except Exception:
        (Path(os.environ['APERTURE_WAYLAND_SESSION']) / 'observer-error.txt').write_text(traceback.format_exc())
        raise

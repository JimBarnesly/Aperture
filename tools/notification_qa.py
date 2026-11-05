"""Synthetic notification lifetime check for a disposable Kodi CI profile only.

Loaded by the CI-only N keymap. Never bundled into the installed skin/add-ons.
No CEC calls, setting changes, remote access, or personal content are involved.
"""
import json
import os
from pathlib import Path
import time


CASES = (
    ('short', 'Aperture test notification', 'Synthetic adapter connection complete.'),
    ('scrolling', 'Aperture scrolling test',
     'This deliberately long synthetic notification must scroll fully before it '
     'expires. The next message must still be displayed and expire normally.'),
    ('empty', 'Aperture empty-body test', ''),
    ('after-empty', 'Aperture queue recovery test', 'Later notifications still work.'),
)


def run():
    import xbmc
    import xbmcgui

    out = Path(os.environ['APERTURE_SMOKE_OUT']) / 'notifications'
    stage = (out / 'request.txt').read_text().strip()
    if stage not in ('initial', 'after-reload'):
        raise ValueError('Unknown CI notification stage')
    out.mkdir(exist_ok=True)
    result_path = out / (stage + '.json')
    result = {'status': 'running', 'stage': stage, 'checks': []}
    monitor = xbmc.Monitor()

    def visible():
        return bool(xbmc.getCondVisibility('Window.IsVisible(10107)'))

    def wait_for(want, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if visible() == want:
                return
            if monitor.waitForAbort(.05):
                raise RuntimeError('Kodi aborted during notification check')
        raise AssertionError('Notification did not become ' + ('visible' if want else 'hidden'))

    def save():
        temporary = result_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(result, indent=2) + '\n')
        temporary.replace(result_path)

    try:
        save()
        wait_for(False, 15)
        for name, caption, body in CASES:
            started = time.monotonic()
            xbmcgui.Dialog().notification(caption, body, xbmcgui.NOTIFICATION_INFO,
                                          3000, False)
            wait_for(True, 8)
            if monitor.waitForAbort(.8):
                raise RuntimeError('Kodi aborted before screenshot')
            screenshot = out / (stage + '-' + name + '.png')
            xbmc.executebuiltin('TakeScreenshot("' + str(screenshot) + '")')
            wait_for(False, 45)
            elapsed = time.monotonic() - started
            if not screenshot.is_file():
                raise AssertionError('Missing rendered notification screenshot')
            result['checks'].append({'case': name, 'shown': True, 'expired': True,
                                     'elapsed_seconds': round(elapsed, 3),
                                     'screenshot': screenshot.name})
            save()
        result['status'] = 'passed'
    except Exception as exc:
        result.update(status='failed', reason=str(exc))
        raise
    finally:
        save()


if __name__ == '__main__':
    run()

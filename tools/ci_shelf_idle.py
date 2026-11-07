"""Real-Kodi idle-return acceptance, called by the Format GUI driver."""
import time


def exercise_idle_return(press, wait_music, music, screenshot, checks,
                         sleep=time.sleep, monotonic=time.monotonic):
    before = music()
    queue = before['queue']
    press('BackSpace')
    shelf = wait_music('Playing album returns to the record shelf',
                       lambda s: s.get('window') == 10502
                       and s.get('dialog') == 9999 and s.get('shelf_visible')
                       and s.get('player') is not None,
                       after=before['sequence'])
    entered = monotonic()
    sleep(30)
    press('Right')  # Even a bounded navigation key must reset Kodi input idle.
    last_input = monotonic()
    sleep(35)
    still = wait_music('Browsing resets the shelf idle deadline',
                       lambda s: s.get('window') == 10502
                       and s.get('dialog') == 9999 and s.get('shelf_visible')
                       and s.get('player') is not None,
                       timeout=5, after=shelf['sequence'])
    assert still['queue'] == queue, 'Browsing replaced the playing album'
    returned = wait_music('Idle shelf returns to playing screen after one minute',
                          lambda s: s.get('window') == 12006
                          and s.get('dialog') == 9999 and s.get('player') is not None,
                          timeout=40, after=still['sequence'])
    elapsed = monotonic() - last_input
    assert elapsed >= 58, 'Shelf returned before one minute of input inactivity'
    assert returned['queue'] == queue, 'Idle return replaced the playing album'
    assert returned['player']['properties']['speed'] == 1, 'Idle return paused playback'
    screenshot('format-03h-idle-return')
    checks.append({'check': 'playing-shelf-idle-return-after-browsing-reset',
                   'seconds_since_entry': monotonic() - entered,
                   'seconds_since_input': elapsed, 'queue_preserved': True})
    return returned

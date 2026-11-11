#!/usr/bin/env python3
"""Real Kodi ZIP installer and accepted-switch/restart test in a fresh profile.

Run only from the isolated CI harness after its earlier Kodi has exited. Entry
hotkeys open native windows; xdotool arrows/Enter drive every actual operation.
"""
import argparse
import base64
from collections import deque
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time
import traceback
import xml.etree.ElementTree as ET
from PIL import Image, ImageStat

from zip_smoke_fixture import SUBJECTS, prepare, verify_installed


def label_matches(actual, expected):
    # Kodi appends the radio-button state to System.CurrentControl. Match only
    # that known suffix; do not select arbitrary prefixes or neighboring items.
    return re.sub(r' \([ *xX]\)$', '', actual.strip()) == expected


def setting_matches(state, expected, after=0):
    return (state.get('unknown_sources') is expected
            and state.get('unknown_sources_read_started', 0) > after
            and time.time() - state.get('unknown_sources_read_completed', 0) < 3)


def installed_matches(state, rows, data):
    """Every subject must remain enabled at the exact installed user path/version."""
    installed = state.get('installed', {})
    for row in rows:
        actual = installed.get(row['addon'], {})
        expected_path = Path(data) / 'addons' / row['addon']
        if (actual.get('enabled') is not True or actual.get('version') != row['version']
                or not actual.get('path') or Path(actual['path']).resolve() != expected_path.resolve()):
            return False
    return True


def movies_guidance(state):
    return (state.get('dialog') == 12002
            and 'Add your existing movie folder' in state.get('dialog_text', ''))




class Driver:
    def __init__(self, root, runtime, out, binary):
        self.out, self.binary = Path(out), binary
        self.target, self.packages = prepare(root, runtime, Path(runtime) / 'system', self.out)
        self.env = dict(os.environ)
        home = self.target / 'home'
        self.env.update(HOME=str(home), KODI_HOME=str(self.target / 'system'),
            KODI_DATA=str(self.target / 'data'), KODI_TEMP=str(self.out / 'logs'),
            XDG_CONFIG_HOME=str(home / '.config'), XDG_CACHE_HOME=str(home / '.cache'),
            XDG_DATA_HOME=str(home / '.local/share'), APERTURE_ZIP_OUT=str(self.out))
        (self.out / 'logs').mkdir()
        (self.out / 'screenshots').mkdir()
        self.process = None
        self.kodi_pid = None
        self.stdout = None
        self.session = 0
        self.latest = {}
        self.checks = []

    def state(self):
        error = self.out / 'observer-error.txt'
        if error.exists():
            raise AssertionError(error.read_text(encoding='utf-8'))
        try:
            self.latest = json.loads((self.out / 'state.json').read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return self.latest

    def wait(self, description, predicate, after=0, timeout=30):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            if self.process.poll() is not None:
                raise AssertionError('Fresh-profile Kodi exited: ' + str(self.process.returncode))
            value = self.state()
            if (value.get('pid') == self.kodi_pid and value.get('sequence', 0) > after
                    and time.time() - value.get('time', 0) < 3 and predicate(value)):
                return value
            time.sleep(0.1)
        raise AssertionError('Timed out: {}; actual state={}'.format(description, self.latest))

    def start(self, skin):
        if self.process is not None and self.process.poll() is None:
            raise AssertionError('Cannot relaunch while the previous Kodi child is alive')
        self.session += 1
        (self.out / 'state.json').unlink(missing_ok=True)
        self.latest = {}
        self.stdout = (self.out / 'logs' / ('stdout-{}.log'.format(self.session))).open('wb')
        self.process = subprocess.Popen([self.binary, '--windowing=x11', '--gl-interface=glx',
            '--audio-backend=pulseaudio', '--debug', '-fs'], env=self.env,
            stdout=self.stdout, stderr=subprocess.STDOUT)
        self.kodi_pid = self.process.pid
        self.wait('fresh-profile Home', lambda s: s.get('skin') == skin and s.get('window') == 10000
                  and s.get('dialog') == 9999 and setting_matches(s, False), timeout=90)
        windows = subprocess.check_output(['xdotool', 'search', '--onlyvisible', '--class', '^Kodi( from Debian)?$'], text=True).split()
        if len(windows) != 1:
            raise AssertionError('Expected only our fresh Kodi window: ' + str(windows))
        title = subprocess.check_output(['xdotool', 'getwindowname', windows[0]], text=True).strip()
        if title not in ('Kodi', 'Kodi from Debian'):
            raise AssertionError('Unexpected fresh Kodi X window')
        subprocess.run(['xdotool', 'windowfocus', '--sync', windows[0]], check=True, timeout=10)
        self.record('zip-session-started', session=self.session, pid=self.kodi_pid,
                    profile=str(self.target / 'data'), requested_skin=skin)

    def archive_session(self):
        if self.stdout:
            self.stdout.close()
            self.stdout = None
        log = self.out / 'logs/kodi.log'
        if log.exists():
            shutil.copy2(log, self.out / 'logs' / ('session-{}.log'.format(self.session)))

    def exit_native(self):
        """Accept only the installed skin's verified Exit action, never power-off.

        No signal fallback belongs here: a timeout/crash fails acceptance even
        if emergency cleanup can subsequently terminate the isolated child.
        """
        child, pid = self.process, self.kodi_pid
        if child is None or child.pid != pid or child.poll() is not None:
            raise AssertionError('Native Exit requires the original live Kodi child')
        menu = ET.parse(self.target / 'data/addons/skin.aperture/xml/DialogButtonMenu.xml').getroot()
        panels = menu.findall(".//control[@id='9000']")
        exits = [item for panel in panels for item in panel.findall('./content/item')
                 if item.findtext('label') == '$LOCALIZE[13012]']
        if (len(panels) != 1 or len(exits) != 1
                or [node.text for node in exits[0].findall('onclick')] != ['Quit()']):
            raise AssertionError('Installed power-menu Exit is not uniquely mapped to Quit()')
        self.wait('Home before native Exit', lambda s: s.get('skin') == 'skin.aperture'
            and s.get('window') == 10000 and s.get('dialog') == 9999)
        before = self.key('s')  # Kodi's native power-menu key, not a Quit shortcut.
        self.wait('native power menu', lambda s: s.get('skin') == 'skin.aperture'
            and s.get('dialog') == 10111, after=before)
        self.find('Exit')
        self.capture('zip-native-exit-session-' + str(self.session))
        selected = self.settle_focus()
        if (selected.get('pid') != pid or selected.get('skin') != 'skin.aperture'
                or selected.get('dialog') != 10111 or selected.get('focus') != 9000
                or selected.get('list_item') != 'Exit'
                or not 0 <= time.time() - selected.get('time', 0) < 3):
            raise AssertionError('Native Exit focus changed; refusing to activate a power action')
        if self.process is not child or child.poll() is not None:
            raise AssertionError('Original Kodi child changed before native Exit')
        evidence = dict(check='zip-native-exit', session=self.session, pid=pid,
                        profile=str(self.target / 'data'), state=dict(selected),
                        method='power-menu Exit', status='pending', returncode=None)
        self.checks.append(evidence)
        # key() requires a subsequent observer frame, which a real Exit need not
        # produce. Reap exactly the Popen child instead of treating stale UI as exit.
        try:
            subprocess.run(['xdotool', 'key', '--clearmodifiers', 'Return'], check=True, timeout=10)
            result = child.wait(timeout=30)
        except subprocess.TimeoutExpired:
            evidence['status'] = 'timed-out'
            raise AssertionError('Native Exit did not terminate the original Kodi child')
        evidence.update(returncode=result, completed=time.time(), status='passed' if result == 0 else 'failed')
        self.archive_session()
        if result != 0:
            raise AssertionError('Native Exit was not clean: ' + str(result))

    def emergency_cleanup(self):
        """Failure-only cleanup; never evidence for normal Exit acceptance."""
        if self.process is not None and self.process.poll() is None:
            if self.kodi_pid is not None:
                try:
                    os.kill(self.kodi_pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            else:
                self.process.terminate()
            try:
                self.process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                if self.kodi_pid is not None:
                    try:
                        os.kill(self.kodi_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                self.process.kill()
                self.process.wait(timeout=5)
                raise AssertionError('Emergency cleanup required SIGKILL')
        self.archive_session()

    def key(self, key):
        before = self.state().get('sequence', 0)
        subprocess.run(['xdotool', 'key', '--clearmodifiers', key], check=True, timeout=10)
        self.wait('fresh state after ' + key, lambda s: True, after=before)
        time.sleep(0.2)
        return before

    def labelled(self, text):
        return any(label_matches(self.state().get(key, ''), text) for key in ('list_item', 'control_label'))

    def settle_focus(self):
        signature, since, frames, sequence = None, 0, 0, -1
        def stable(state):
            nonlocal signature, since, frames, sequence
            current = tuple(state.get(key) for key in ('window', 'dialog', 'focus', 'control_label', 'list_item'))
            if current != signature:
                signature, since, frames, sequence = current, state['time'], 0, -1
            if state['sequence'] != sequence:
                sequence = state['sequence']
                frames += 1
            return frames >= 3 and state['time'] - since >= 0.5
        return self.wait('focused item settled across real rendered frames', stable, timeout=8)

    def find(self, text, direction='Down', steps=15):
        # Entering a folder can briefly retain its previous source row. Let that
        # transition finish before sending an arrow, or it can masquerade as the
        # arrow's own focus change and leave an extra input queued behind it.
        self.settle_focus()
        for index in range(steps + 1):
            if self.labelled(text):
                return
            if index < steps:
                previous = tuple(self.state().get(key) for key in ('focus', 'control_label', 'list_item'))
                before = self.key(direction)
                # A newer observer frame need not mean Kodi has consumed the key.
                # Never queue another arrow until the actual focused item changes.
                self.wait('focus changed after ' + direction,
                    lambda s: tuple(s.get(key) for key in ('focus', 'control_label', 'list_item')) != previous,
                    after=before, timeout=5)
                self.settle_focus()
        raise AssertionError('Cannot focus {!r}; actual state={}'.format(text, self.state()))

    def capture(self, name):
        time.sleep(0.7)
        path = self.out / 'screenshots' / (name + '.png')
        subprocess.run(['xwd', '-root', '-silent', '-out', str(path.with_suffix('.xwd'))], check=True, timeout=10)
        subprocess.run(['import', '-window', 'root', str(path)], check=True, timeout=10)
        with Image.open(path) as source:
            rgb = source.convert('RGB')
            if rgb.size != (1920, 1080) or max(ImageStat.Stat(rgb).stddev) < 3:
                raise AssertionError('Fresh ZIP screenshot blank or wrong size')
            rgb.thumbnail((640, 360))
            preview = path.with_suffix('.preview.jpg')
            rgb.save(preview, quality=65)
        print('APERTURE_SCREENSHOT_BASE64_BEGIN ' + preview.name, flush=True)
        print(base64.b64encode(preview.read_bytes()).decode(), flush=True)
        print('APERTURE_SCREENSHOT_BASE64_END ' + preview.name, flush=True)
        self.record(name, screenshot=str(path.relative_to(self.out)))

    def record(self, name, **extra):
        self.checks.append(dict(check=name, state=self.state(), **extra))

    def confirm(self, label):
        self.wait('native confirmation dialog', lambda s: s.get('dialog') == 10100)
        self.find(label, direction='Left', steps=2)
        self.key('Return')

    def set_unknown_sources(self, enabled):
        self.key('n')
        self.wait('native add-on settings', lambda s: s.get('window') == 10016 and s.get('dialog') == 9999)
        if self.state().get('focus') in (3, -200):
            self.key('Right')
        self.find('Unknown sources')
        self.wait('fresh Unknown sources value', lambda s: any(setting_matches(s, value) for value in (True, False)))
        if self.state()['unknown_sources'] is not enabled:
            changed_after = time.time()
            self.key('Return')
            if enabled:
                self.wait('test-profile Unknown sources warning', lambda s: s.get('dialog') == 10100)
                self.capture('zip-02-private-profile-warning')
                self.confirm('Yes')
            self.wait('Unknown sources matches requested test state', lambda s: setting_matches(s, enabled, changed_after) and s.get('dialog') == 9999)
        self.capture('zip-03-private-sources-on' if enabled else 'zip-07-private-sources-off')

    def install(self, row):
        self.key('m')
        self.wait('native Add-on browser', lambda s: s.get('window') == 10040 and s.get('dialog') == 9999)
        self.find('Install from zip file')
        self.key('Return')
        self.wait('native ZIP file picker', lambda s: s.get('dialog') == 10126)
        self.find('Aperture CI packages', steps=20)
        self.key('Return')
        self.find(row['file'], steps=5)
        self.capture('zip-04-select-' + row['addon'])
        if not self.labelled(row['file']):
            raise AssertionError('ZIP filename focus changed before activation; refusing to select another item')
        self.key('Return')
        self.wait('ZIP installed or skin install prompt', lambda s: row['addon'] in s.get('installed', {}), timeout=90)
        if row['addon'] == 'skin.aperture':
            self.wait('native new-skin offer', lambda s: s.get('dialog') == 10100)
            self.capture('zip-05-new-skin-offer')
            self.confirm('No')  # Exercise explicit chooser/Keep below, after restoring sources-off.
        self.wait('installed add-on enabled', lambda s: s.get('dialog') == 9999 and
            s.get('installed', {}).get(row['addon'], {}).get('enabled') is True)
        if not installed_matches(self.state(), [row], self.target / 'data'):
            raise AssertionError('ZIP installation did not produce the expected user add-on/version')
        self.record('zip-installed-' + row['addon'])

    def choose_skin(self, name, identifier, tag):
        self.key('i')
        self.wait('native Interface settings', lambda s: s.get('window') == 10032 and s.get('dialog') == 9999)
        if self.state().get('focus') in (3, -200):
            self.key('Right')
        self.find('Skin', steps=12)
        self.key('Return')
        self.wait('native skin chooser', lambda s: s.get('dialog') == 12000)
        self.find(name, steps=5)
        self.capture(tag + '-chooser')
        self.key('Return')
        self.wait('real skin loaded awaiting Keep', lambda s: s.get('skin') == identifier and s.get('dialog') == 10100)
        self.capture(tag + '-keep')
        self.confirm('Yes')
        self.wait('accepted skin with no modal', lambda s: s.get('skin') == identifier and s.get('dialog') == 9999)
        self.key('h')
        self.wait('accepted skin Home', lambda s: s.get('skin') == identifier and s.get('window') == 10000)
        self.capture(tag + '-home')

    def focus_home(self, target):
        graph = {}
        source = self.target / 'data/addons/skin.aperture/xml/Home.xml'
        for node in ET.parse(source).getroot().iter('control'):
            if node.get('id', '').isdigit():
                graph[int(node.get('id'))] = {key: int(node.findtext(tag)) for key, tag in
                    [('Left', 'onleft'), ('Right', 'onright'), ('Up', 'onup'), ('Down', 'ondown')]
                    if node.findtext(tag, '').isdigit()}
        self.wait('Home before installed focus navigation', lambda s: s.get('skin') == 'skin.aperture'
            and s.get('window') == 10000 and s.get('dialog') == 9999)
        # Home is reported active before its 730 ms WindowOpen reveal accepts
        # arrows. Match the broad GUI driver's guard, then route from fresh,
        # settled focus rather than the transient focus restored during entry.
        time.sleep(0.85)
        current = self.settle_focus()
        if (current.get('skin') != 'skin.aperture' or current.get('window') != 10000
                or current.get('dialog') != 9999):
            raise AssertionError('Home changed while waiting for installed focus navigation')
        start = current['focus']
        todo, visited = deque([(start, [])]), {start}
        while todo:
            at, route = todo.popleft()
            if at == target:
                for key, wanted in route:
                    before = self.key(key)
                    self.wait('installed Home focus ' + str(wanted), lambda s: s.get('focus') == wanted
                        and s.get('window') == 10000 and s.get('dialog') == 9999, after=before)
                return
            for key, nxt in graph.get(at, {}).items():
                if nxt not in visited:
                    visited.add(nxt)
                    todo.append((nxt, route + [(key, nxt)]))
        raise AssertionError('No native arrow route to installed Home control')

    def check_music(self):
        # Exercise the installed Home action, not a shortcut into the add-on.
        # Reentering must reset to the single Format root and Back restores Music.
        for attempt in range(2):
            self.focus_home(103)
            before = self.key('Return')
            self.wait('ZIP-installed direct Music shelf', lambda s: s.get('window') == 10502
                and s.get('dialog') == 9999 and s.get('folder') == 'plugin://plugin.audio.aperture.format/?action=albums', after=before)
            if attempt == 0:
                self.capture('zip-10-installed-format')
            self.settle_focus()
            before = self.key('BackSpace')
            self.wait('Format Back returns to Home Music', lambda s: s.get('window') == 10000
                and s.get('dialog') == 9999 and s.get('focus') == 103, after=before)
            self.record('unified-music-open-back', attempt=attempt)

    def run(self):
        self.start('skin.estuary')
        if self.state()['installed'] or self.state()['unknown_sources']:
            raise AssertionError('ZIP phase was not initially empty and sources-off')
        self.capture('zip-01-stock-estuary')
        self.set_unknown_sources(True)
        for row in self.packages:
            self.install(row)
        skin_name = self.state()['installed']['skin.aperture']['name']
        verification = verify_installed(self.target / 'packages', self.target / 'data', self.packages)
        self.record('zip-installed-bytes-match', packages=verification)
        self.set_unknown_sources(False)
        self.choose_skin(skin_name, 'skin.aperture', 'zip-08-accepted-aperture')
        self.exit_native()
        # The direct shelf needs a configured server. Configure only the
        # disposable profile with the already-running synthetic loopback fixture.
        ready = json.loads((self.out.parent / 'format-ready.json').read_text())
        if not ready['url'].startswith('http://127.0.0.1:'):
            raise AssertionError('ZIP smoke requires the local synthetic Format server')
        settings = self.target / 'data/userdata/addon_data/plugin.audio.aperture.format/settings.xml'
        settings.parent.mkdir(parents=True, exist_ok=True)
        config = ET.Element('settings', version='2')
        ET.SubElement(config, 'setting', id='server_url').text = ready['url']
        ET.ElementTree(config).write(settings, encoding='utf-8', xml_declaration=True)
        self.start('skin.aperture')
        self.wait('accepted skin/sources-off persisted after restart', lambda s: setting_matches(s, False) and
            installed_matches(s, self.packages, self.target / 'data'))
        self.capture('zip-09-restarted-aperture')
        self.check_music()
        # This profile has no video sources. Prove the independently ZIP-installed
        # Movies route runs, explains setup, and survives dismissal/Back/reopening.
        self.check_movies()
        # Recovery is accepted, not just a test profile config-file replacement.
        self.choose_skin('Estuary', 'skin.estuary', 'zip-12-recovery-estuary')
        self.choose_skin(skin_name, 'skin.aperture', 'zip-13-return-aperture')
        self.exit_native()
        self.start('skin.aperture')
        self.wait('recovered preference and all installed add-ons persist', lambda s: setting_matches(s, False)
            and installed_matches(s, self.packages, self.target / 'data'))
        self.capture('zip-14-final-restart')
        verify_installed(self.target / 'packages', self.target / 'data', self.packages)
        self.exit_native()
        for path in (self.out / 'logs').glob('session-*.log'):
            log = path.read_text(encoding='utf-8', errors='replace')
            for marker in ('Error loading skin', 'failed to load skin', 'EXCEPTION Thrown (PythonToCppException)',
                           'Aperture: operation failed', 'Aperture Movies: source listing failed'):
                if marker.lower() in log.lower():
                    raise AssertionError('Fresh ZIP runtime error: ' + marker)
        shutil.copy2(self.target / 'data/userdata/guisettings.xml', self.out / 'final-guisettings.xml')
        return {'status': 'passed', 'scope': 'Fresh Format, Movies and skin ZIP installs, native media entry, accepted skin selection, native power-menu Exit/relaunch persistence and accepted Estuary recovery',
            'checks': self.checks, 'packages': verification, 'unknown_sources_restored': True,
            'limitations': ['CI-only disposable profile and entry-window hotkeys', 'No Pi/hardware/controller/audio-output/core acceptance',
                'No production network source or streaming acceptance']}

    def check_movies(self):
        for attempt, dismiss in ((1, 'Return'), (2, 'BackSpace')):
            self.focus_home(100)
            before = self.key('Return')
            initial_focus = 720 if attempt == 1 else 723
            self.wait('ZIP-installed Movies online-first home', lambda s, focus=initial_focus: s.get('window') == 11120
                and s.get('dialog') == 9999 and s.get('focus') == focus, after=before)
            self.capture('zip-11-installed-movies-home-' + str(attempt))
            # Reentry preserves Local files focus; first entry starts on Search.
            for _ in range(3 if attempt == 1 else 0):
                self.key('Right')
            before = self.key('Return')
            self.wait('ZIP-installed Movies no-source guidance', movies_guidance, after=before)
            self.capture('zip-11-installed-movies-guidance-' + str(attempt))
            before = self.key(dismiss)
            self.wait('ZIP-installed Movies empty local files', lambda s: s.get('window') == 10025
                and s.get('dialog') == 9999
                and s.get('folder') == 'plugin://plugin.video.aperture.movies/?mode=local', after=before)
            self.record('zip-installed-movies-empty-local-' + str(attempt))
            before = self.key('BackSpace')
            self.wait('Back restores Movies home', lambda s: s.get('window') == 11120
                and s.get('dialog') == 9999, after=before)
            before = self.key('BackSpace')
            self.wait('Home after installed Movies', lambda s: s.get('window') == 10000
                and s.get('dialog') == 9999 and s.get('focus') == 100, after=before)
        self.capture('zip-11-installed-movies-home')


def main():
    parser = argparse.ArgumentParser()
    for name in ('root', 'runtime', 'out', 'binary'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    driver = None
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        driver = Driver(args.root, args.runtime, args.out, args.binary)
        result = driver.run()
    except Exception as exc:
        if driver:
            try:
                driver.capture('zip-failure')
            except Exception:
                pass
        result = {'status': 'failed', 'reason': str(exc), 'checks': driver.checks if driver else [],
                  'traceback': traceback.format_exc()}
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        raise
    finally:
        if driver and driver.process is not None and driver.process.poll() is None:
            driver.emergency_cleanup()
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('PASS: fresh Kodi ZIP installs, accepted skin switching, restart persistence and Estuary recovery verified.', flush=True)


if __name__ == '__main__':
    main()


#!/usr/bin/env python3
"""Disposable native Wayland normal-Exit diagnostic, not a workaround.

Observe before input. Four launches give three actual same-profile relaunches.
No Kodi RPC calls, skin switching, media playback or production device access.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import traceback
import xml.etree.ElementTree as ET
from PIL import Image, ImageStat

OBSERVER = 'service.aperture.waylanddiagnostic'


class DiagnosticFailure(RuntimeError):
    def __init__(self, category, message):
        super().__init__(message)
        self.category = category


def exit_mapping(path):
    """Bind the visible localized Exit item to its exact installed action."""
    root = ET.parse(path).getroot()
    matches = []
    for panel in root.iter('control'):
        if not panel.get('id', '').isdigit():
            continue
        for item in panel.findall('./content/item'):
            if item.findtext('label', '').strip() == '$LOCALIZE[13012]':
                matches.append((int(panel.get('id')), item))
        if panel.findtext('label', '').strip() in ('$LOCALIZE[13012]', '13012'):
            matches.append((int(panel.get('id')), panel))
    if len(matches) != 1:
        raise DiagnosticFailure('harness_failure', 'Exit menu item is not unique')
    focus, item = matches[0]
    actions = [e.text.strip().lower() for e in item.findall('onclick') if e.text]
    if actions != ['quit()']:
        raise DiagnosticFailure('harness_failure', 'Exit is not mapped only to Quit()')
    return focus


def home_state(state, skin, pid):
    return (state.get('pid') == pid and state.get('skin') == skin
        and state.get('window') == 10000 and state.get('dialog') == 9999
        and state.get('home_visible') is True and state.get('width') == 1920
        and state.get('height') == 1080)


def pixel_evidence(path, text):
    with Image.open(path) as image:
        rgb = image.convert('RGB')
        stats = ImageStat.Stat(rgb)
        sample = rgb.resize((320, 180))
        pixels = list(sample.getdata())
        dark_fraction = sum(max(p) < 12 for p in pixels) / len(pixels)
        words = set(re.findall(r'[a-z]+', text.lower()))
        labels = sorted(words & {'movies', 'music', 'games', 'settings', 'shows', 'videos', 'pictures', 'weather'})
        # A noisy/debug-overlay image cannot pass just through variance.
        return dict(size=list(rgb.size), stddev=stats.stddev, dark_fraction=dark_fraction,
            recognized_home_labels=labels,
            home_pixels=rgb.size == (1920, 1080) and max(stats.stddev) > 3 and len(labels) >= 3,
            black_frame=rgb.size == (1920, 1080) and dark_fraction > .995)


def prepare(root, runtime, skin):
    target = runtime / 'profile'
    if target.exists():
        raise DiagnosticFailure('harness_failure', 'Refusing an existing profile')
    system, data, home = target / 'system', target / 'data', target / 'home'
    source = Path('/usr/share/kodi')
    shutil.copytree(source, system, symlinks=True)
    for original in source.rglob('*'):
        if not original.is_symlink():
            continue
        resolved = original.resolve()
        if not resolved.is_file() and original.suffix.lower() in ('.ttf', '.otf'):
            resolved = root / 'build/skin.aperture/fonts' / original.name
        if not resolved.is_file():
            raise DiagnosticFailure('harness_failure', 'Unresolved distro resource: ' + str(original))
        copied = system / original.relative_to(source)
        copied.unlink()
        shutil.copy2(resolved, copied)
    if skin == 'skin.aperture':
        shutil.copytree(root / 'build/skin.aperture', system / 'addons/skin.aperture')
    observer = system / 'addons' / OBSERVER
    observer.mkdir()
    shutil.copy2(root / 'tools/labwc_relaunch_observer.py', observer / 'service.py')
    (observer / 'addon.xml').write_text(f'''<addon id="{OBSERVER}" name="Wayland diagnostic observer" version="1.0.0" provider-name="Aperture CI">
<requires><import addon="xbmc.python" version="3.0.1"/></requires>
<extension point="xbmc.service" library="service.py"/>
<extension point="xbmc.addon.metadata"><summary lang="en_GB">Read-only disposable observer</summary><platform>all</platform><license>GPL-3.0-or-later</license></extension></addon>''')
    manifest = ET.parse(system / 'system/addon-manifest.xml')
    for name in (skin, OBSERVER):
        if not any(e.text == name for e in manifest.getroot().findall('addon')):
            ET.SubElement(manifest.getroot(), 'addon').text = name
    manifest.write(system / 'system/addon-manifest.xml', encoding='utf-8', xml_declaration=True)
    for directory in (data / 'userdata', home / '.config', home / '.cache', home / '.local/share'):
        directory.mkdir(parents=True)
    settings = ET.Element('settings', version='2')
    values = {'lookandfeel.skin': skin, 'general.addonupdates': '2', 'addons.unknownsources': 'false',
              'lookandfeel.enablerssfeeds': 'false', 'input.enablemouse': 'false', 'screensaver.mode': '',
              'powermanagement.displaysoff': '0', 'powermanagement.shutdowntime': '0'}
    for service in ('webserver', 'esenabled', 'esallinterfaces', 'zeroconf', 'wsdiscovery', 'airplay', 'upnp', 'upnpserver', 'upnprenderer'):
        values['services.' + service] = 'false'
    for key, value in values.items():
        ET.SubElement(settings, 'setting', id=key).text = value
    ET.ElementTree(settings).write(data / 'userdata/guisettings.xml', encoding='utf-8', xml_declaration=True)
    (data / 'userdata/advancedsettings.xml').write_text('<advancedsettings><loglevel hide="false">1</loglevel></advancedsettings>')
    return target


class Driver:
    def __init__(self):
        self.root = Path(os.environ['APERTURE_WAYLAND_ROOT'])
        self.out = Path(os.environ['APERTURE_WAYLAND_OUT'])
        self.runtime = Path(os.environ['APERTURE_WAYLAND_RUNTIME'])
        self.skin = 'skin.' + os.environ['APERTURE_WAYLAND_SKIN']
        if self.skin not in ('skin.estuary', 'skin.aperture'):
            raise DiagnosticFailure('harness_failure', 'Unexpected skin')
        self.checks, self.latest = [], {}
        self.process = self.stdout = self.keeper = self.keeper_log = None
        self.session = None
        self.launch = 0
        self.compositor = self.find_compositor()
        self.target = prepare(self.root, self.runtime, self.skin)
        self.focus_id = exit_mapping(self.target / 'system/addons' / self.skin / 'xml/DialogButtonMenu.xml')
        self.env = dict(os.environ)
        home = self.target / 'home'
        self.env.update(HOME=str(home), KODI_HOME=str(self.target / 'system'), KODI_DATA=str(self.target / 'data'),
            XDG_CONFIG_HOME=str(home / '.config'), XDG_CACHE_HOME=str(home / '.cache'),
            XDG_DATA_HOME=str(home / '.local/share'), WAYLAND_DEBUG='client', EGL_LOG_LEVEL='debug')
        self.record('fixture', skin=self.skin, profile=str(self.target / 'data'), compositor=self.compositor,
            display=os.environ.get('WAYLAND_DISPLAY'), runtime=os.environ.get('XDG_RUNTIME_DIR'),
            clean_profile=True, native_keymap=True, exit_focus=self.focus_id, exit_action='Quit()')

    def find_compositor(self):
        pid = os.getppid()
        for _ in range(8):
            proc = Path('/proc') / str(pid)
            if (proc / 'comm').read_text().strip() == 'labwc':
                return pid
            status = (proc / 'status').read_text()
            pid = int(re.search(r'^PPid:\s*(\d+)', status, re.M).group(1))
            if pid <= 1:
                break
        raise DiagnosticFailure('harness_failure', 'Cannot identify ancestor Labwc process')

    def record(self, event, **fields):
        value = dict(event=event, time=time.time(), monotonic=time.monotonic(), launch=self.launch, **fields)
        self.checks.append(value)
        with (self.out / 'events.jsonl').open('a') as log:
            log.write(json.dumps(value) + '\n')
        print(json.dumps(value), flush=True)

    def compositor_alive(self):
        os.kill(self.compositor, 0)
        if (Path('/proc') / str(self.compositor) / 'comm').read_text().strip() != 'labwc':
            raise DiagnosticFailure('harness_failure', 'Original compositor changed')

    def command(self, args, name):
        result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
        (self.out / name).write_text(result.stdout)
        if result.returncode:
            raise DiagnosticFailure('harness_failure', '{} failed: {}'.format(args[0], result.stdout))
        return result.stdout

    def setup_display(self):
        self.command(['wayland-info'], 'wayland-info-before-keyboard.txt')
        outputs = self.command(['wlr-randr'], 'outputs-before.txt')
        names = re.findall(r'^(HEADLESS[^\s]*)', outputs, re.M)
        if len(names) != 1:
            raise DiagnosticFailure('harness_failure', 'Expected one headless output: ' + outputs)
        self.output = names[0]
        self.command(['wlr-randr', '--output', self.output, '--custom-mode', '1920x1080@60Hz'], 'mode-set.txt')
        self.command(['wlr-randr'], 'outputs-after.txt')
        # Establish wl_seat keyboard capability before Kodi without sending a key.
        self.keeper_log = (self.out / 'keyboard-capability.log').open('w')
        self.keeper = subprocess.Popen(['wtype', '-s', '720000'], stdout=self.keeper_log, stderr=subprocess.STDOUT,
            env=dict(os.environ, WAYLAND_DEBUG='client'))
        time.sleep(.5)
        if self.keeper.poll() is not None:
            raise DiagnosticFailure('harness_failure', 'No-input virtual keyboard keeper exited')
        self.command(['wayland-info'], 'wayland-info-after-keyboard.txt')
        self.record('keyboard-capability-established', pid=self.keeper.pid, synthetic_keys_sent=0)

    def state(self):
        if self.session and (self.session / 'observer-error.txt').exists():
            raise DiagnosticFailure('harness_failure', (self.session / 'observer-error.txt').read_text())
        if self.session:
            try:
                self.latest = json.loads((self.session / 'state.json').read_text())
            except (FileNotFoundError, json.JSONDecodeError):
                pass
        return self.latest

    def wait(self, description, predicate, timeout=30, after=0, category='harness_failure'):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            self.compositor_alive()
            if self.process.poll() is not None:
                raise DiagnosticFailure(category, 'Original Kodi child exited {} while {}'.format(self.process.returncode, description))
            state = self.state()
            if (state.get('pid') == self.process.pid and state.get('sequence', 0) > after
                    and 0 <= time.time() - state.get('time', 0) < 3 and predicate(state)):
                return state
            time.sleep(.1)
        raise DiagnosticFailure(category, 'Timed out: {}; last state={}'.format(description, self.latest))

    def capture(self, name, ocr=False):
        path = self.session / (name + '.png')
        subprocess.run(['grim', '-o', self.output, str(path)], check=True, timeout=20)
        text = ''
        if ocr:
            text = subprocess.check_output(['tesseract', str(path), 'stdout', '--psm', '11'], stderr=subprocess.DEVNULL, text=True, timeout=30)
            (self.session / (name + '.ocr.txt')).write_text(text)
        evidence = pixel_evidence(path, text)
        (self.session / (name + '.pixels.json')).write_text(json.dumps(evidence, indent=2) + '\n')
        (self.session / (name + '.state.json')).write_text(json.dumps(self.state(), indent=2) + '\n')
        if ocr:
            with Image.open(path) as im:
                im.thumbnail((640, 360))
                preview = self.session / (name + '.jpg')
                im.convert('RGB').save(preview, quality=60)
            print('APERTURE_WAYLAND_SCREENSHOT {} {}'.format(str(path.relative_to(self.out)), base64.b64encode(preview.read_bytes()).decode()), flush=True)
        return evidence

    def start(self):
        self.compositor_alive()
        if self.process is not None and self.process.poll() is None:
            raise DiagnosticFailure('harness_failure', 'Previous Kodi child is still alive')
        self.launch += 1
        self.session = self.out / ('launch-' + str(self.launch))
        self.session.mkdir()
        self.latest = {}
        self.env.update(KODI_TEMP=str(self.session), APERTURE_WAYLAND_SESSION=str(self.session))
        settings = self.target / 'data/userdata/guisettings.xml'
        shutil.copy2(settings, self.session / 'guisettings-before.xml')
        persisted = ET.parse(settings).findtext("./setting[@id='lookandfeel.skin']")
        if persisted != self.skin:
            raise DiagnosticFailure('product_reproduction_candidate', 'Skin preference changed before relaunch')
        self.stdout = (self.session / 'kodi-stdout.log').open('w')
        self.process = subprocess.Popen([os.environ['APERTURE_KODI_BIN'], '--windowing=wayland', '-fs', '--debug', '--logging=console'],
            env=self.env, stdout=self.stdout, stderr=subprocess.STDOUT)
        self.record('launch-started', pid=self.process.pid, compositor=self.compositor,
            profile=str(self.target / 'data'), settings_sha256=hashlib.sha256(settings.read_bytes()).hexdigest(), synthetic_keys_sent=0)
        category = 'harness_failure' if self.launch == 1 else 'product_reproduction_candidate'
        try:
            self.wait('fresh Home before any input', lambda s: home_state(s, self.skin, self.process.pid), timeout=90, category=category)
            time.sleep(2)  # Finish opening animation without applying any input.
            state = self.wait('stable fresh Home', lambda s: home_state(s, self.skin, self.process.pid), category=category)
            pixels = self.capture('home-before-input', ocr=True)
        except Exception:
            try:
                self.capture('failure-before-input', ocr=True)
            except Exception:
                pass
            raise
        log = (self.session / 'kodi.log').read_text(errors='replace') if (self.session / 'kodi.log').exists() else ''
        if not re.search(r'llvmpipe', log, re.I) or not re.search(r'wayland', log, re.I):
            raise DiagnosticFailure('harness_failure', 'Kodi Wayland + llvmpipe not established in runtime log')
        if not pixels['home_pixels']:
            failure = ('product_reproduction_candidate' if self.launch > 1 else 'unexplained_visual_failure') if pixels['black_frame'] else 'harness_visual_validation_failure'
            raise DiagnosticFailure(failure, 'Home state exists but screenshot failed independent Home text/pixel validation: ' + str(pixels))
        self.record('home-before-input-passed', pid=self.process.pid, state=state, pixels=pixels,
            synthetic_keys_sent=0, screenshot=str((self.session / 'home-before-input.png').relative_to(self.out)))

    def key(self, key):
        before = self.state().get('sequence', 0)
        self.record('synthetic-key', key=key, pid=self.process.pid)
        subprocess.run(['wtype', '-k', key], check=True, timeout=10)
        return before

    def settle_focus(self, after=0, timeout=8):
        until = time.monotonic() + timeout
        signature = None
        same_since = 0
        frames = 0
        sequence = after
        while time.monotonic() < until:
            state = self.wait('fresh menu observation', lambda s: s.get('dialog') == 10111,
                              after=sequence, timeout=3)
            sequence = state['sequence']
            current = tuple(state.get(k) for k in ('pid', 'skin', 'dialog', 'focus', 'list_item', 'control_label'))
            if current == signature:
                frames += 1
            else:
                signature, same_since, frames = current, time.monotonic(), 1
            if frames >= 3 and time.monotonic() - same_since >= .5:
                return state
        raise DiagnosticFailure('harness_failure', 'Native menu focus did not settle')

    def exit_native(self):
        child, pid = self.process, self.process.pid
        before = self.key('s')
        self.wait('native power menu', lambda s: s.get('dialog') == 10111, after=before)
        # Select only the verified localized Exit; never activate adjacent power actions.
        for step in range(20):
            state = self.settle_focus(after=before)
            if state.get('focus') == self.focus_id and state.get('exit_label') == 'Exit' and 'Exit' in (state.get('list_item'), state.get('control_label')):
                break
            before = self.key('Down')
            self.wait('fresh state after menu navigation', lambda s: s.get('dialog') == 10111, after=before)
        else:
            raise DiagnosticFailure('harness_failure', 'Could not verify native Exit focus')
        self.capture('exit-selected')
        state = self.settle_focus(after=self.state().get('sequence', 0))
        if not (state.get('focus') == self.focus_id and state.get('exit_label') == 'Exit'
                and 'Exit' in (state.get('list_item'), state.get('control_label'))):
            raise DiagnosticFailure('harness_failure', 'Exit selection changed after capture')
        if child.poll() is not None or self.process is not child:
            raise DiagnosticFailure('harness_failure', 'Original child changed before Exit')
        self.record('native-exit-selected', pid=pid, state=state, action='Quit()', focus=self.focus_id)
        self.key('Return')
        try:
            rc = child.wait(timeout=45)
        except subprocess.TimeoutExpired:
            raise DiagnosticFailure('product_reproduction_candidate', 'Verified native Exit did not terminate original Kodi PID')
        self.archive()
        self.record('native-exit-completed', pid=pid, returncode=rc, compositor=self.compositor)
        if rc != 0:
            raise DiagnosticFailure('product_reproduction_candidate', 'Native Exit returned ' + str(rc))
        self.compositor_alive()
        settings = self.target / 'data/userdata/guisettings.xml'
        shutil.copy2(settings, self.session / 'guisettings-after.xml')
        time.sleep(1)

    def archive(self):
        if self.stdout:
            self.stdout.close()
            self.stdout = None
        if self.session:
            interesting = re.compile(r'configure|ack_configure|\.commit\(|\.frame\(|\.done\(|Apply|Resize|fullscreen|llvmpipe|WinSystemWayland', re.I)
            with (self.session / 'configure-frame-trace.txt').open('w') as output:
                for name in ('kodi-stdout.log', 'kodi.log'):
                    path = self.session / name
                    if path.exists():
                        for line in path.open(errors='replace'):
                            if interesting.search(line):
                                output.write(name + ': ' + line)

    def cleanup(self):
        if self.process is not None and self.process.poll() is None:
            self.record('failure-only-cleanup', pid=self.process.pid, accepted_as_native_exit=False)
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.archive()
        if self.keeper is not None and self.keeper.poll() is None:
            self.keeper.terminate()
            self.keeper.wait(timeout=5)
        if self.keeper_log:
            self.keeper_log.close()


def main():
    out = Path(os.environ['APERTURE_WAYLAND_OUT'])
    driver = None
    result = dict(status='harness_failure', reason='Driver did not finish')
    try:
        driver = Driver()
        driver.setup_display()
        for _ in range(4):  # Initial launch plus three normal-Exit/relaunch cycles.
            driver.start()
            driver.exit_native()
        result = dict(status='passed', launches=4, relaunches=3, clean_native_exits=4,
            skin=driver.skin, compositor_pid=driver.compositor, profile=str(driver.target / 'data'),
            scope='Synthetic Labwc headless Pixman + Kodi 21.3 native Wayland llvmpipe',
            limitations=['Not a production workaround', 'No physical Pi, display, controller, CEC or audio acceptance'], checks=driver.checks)
    except Exception as error:
        result = dict(status=getattr(error, 'category', 'harness_failure'), reason=str(error), traceback=traceback.format_exc(),
            launch=driver.launch if driver else 0, checks=driver.checks if driver else [])
        print(traceback.format_exc(), flush=True)
        if driver and driver.session:
            try:
                driver.capture('terminal-failure', ocr=True)
            except Exception:
                pass
    finally:
        if driver:
            try:
                driver.cleanup()
            except Exception:
                result['cleanup_error'] = traceback.format_exc()
                if result['status'] == 'passed':
                    result.update(status='harness_failure', reason='Cleanup failed after acceptance checks')
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print('APERTURE_WAYLAND_RESULT ' + json.dumps(result), flush=True)
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env bash
# Real Kodi 21 GUI smoke test for an isolated, disposable CI runner.
# This never installs packages, uses a user's Kodi profile, or enables RPC servers.
# Prerequisites are installed by .github/workflows/kodi-smoke.yml, not this script.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# Record the tested revision before replacing HOME. A container checkout may be
# owned by the host runner; do not disable Git ownership checks or add exceptions.
COMMIT="${GITHUB_SHA:-$(git -C "$ROOT" rev-parse HEAD)}"
[[ "$COMMIT" =~ ^[[:xdigit:]]{40}$ ]] || { echo "Invalid tested commit SHA" >&2; exit 2; }
OUT="${APERTURE_SMOKE_OUT:-$ROOT/build/kodi-smoke}"
[[ ! -d "$OUT" || -z "$(ls -A "$OUT")" ]] || { echo "Output directory must be empty" >&2; exit 2; }
mkdir -p "$OUT"
OUT="$(cd -- "$OUT" && pwd)"
RUNTIME="$(mktemp -d "${RUNNER_TEMP:-/tmp}/aperture-kodi-smoke.XXXXXXXX")"
export APERTURE_SMOKE_OUT="$OUT"
export HOME="$RUNTIME/home" KODI_DATA="$RUNTIME/data" KODI_TEMP="$OUT/logs"
export KODI_HOME="$RUNTIME/system"
export XDG_CONFIG_HOME="$HOME/.config" XDG_CACHE_HOME="$HOME/.cache"
export XDG_DATA_HOME="$HOME/.local/share" XDG_RUNTIME_DIR="$RUNTIME/run"
export DISPLAY=:91 XAUTHORITY="$RUNTIME/Xauthority"
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
mkdir -p "$HOME" "$KODI_DATA/userdata" "$KODI_TEMP" "$XDG_RUNTIME_DIR" "$OUT/screenshots"
chmod 700 "$RUNTIME" "$XDG_RUNTIME_DIR"
# This is a brand-new HOME and no real credentials or personal media are used.
printf '%s\n' "$RUNTIME" > "$OUT/runtime-path.txt"
printf '{"status":"not_run","reason":"GUI checks have not completed"}\n' > "$OUT/result.json"
KODI_PID=""; XVFB_PID=""; PULSE_PID=""; FORMAT_PID=""
cleanup() {
  local rc=$?
  trap - EXIT
  if [[ -n "$KODI_PID" ]] && kill -0 "$KODI_PID" 2>/dev/null; then
    kill -TERM "$KODI_PID" 2>/dev/null || true
    for _ in {1..30}; do kill -0 "$KODI_PID" 2>/dev/null || break; sleep 0.1; done
    kill -KILL "$KODI_PID" 2>/dev/null || true
    wait "$KODI_PID" 2>/dev/null || true
  fi
  if [[ -n "$XVFB_PID" ]]; then kill -TERM "$XVFB_PID" 2>/dev/null || true; wait "$XVFB_PID" 2>/dev/null || true; fi
  if [[ -n "$PULSE_PID" ]]; then kill -TERM "$PULSE_PID" 2>/dev/null || true; wait "$PULSE_PID" 2>/dev/null || true; fi
  if [[ -n "$FORMAT_PID" ]]; then kill -TERM "$FORMAT_PID" 2>/dev/null || true; wait "$FORMAT_PID" 2>/dev/null || true; fi
  [[ ! -f "$KODI_DATA/userdata/guisettings.xml" ]] || cp "$KODI_DATA/userdata/guisettings.xml" "$OUT/guisettings.xml"
  if [[ "$rc" -ne 0 ]]; then
    printf '\nKodi GUI smoke test FAILED (exit %s). See logs/result.json; no GUI pass is implied.\n' "$rc" >&2
    tail -100 "$KODI_TEMP/kodi.log" 2>/dev/null || true
    python3 - "$OUT/result.json" "$rc" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1]); data=json.loads(p.read_text())
if data.get('status') != 'failed':
    data.update(status='failed', reason='Smoke runner exited before all GUI assertions passed', exit_code=int(sys.argv[2]))
p.write_text(json.dumps(data, indent=2)+'\n')
PY
  fi
  exit "$rc"
}
trap cleanup EXIT

for command in python3 Xvfb xauth xdotool xdpyinfo xprop xwininfo glxinfo xwd import dpkg git pulseaudio pactl; do
  command -v "$command" >/dev/null || { echo "Missing prerequisite: $command" >&2; exit 2; }
done
KODI_BIN="$(dpkg -L kodi-bin | grep '/kodi\.bin$' | head -1)"
[[ -x "$KODI_BIN" ]] || { echo 'Kodi binary not found in kodi-bin package' >&2; exit 2; }
export KODI_BIN_HOME="$(dirname -- "$KODI_BIN")"
export KODI_BINADDON_PATH="$KODI_BIN_HOME/addons"
"$KODI_BIN" --version | tee "$OUT/kodi-version.txt"
printf '%s\n' "$COMMIT" > "$OUT/commit.txt"
dpkg-query -W kodi kodi-bin kodi-data xvfb libgl1-mesa-dri > "$OUT/runtime-packages.txt"
[[ ! -f "$ROOT/dist/checksums.json" ]] || cp "$ROOT/dist/checksums.json" "$OUT/package-checksums.json"
grep -Eq 'Center 21\.3([ .]|$)' "$OUT/kodi-version.txt" || { echo 'This test requires Kodi 21.3 exactly' >&2; exit 2; }
[[ -f "$ROOT/build/skin.aperture/xml/Home.xml" ]] || { echo 'Run python3 tools/build.py first' >&2; exit 2; }
[[ -f "$ROOT/build/skin.aperture/APERTURE_BUILD.json" && -f "$ROOT/build/skin.aperture/xml/DialogConfirm.xml" && -f "$ROOT/build/skin.aperture/fonts/NotoSans-Regular.ttf" ]] || { echo 'A complete materialized skin is required' >&2; exit 2; }

# Copy distro data into the fixture, materializing its external font/JS links.
# Bundle the two test subjects and a read-only observer in this ephemeral KODI_HOME.
# This tests rendering/navigation, NOT the ZIP-install or keep/revert experience.
APERTURE_SOURCE_ROOT="$ROOT" python3 - <<'PY_COPY'
import os
from pathlib import Path
import shutil
source=Path('/usr/share/kodi'); destination=Path(os.environ['KODI_HOME'])
shutil.copytree(source, destination, symlinks=True)
for original in source.rglob('*'):
    if not original.is_symlink():
        continue
    target=original.resolve()
    # Debian 13's Kodi data may point at a removed Roboto-Thin package path.
    # Use the same genuine font already present in our pinned Estuary baseline.
    if not target.is_file() and original.relative_to(source).as_posix() == 'addons/skin.estuary/fonts/Roboto-Thin.ttf':
        target=Path(os.environ['APERTURE_SOURCE_ROOT'])/'build/skin.aperture/fonts/Roboto-Thin.ttf'
    if not target.is_file():
        raise RuntimeError(f'Unresolved distro data link: {original} -> {target}')
    copied=destination/original.relative_to(source)
    copied.unlink()
    shutil.copy2(target, copied)
PY_COPY
cp -a "$ROOT/build/skin.aperture" "$KODI_HOME/addons/skin.aperture"
cp "$ROOT/tools/notification_qa.py" "$KODI_HOME/notification_qa.py"
mkdir -p "$OUT/notifications"
mkdir -p "$KODI_HOME/addons/service.aperture.cismoke"
cat > "$KODI_HOME/addons/service.aperture.cismoke/addon.xml" <<'XML'
<addon id="service.aperture.cismoke" name="Aperture CI observer" version="1.0.0" provider-name="Aperture CI">
  <requires><import addon="xbmc.python" version="3.0.1"/></requires>
  <extension point="xbmc.service" library="service.py"/>
  <extension point="xbmc.addon.metadata"><summary lang="en_GB">Read-only ephemeral test observer</summary><platform>all</platform><license>GPL-3.0-or-later</license></extension>
</addon>
XML
cat > "$KODI_HOME/addons/service.aperture.cismoke/service.py" <<'PY'
"""Observe real Kodi GUI state; never invoke actions or network APIs."""
import json
import os
import time
import traceback
from pathlib import Path
import xbmc
import xbmcgui

out = Path(os.environ['APERTURE_SMOKE_OUT'])
monitor = xbmc.Monitor()
sequence = 0
try:
    with (out / 'states.jsonl').open('a', buffering=1) as history:
        while not monitor.abortRequested():
            sequence += 1
            window_id = xbmcgui.getCurrentWindowId()
            dialog_id = xbmcgui.getCurrentWindowDialogId()
            try:
                focus = int(xbmc.getInfoLabel('System.CurrentControlId'))
            except (TypeError, ValueError):
                focus = -1
            dialog_focus = focus if dialog_id != 9999 else -1
            state = {
                'sequence': sequence, 'time': time.time(), 'pid': os.getpid(),
                'skin': xbmc.getSkinDir(), 'window': window_id,
                'dialog': dialog_id, 'focus': focus, 'dialog_focus': dialog_focus,
                'window_label': xbmc.getInfoLabel('System.CurrentWindow'),
                'control_label': xbmc.getInfoLabel('System.CurrentControl'),
                'list_item': xbmc.getInfoLabel('ListItem.Label'),
                'folder': xbmc.getInfoLabel('Container.FolderPath'),
                'library_state': xbmc.getInfoLabel('Container.Property(Aperture.LibraryState)'),
                'game_plugin_enabled': bool(xbmc.getCondVisibility('System.AddonIsEnabled(plugin.games.aperture)')),
                'width': xbmcgui.getScreenWidth(), 'height': xbmcgui.getScreenHeight(),
            }
            payload = json.dumps(state)
            history.write(payload + '\n')
            temporary = out / 'state.tmp'
            temporary.write_text(payload)
            temporary.replace(out / 'state.json')
            if monitor.waitForAbort(0.15):
                break
except Exception:
    (out / 'observer-error.txt').write_text(traceback.format_exc())
    raise
PY
python3 - <<'PY'
import os, pathlib, xml.etree.ElementTree as ET
p=pathlib.Path(os.environ['KODI_HOME'])/'system/addon-manifest.xml'
tree=ET.parse(p)
for name in ('skin.aperture', 'service.aperture.cismoke'):
    if not any(e.text == name for e in tree.getroot().findall('addon')):
        ET.SubElement(tree.getroot(), 'addon').text=name
tree.write(p, encoding='utf-8', xml_declaration=True)
PY
cat > "$KODI_DATA/userdata/guisettings.xml" <<'XML'
<settings version="2">
  <setting id="lookandfeel.skin">skin.estuary</setting>
  <setting id="lookandfeel.enablerssfeeds">false</setting>
  <setting id="input.enablemouse">false</setting>
  <setting id="services.webserver">false</setting>
  <setting id="services.esenabled">false</setting>
  <setting id="services.esallinterfaces">false</setting>
  <setting id="services.zeroconf">false</setting>
  <setting id="services.wsdiscovery">false</setting>
  <setting id="services.airplay">false</setting>
  <setting id="services.upnp">false</setting>
  <setting id="services.upnpserver">false</setting>
  <setting id="services.upnprenderer">false</setting>
  <setting id="addons.unknownsources">false</setting>
  <setting id="screensaver.mode"></setting>
  <resolutions/>
  <viewstates/>
  <skinsettings/>
</settings>
XML
cat > "$KODI_DATA/userdata/advancedsettings.xml" <<'XML'
<advancedsettings><loglevel hide="false">1</loglevel></advancedsettings>
XML
mkdir -p "$KODI_DATA/userdata/keymaps"
cat > "$KODI_DATA/userdata/keymaps/ci.xml" <<'XML'
<keymap><global><keyboard><i>ActivateWindow(10032,lookandfeel.skin)</i></keyboard></global><Home><keyboard><i>ActivateWindow(10032,lookandfeel.skin)</i></keyboard></Home></keymap>
XML
python3 - <<'PY'
import os, pathlib, xml.etree.ElementTree as ET
p=pathlib.Path(os.environ['KODI_DATA'])/'userdata/keymaps/ci.xml'
tree=ET.parse(p)
for scope in ('global','Home'):
    ET.SubElement(tree.find('./'+scope+'/keyboard'),'n').text='RunScript('+str(pathlib.Path(os.environ['KODI_HOME'])/'notification_qa.py')+')'
tree.write(p,encoding='utf-8',xml_declaration=True)
PY
# Synthetic loopback Format server and read-only player observer. No user data.
python3 "$ROOT/tests/kodi_format_fixture.py" prepare --runtime "$RUNTIME" --out "$OUT"
python3 "$ROOT/tests/kodi_format_fixture.py" serve --runtime "$RUNTIME" > "$KODI_TEMP/format-server.log" 2>&1 &
FORMAT_PID=$!
for _ in {1..100}; do
  [[ -f "$OUT/format-ready.json" ]] && break
  kill -0 "$FORMAT_PID" 2>/dev/null || { cat "$KODI_TEMP/format-server.log"; exit 3; }
  sleep 0.1
done
[[ -f "$OUT/format-ready.json" ]] || { echo 'Format fixture did not become ready'; exit 3; }
export APERTURE_FORMAT_DRIVER="$ROOT/tools/ci_format_driver.py"
# Private, clocked discard audio; never use a host server, TCP or hardware sink.
export PULSE_RUNTIME_PATH="$RUNTIME/pulse" PULSE_STATE_PATH="$RUNTIME/pulse-state"
export PULSE_SERVER="unix:$RUNTIME/pulse/native" PULSE_COOKIE="$RUNTIME/pulse/cookie"
export PULSE_CLIENTCONFIG="$RUNTIME/pulse/client.conf" PULSE_SINK=aperture_format_qa
mkdir -m 700 "$PULSE_STATE_PATH"
pulseaudio --daemonize=no --system=no --use-pid-file=no --exit-idle-time=-1 \
  --high-priority=no --realtime=no --disable-shm=yes --disallow-module-loading=yes \
  --log-target=stderr --log-level=info -n --file="$RUNTIME/pulse/default.pa" \
  > "$KODI_TEMP/pulseaudio.log" 2>&1 &
PULSE_PID=$!
for _ in {1..100}; do
  pactl info > "$OUT/pulse-info.txt" 2>/dev/null && break
  kill -0 "$PULSE_PID" 2>/dev/null || { cat "$KODI_TEMP/pulseaudio.log"; exit 3; }
  sleep 0.1
done
pactl --format=json list sinks > "$OUT/pulse-sinks.json"
pactl --format=json list modules > "$OUT/pulse-modules.json"
python3 - "$OUT" <<'PY'
import json, pathlib, sys
out=pathlib.Path(sys.argv[1])
sinks=json.loads((out/'pulse-sinks.json').read_text())
modules=json.loads((out/'pulse-modules.json').read_text())
assert len(sinks)==1 and sinks[0]['name']=='aperture_format_qa', 'Expected only the private discard sink'
assert {m['name'] for m in modules}=={'module-native-protocol-unix','module-null-sink'}, 'Unexpected PulseAudio module'
PY
# Do not relax X authentication or expose X11 on TCP.
touch "$XAUTHORITY"
xauth -f "$XAUTHORITY" add "$DISPLAY" . "$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
Xvfb "$DISPLAY" -auth "$XAUTHORITY" -screen 0 1920x1080x24 -nolisten tcp +extension GLX +render > "$KODI_TEMP/xvfb.log" 2>&1 &
XVFB_PID=$!
for _ in {1..100}; do
  xdpyinfo >/dev/null 2>&1 && break
  kill -0 "$XVFB_PID" 2>/dev/null || { cat "$KODI_TEMP/xvfb.log"; exit 3; }
  sleep 0.1
done
xdpyinfo > "$OUT/xdpyinfo.txt"
glxinfo -B | tee "$OUT/glxinfo.txt"
grep -qi 'llvmpipe\|softpipe' "$OUT/glxinfo.txt" || { echo 'Software GL renderer was not established' >&2; exit 3; }
"$KODI_BIN" --windowing=x11 --gl-interface=glx --audio-backend=pulseaudio --debug -fs > "$KODI_TEMP/kodi-stdout.log" 2>&1 &
KODI_PID=$!
export APERTURE_KODI_PID="$KODI_PID" APERTURE_KODI_BIN="$KODI_BIN" APERTURE_SKIN_HOME="$ROOT/build/skin.aperture/xml/Home.xml"

python3 - <<'PY'
"""Drive actual keyboard navigation; only measured Kodi state can satisfy checks."""
import base64
from collections import deque
import json
import os
from pathlib import Path
import subprocess
import time
import traceback
import xml.etree.ElementTree as ET
from PIL import Image, ImageStat

out=Path(os.environ['APERTURE_SMOKE_OUT'])
pid=int(os.environ['APERTURE_KODI_PID'])
checks=[]
HOME, SETTINGS, GAMES = 10000, 10004, 10821  # Kodi 21 WindowIDs.h
last={}

def state():
    global last
    try:
        last=json.loads((out/'state.json').read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return last

def wait_for(description, predicate, timeout=30, after=0):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        os.kill(pid, 0)
        s=state()
        if s.get('pid')==pid and s.get('sequence', 0)>after and time.time()-s.get('time', 0)<3 and predicate(s):
            return s
        if (out/'observer-error.txt').exists():
            raise AssertionError((out/'observer-error.txt').read_text())
        time.sleep(0.1)
    raise AssertionError(f'Timed out: {description}; last actual state={last}')

def screenshot(name):
    time.sleep(0.7)  # Let the observed window animation paint before capture.
    folder=out/'screenshots'; png=folder/(name+'.png')
    subprocess.run(['xwd','-root','-silent','-out',str(folder/(name+'.xwd'))],check=True,timeout=10)
    subprocess.run(['import','-window','root',str(png)],check=True,timeout=10)
    with Image.open(png) as im:
        rgb=im.convert('RGB')
        if rgb.size != (1920,1080) or max(ImageStat.Stat(rgb).stddev)<3:
            raise AssertionError(f'{name}: screenshot missing full-size nonblank rendered pixels')
        rgb.thumbnail((640,360))
        small=folder/(name+'.preview.jpg'); rgb.save(small,quality=65)
    # Bounded fallback evidence when a connector cannot download Actions artifacts.
    print(f'APERTURE_SCREENSHOT_BASE64_BEGIN {small.name}',flush=True)
    print(base64.b64encode(small.read_bytes()).decode(),flush=True)
    print(f'APERTURE_SCREENSHOT_BASE64_END {small.name}',flush=True)
    checks.append({'check':name,'state':state(),'screenshot':str(png.relative_to(out))})

def press(key):
    before=state().get('sequence',0)
    subprocess.run(['xdotool','key','--clearmodifiers',key],check=True,timeout=10)
    return before

def verify_notifications(stage):
    folder=out/'notifications'
    (folder/'request.txt').write_text(stage)
    result_path=folder/(stage+'.json')
    press('n')
    start_deadline=time.monotonic()+10
    deadline=time.monotonic()+190
    while time.monotonic()<deadline:
        os.kill(pid,0)
        if not result_path.exists() and time.monotonic()>start_deadline:
            raise AssertionError('Notification CI shortcut did not start fixture: '+stage)
        if result_path.exists():
            result=json.loads(result_path.read_text())
            if result.get('status')=='failed':
                raise AssertionError('Notification lifetime: '+str(result))
            if result.get('status')=='passed':
                for check in result['checks']:
                    png=folder/check['screenshot']
                    with Image.open(png) as im:
                        rgb=im.convert('RGB')
                        if rgb.size != (1920,1080) or max(ImageStat.Stat(rgb).stddev)<3:
                            raise AssertionError('Notification screenshot missing rendered pixels')
                        rgb.thumbnail((640,360))
                        small=png.with_suffix('.preview.jpg'); rgb.save(small,quality=70)
                    print(f'APERTURE_SCREENSHOT_BASE64_BEGIN {small.name}',flush=True)
                    print(base64.b64encode(small.read_bytes()).decode(),flush=True)
                    print(f'APERTURE_SCREENSHOT_BASE64_END {small.name}',flush=True)
                checks.append({'check':'notification-lifetime-'+stage,'result':result})
                return
        time.sleep(.1)
    raise AssertionError('Notification lifetime did not finish: '+stage)


def labelled(s, text):
    return any(s.get(key,'').strip()==text for key in ('list_item','control_label'))

def next_observation(key):
    before=press(key)
    return wait_for(f'fresh state after {key}',lambda s:True,after=before)

def focus_signature(s):
    return tuple(s.get(key) for key in ('window','dialog','focus','dialog_focus','list_item','control_label'))

def settle_focus(timeout=8):
    deadline=time.monotonic()+timeout; previous=None; same_since=0; frames=0; sequence=-1
    while time.monotonic()<deadline:
        current=state(); signature=focus_signature(current)
        if current.get('sequence')!=sequence:
            sequence=current.get('sequence')
            if signature==previous: frames+=1
            else: previous=signature; frames=1; same_since=time.monotonic()
            if frames>=3 and time.monotonic()-same_since>=.3: return current
        time.sleep(.1)
    raise AssertionError('Focus failed to settle: '+str(state()))

def find_label(text, direction, max_steps):
    for step in range(max_steps+1):
        current=settle_focus()
        if labelled(current,text): return
        if step==max_steps: break
        signature=focus_signature(current); before=press(direction)
        wait_for('focus moves toward '+text,lambda s:focus_signature(s)!=signature,after=before)
    raise AssertionError(f'Could not focus visible item {text!r}; actual state={state()}')

# Use source navigation edges to support vertical and horizontal experiment branches,
# but confirm every edge through actual focus changes, not source assertions.
graph={}
for node in ET.parse(os.environ['APERTURE_SKIN_HOME']).getroot().iter('control'):
    if node.get('id','').isdigit():
        graph[int(node.get('id'))]={}
        for key,tag in [('Left','onleft'),('Right','onright'),('Up','onup'),('Down','ondown')]:
            target=node.findtext(tag,'').strip()
            if target.isdigit(): graph[int(node.get('id'))][key]=int(target)

def focus(target):
    current=wait_for('Home before focus navigation',lambda s:s.get('window')==HOME and s.get('skin')=='skin.aperture')
    # Home enters before its opening animation accepts input. Wait for the
    # complete source-defined reveal, then inspect a fresh stable focus.
    time.sleep(.85)
    current=settle_focus()
    start=current['focus']; todo=deque([(start,[])]); visited={start}; path=None
    while todo:
        at,route=todo.popleft()
        if at==target: path=route; break
        for key,nxt in graph.get(at,{}).items():
            if nxt not in visited:
                visited.add(nxt);todo.append((nxt,route+[(key,nxt)]))
    if path is None: raise AssertionError(f'No arrow-key path from real focus {start} to {target}')
    for key,nxt in path:
        before=press(key)
        wait_for(f'{key} focuses {nxt}',lambda s:s.get('window')==HOME and s.get('focus')==nxt,after=before)

try:
    wait_for('Estuary startup and observer',lambda s:s.get('skin')=='skin.estuary' and s.get('window')==HOME,timeout=90)
    windows=subprocess.check_output(['xdotool','search','--onlyvisible','--class','^Kodi( from Debian)?$'],text=True,timeout=10).split()
    if len(windows)!=1: raise AssertionError(f'Expected one visible Kodi X window, found {windows}')
    window=windows[0]
    subprocess.run(['xdotool','windowfocus','--sync',window],check=True,timeout=10)
    screenshot('01-estuary-baseline')

    def choose_skin(name, expected_skin, accept=True):
        before=press('i')
        wait_for('Interface settings',lambda s:s.get('window')==10032 and s.get('dialog')==9999,after=before)
        current=settle_focus()
        if current.get('focus') in (3,-200):
            before=press('Right')
            wait_for('Settings content focused',lambda s:s.get('focus') not in (3,-200),after=before)
        find_label('Skin','Down',8)
        before=press('Return')
        wait_for('Skin chooser',lambda s:s.get('dialog')==12000,after=before)
        # Small installed-skin list, no downloads or repository configuration.
        find_label(name,'Down',5)
        before=press('Return')
        wait_for('Keep/revert dialog',lambda s:s.get('skin')==expected_skin and s.get('dialog')==10100,timeout=40,after=before)
        screenshot('skin-confirm-'+expected_skin)
        if accept:
            settle_focus()
            if state().get('dialog_focus')!=11:
                before=press('Left')
                wait_for('Yes focused',lambda s:s.get('dialog')==10100 and s.get('dialog_focus')==11,after=before)
            settle_focus()
            if state().get('dialog_focus')!=11: raise AssertionError('Yes button not visibly focused')
            before=press('Return')
            wait_for('Accepted '+name,lambda s:s.get('skin')==expected_skin and s.get('dialog')==9999,after=before)
        else:
            previous='skin.aperture' if expected_skin=='skin.estuary' else 'skin.estuary'
            wait_for('Automatic skin rollback',lambda s:s.get('skin')==previous and s.get('dialog')==9999,timeout=40)
        for _ in range(5):
            if state().get('window')==HOME: break
            next_observation('Escape'); time.sleep(.2)
        wait_for('Home after skin choice',lambda s:s.get('window')==HOME and s.get('dialog')==9999)
        keymap = Path(os.environ['KODI_DATA'])/'userdata/keymaps/zz-aperture-turntable.xml'
        final_skin = expected_skin if accept else previous
        if final_skin == 'skin.aperture':
            source_keymap = Path(os.environ['KODI_HOME'])/'addons/plugin.audio.aperture.format/resources/keymaps/aperture-turntable.xml'
            wait_for('Aperture loads only its owned turntable keymap',
                     lambda s:keymap.is_file() and keymap.read_bytes() == source_keymap.read_bytes()
                     and any('Loading ' in line and 'zz-aperture-turntable.xml' in line
                             for line in (Path(os.environ['KODI_TEMP'])/'kodi.log').read_text(errors='replace').splitlines()))
        else:
            wait_for('Estuary restores original keys without owned override', lambda s:not keymap.exists())
        checks.append({'check':'skin-selection-'+name+('-accepted' if accept else '-auto-reverted'),'state':state()})

    choose_skin('Aperture','skin.aperture')
    wait_for('Aperture Home focused',lambda s:s.get('focus') in graph and s.get('skin')=='skin.aperture')
    screenshot('02-aperture-home')
    verify_notifications('initial')
    for cycle in range(3):
        for control in range(100,107):
            focus(control)
            checks.append({'check':f'home-focus-{cycle}-{control}','state':state()})
        for control,expected,name in [(100,10025,'movies'),(101,10025,'television'),(102,10821,'games'),(103,10502,'music'),(104,10025,'videos'),(105,10004,'settings')]:
            focus(control); before=press('Return')
            wait_for(name+' opened',lambda s:s.get('window')==expected and s.get('skin')=='skin.aperture',after=before)
            if control == 103:
                wait_for('Music opens the direct Format shelf', lambda s:s.get('window')==10502
                    and s.get('dialog')==9999 and s.get('folder')=='plugin://plugin.audio.aperture.format/?action=albums', after=before)
            if control in (100,101,104):
                wait_for('Unscanned video sources are reachable', lambda s:s.get('folder')=='sources://video/', after=before)
            if cycle==0: screenshot('03-'+name)
            if control == 103:
                # Check the controller-equivalent Back route, including restored
                # Home focus, on every direct entry/reentry into Format.
                settle_focus()
                before=press('BackSpace')
                wait_for('Format Back returns to Home Music', lambda s:s.get('window')==HOME
                    and s.get('dialog')==9999 and s.get('focus')==103, after=before)
            for _ in range(5):
                if state().get('window')==HOME: break
                next_observation('Escape'); time.sleep(.2)
            wait_for(name+' Back to Home',lambda s:s.get('window')==HOME and s.get('dialog')==9999)
            checks.append({'check':f'{name}-back-{cycle}','state':state()})
        focus(106); before=press('Return')
        wait_for('Power menu',lambda s:s.get('dialog')==10111,after=before)
        before=press('Escape')
        wait_for('Power dismissed',lambda s:s.get('window')==HOME and s.get('dialog')==9999,after=before)
    choose_skin('Estuary','skin.estuary',accept=False)
    choose_skin('Estuary','skin.estuary')
    screenshot('04-estuary-recovery')
    choose_skin('Aperture','skin.aperture')
    screenshot('05-aperture-restored')
    verify_notifications('after-reload')
    # Observe continued real GUI activity; stale observer data cannot pass.
    before=state()['sequence']; time.sleep(10)
    wait_for('Idle Home still responsive',lambda s:s.get('window')==HOME and s.get('skin')=='skin.aperture',after=before)
    focus(105); before=press('Return')
    wait_for('Settings still responds after idle',lambda s:s.get('window')==SETTINGS,after=before)
    next_observation('Escape')
    wait_for('Final Home',lambda s:s.get('window')==HOME)
    screenshot('06-final-home')
    import importlib.util
    spec=importlib.util.spec_from_file_location('ci_format_driver', os.environ['APERTURE_FORMAT_DRIVER'])
    format_driver=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(format_driver)
    format_result=format_driver.run(globals())
    checks.extend(format_result['checks'])
    log=(out/'logs/kodi.log').read_text(errors='replace')
    # Omega's LoadTTF and ReloadTTFFonts use different messages. Reject both,
    # including an initial load failure that subsequently falls back to Arial.
    fatal_markers=('Error loading skin', 'failed to load skin', 'EXCEPTION Thrown (PythonToCppException)',
                   'unable to load font', "Couldn't load font", "Couldn't re-load font file")
    errors=[line for line in log.splitlines() if any(marker.lower() in line.lower() for marker in fatal_markers)]
    if errors: raise AssertionError('Skin errors in Kodi log: '+'\n'.join(errors))
    result={'status':'passed','scope':'Kodi 21.3 actual GUI activation, repeated navigation, accepted skin switch, automatic recovery and synthetic Format HTTP playback',
            'checks':checks,'limitations':['No physical Pi/controller/audio/core acceptance','No ZIP-installer interaction yet','No claim of reproducing the original Pi freeze']}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: real Kodi 21.3 skin activation, repeated native navigation and recovery.',flush=True)
except Exception as exc:
    try: screenshot('failure')
    except Exception: pass
    result={'status':'failed','reason':str(exc),'checks':checks,'last_state':last,'traceback':traceback.format_exc()}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    raise
PY

# End the first process cleanly before the independent fresh ZIP acceptance run.
kill -TERM "$KODI_PID"
for _ in {1..100}; do kill -0 "$KODI_PID" 2>/dev/null || break; sleep 0.1; done
if kill -0 "$KODI_PID" 2>/dev/null; then
  echo 'Kodi did not shut down cleanly before ZIP acceptance' >&2
  exit 1
fi
wait "$KODI_PID" || true
KODI_PID=""
python3 "$ROOT/tools/zip_smoke_driver.py" --root "$ROOT" --runtime "$RUNTIME" --out "$OUT/zip-install" --binary "$KODI_BIN"
python3 - "$OUT" <<'PY'
import json, pathlib, sys
out=pathlib.Path(sys.argv[1]); p=out/'result.json'
result=json.loads(p.read_text()); zip_result=json.loads((out/'zip-install/result.json').read_text())
if zip_result.get('status')!='passed': raise RuntimeError('Fresh ZIP acceptance did not pass')
result['zip_acceptance']=zip_result
result['limitations']=[s for s in result['limitations'] if s!='No ZIP-installer interaction yet']
result['scope'] += '; fresh ZIP installation, process restart persistence and accepted Estuary recovery'
p.write_text(json.dumps(result,indent=2)+'\n')
PY

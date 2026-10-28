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
OUT="${APETURE_SMOKE_OUT:-$ROOT/build/kodi-smoke}"
mkdir -p "$OUT"
OUT="$(cd -- "$OUT" && pwd)"
RUNTIME="$(mktemp -d "${RUNNER_TEMP:-/tmp}/apeture-kodi-smoke.XXXXXXXX")"
export APETURE_SMOKE_OUT="$OUT"
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
KODI_PID=""; XVFB_PID=""
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

for command in python3 Xvfb xauth xdotool xdpyinfo xprop xwininfo glxinfo xwd import dpkg git; do
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
grep -Eq 'Center 21\.' "$OUT/kodi-version.txt" || { echo 'This test requires Kodi 21, not another major version' >&2; exit 2; }
[[ -f "$ROOT/build/skin.apeture/xml/Home.xml" ]] || { echo 'Run python3 tools/build.py first' >&2; exit 2; }
[[ -f "$ROOT/build/skin.apeture/APETURE_BUILD.json" && -f "$ROOT/build/skin.apeture/xml/DialogConfirm.xml" && -f "$ROOT/build/skin.apeture/fonts/NotoSans-Regular.ttf" ]] || { echo 'A complete materialized skin is required' >&2; exit 2; }

# Copy distro data into the fixture, materializing its external font/JS links.
# Bundle the two test subjects and a read-only observer in this ephemeral KODI_HOME.
# This tests rendering/navigation, NOT the ZIP-install or keep/revert experience.
APETURE_SOURCE_ROOT="$ROOT" python3 - <<'PY_COPY'
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
        target=Path(os.environ['APETURE_SOURCE_ROOT'])/'build/skin.apeture/fonts/Roboto-Thin.ttf'
    if not target.is_file():
        raise RuntimeError(f'Unresolved distro data link: {original} -> {target}')
    copied=destination/original.relative_to(source)
    copied.unlink()
    shutil.copy2(target, copied)
PY_COPY
cp -a "$ROOT/build/skin.apeture" "$KODI_HOME/addons/skin.apeture"
cp -a "$ROOT/addons/plugin.games.apeture" "$KODI_HOME/addons/plugin.games.apeture"
mkdir -p "$KODI_HOME/addons/service.apeture.cismoke"
cat > "$KODI_HOME/addons/service.apeture.cismoke/addon.xml" <<'XML'
<addon id="service.apeture.cismoke" name="Apeture CI observer" version="1.0.0" provider-name="Apeture CI">
  <requires><import addon="xbmc.python" version="3.0.1"/></requires>
  <extension point="xbmc.service" library="service.py"/>
  <extension point="xbmc.addon.metadata"><summary lang="en_GB">Read-only ephemeral test observer</summary><platform>all</platform><license>GPL-3.0-or-later</license></extension>
</addon>
XML
cat > "$KODI_HOME/addons/service.apeture.cismoke/service.py" <<'PY'
"""Observe real Kodi GUI state; never invoke actions or network APIs."""
import json
import os
import time
import traceback
from pathlib import Path
import xbmc
import xbmcgui

out = Path(os.environ['APETURE_SMOKE_OUT'])
monitor = xbmc.Monitor()
sequence = 0
try:
    with (out / 'states.jsonl').open('a', buffering=1) as history:
        while not monitor.abortRequested():
            sequence += 1
            window_id = xbmcgui.getCurrentWindowId()
            dialog_id = xbmcgui.getCurrentWindowDialogId()
            try:
                dialog_focus = xbmcgui.Window(dialog_id).getFocusId() if dialog_id != 9999 else -1
            except (RuntimeError, ValueError):
                dialog_focus = -1
            try:
                focus = xbmcgui.Window(window_id).getFocusId()
            except (RuntimeError, ValueError):
                focus = -1
            state = {
                'sequence': sequence, 'time': time.time(), 'pid': os.getpid(),
                'skin': xbmc.getSkinDir(), 'window': window_id,
                'dialog': dialog_id, 'focus': focus, 'dialog_focus': dialog_focus,
                'window_label': xbmc.getInfoLabel('System.CurrentWindow'),
                'control_label': xbmc.getInfoLabel('System.CurrentControl'),
                'list_item': xbmc.getInfoLabel('ListItem.Label'),
                'folder': xbmc.getInfoLabel('Container.FolderPath'),
                'library_state': xbmc.getInfoLabel('Container.Property(Apeture.LibraryState)'),
                'game_plugin_enabled': bool(xbmc.getCondVisibility('System.AddonIsEnabled(plugin.games.apeture)')),
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
for name in ('skin.apeture', 'plugin.games.apeture', 'service.apeture.cismoke'):
    if not any(e.text == name for e in tree.getroot().findall('addon')):
        ET.SubElement(tree.getroot(), 'addon').text=name
tree.write(p, encoding='utf-8', xml_declaration=True)
PY
cat > "$KODI_DATA/userdata/guisettings.xml" <<'XML'
<settings version="2">
  <setting id="lookandfeel.skin">skin.apeture</setting>
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
"$KODI_BIN" --windowing=x11 --gl-interface=glx --audio-backend=alsa --debug -fs > "$KODI_TEMP/kodi-stdout.log" 2>&1 &
KODI_PID=$!
export APETURE_KODI_PID="$KODI_PID" APETURE_SKIN_HOME="$ROOT/build/skin.apeture/xml/Home.xml"

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

out=Path(os.environ['APETURE_SMOKE_OUT'])
pid=int(os.environ['APETURE_KODI_PID'])
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
    print(f'APETURE_SCREENSHOT_BASE64_BEGIN {small.name}',flush=True)
    print(base64.b64encode(small.read_bytes()).decode(),flush=True)
    print(f'APETURE_SCREENSHOT_BASE64_END {small.name}',flush=True)
    checks.append({'check':name,'state':state(),'screenshot':str(png.relative_to(out))})

def press(key):
    before=state().get('sequence',0)
    subprocess.run(['xdotool','key','--clearmodifiers',key],check=True,timeout=10)
    return before


def labelled(s, text):
    return any(s.get(key,'').strip()==text for key in ('list_item','control_label'))

def next_observation(key):
    before=press(key)
    return wait_for(f'fresh state after {key}',lambda s:True,after=before)

def find_label(text, direction, max_steps):
    # The bound comes from the small menu under test; never choose an unobserved item.
    for _ in range(max_steps+1):
        if labelled(state(),text): return
        next_observation(direction)
        time.sleep(0.2)
    raise AssertionError(f'Could not focus visible item {text!r}; actual state={state()}')

# Use source navigation edges to support vertical and horizontal experiment branches,
# but confirm every edge through actual focus changes, not source assertions.
graph={}
for node in ET.parse(os.environ['APETURE_SKIN_HOME']).getroot().iter('control'):
    if node.get('id','').isdigit():
        graph[int(node.get('id'))]={}
        for key,tag in [('Left','onleft'),('Right','onright'),('Up','onup'),('Down','ondown')]:
            target=node.findtext(tag,'').strip()
            if target.isdigit(): graph[int(node.get('id'))][key]=int(target)

def focus(target):
    current=wait_for('Home before focus navigation',lambda s:s.get('window')==HOME and s.get('skin')=='skin.apeture')
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
    wait_for('actual Apeture Home and observer',lambda s:s.get('skin')=='skin.apeture' and s.get('window')==HOME and s.get('focus') in graph,timeout=90)
    # Kodi 21 X11 sets WM_CLASS/WM_NAME but does not set _NET_WM_PID.
    # Only this Kodi process runs on our fresh authenticated display; also require
    # the in-process observer PID, one exact app class/title, and fullscreen size.
    windows=subprocess.check_output(['xdotool','search','--onlyvisible','--class','^Kodi( from Debian)?$'],text=True,timeout=10).split()
    if len(windows)!=1: raise AssertionError(f'Expected one visible Kodi X window, found {windows}')
    window=windows[0]
    title=subprocess.check_output(['xdotool','getwindowname',window],text=True,timeout=10).strip()
    if title not in ('Kodi', 'Kodi from Debian'): raise AssertionError(f'Unexpected X window title: {title}')
    geometry=subprocess.check_output(['xdotool','getwindowgeometry','--shell',window],text=True,timeout=10)
    dimensions=dict(line.split('=',1) for line in geometry.splitlines() if '=' in line)
    if dimensions.get('WIDTH')!='1920' or dimensions.get('HEIGHT')!='1080':
        raise AssertionError(f'Kodi window is not fullscreen: {geometry}')
    properties=subprocess.check_output(['xprop','-id',window,'WM_CLASS','WM_NAME','_NET_WM_PID'],text=True,timeout=10)
    (out/'x-window.txt').write_text(properties+'\n'+geometry)
    subprocess.run(['xdotool','windowfocus','--sync',window],check=True,timeout=10)
    if not state().get('game_plugin_enabled'): raise AssertionError('Apeture game companion is not enabled')
    screenshot('01-home')
    for control in range(9100,9106):
        focus(control)
        checks.append({'check':f'home-focus-{control}','state':state()})
    focus(9105)
    before=press('Return')
    wait_for('Settings opened by Home button',lambda s:s.get('window')==SETTINGS and s.get('skin')=='skin.apeture',after=before)
    screenshot('02-settings')
    before=press('Escape')
    wait_for('Back from Settings to Home',lambda s:s.get('window')==HOME and s.get('skin')=='skin.apeture',after=before)
    screenshot('03-home-after-settings')
    focus(9100)
    before=press('Return')
    wait_for('Apeture games plugin directory',lambda s:s.get('window')==GAMES and s.get('folder','').startswith('plugin://plugin.games.apeture') and s.get('library_state')=='unconfigured',after=before)
    screenshot('04-games-unconfigured')
    before=press('Escape')
    wait_for('Back from Games to Home',lambda s:s.get('window')==HOME and s.get('skin')=='skin.apeture',after=before)
    screenshot('05-home-after-games')
    # Repeat the Settings round trip to catch stale focus or one-shot navigation.
    focus(9105); before=press('Return')
    wait_for('Repeated Settings entry',lambda s:s.get('window')==SETTINGS,after=before)
    before=press('Escape')
    wait_for('Repeated Settings exit',lambda s:s.get('window')==HOME,after=before)
    checks.append({'check':'repeat-settings-round-trip','state':state()})
    # Empty-library destinations must open native windows, not just focus on Home.
    for control,expected,name in [(9101,10025,'movies'),(9102,10025,'tv'),(9103,10502,'music'),(9104,10003,'files')]:
        focus(control); before=press('Return')
        wait_for(f'{name} destination',lambda s:s.get('window')==expected and s.get('skin')=='skin.apeture',after=before)
        screenshot('06-'+name)
        before=press('Escape')
        wait_for(f'Back from {name}',lambda s:s.get('window')==HOME and s.get('dialog')==9999,after=before)
        checks.append({'check':name+'-back','state':state()})
    # Open the unconfigured game-library settings and Cancel without choosing files.
    focus(9100); before=press('Return')
    wait_for('Games for configuration test',lambda s:s.get('window')==GAMES and s.get('library_state')=='unconfigured',after=before)
    find_label('Choose your ROM folder to get started…','Down',3)
    before=press('Return')
    wait_for('Game-library settings dialog',lambda s:s.get('dialog')==10140,after=before)
    screenshot('07-game-config')
    before=press('Escape')
    wait_for('Cancel game-library settings',lambda s:s.get('window')==GAMES and s.get('dialog')==9999 and s.get('library_state')=='unconfigured',after=before)
    checks.append({'check':'game-config-cancel','state':state()})
    before=press('Escape')
    wait_for('Home after game settings Cancel',lambda s:s.get('window')==HOME,after=before)
    # Only open/dismiss Power: never select a shutdown, reboot or suspend action.
    focus(9200); before=press('Return')
    wait_for('Power menu dialog',lambda s:s.get('dialog')==10111,after=before)
    screenshot('08-power-menu')
    before=press('Escape')
    wait_for('Dismiss Power menu',lambda s:s.get('window')==HOME and s.get('dialog')==9999,after=before)
    focus(9201); before=press('Return')
    wait_for('Empty Favourites browser',lambda s:s.get('window')==10060,after=before)
    screenshot('09-favourites')
    before=press('Escape')
    wait_for('Back from Favourites',lambda s:s.get('window')==HOME and s.get('dialog')==9999,after=before)
    checks.append({'check':'utilities-dismissed','state':state()})
    # Exercise Kodi's own skin chooser and automatic rollback via keyboard only.
    # The temporary profile is disposable, and no keep-confirmation is accepted.
    focus(9105); before=press('Return')
    wait_for('Settings for skin chooser',lambda s:s.get('window')==SETTINGS,after=before)
    before=press('Down')
    wait_for('Settings categories',lambda s:s.get('window')==SETTINGS and s.get('focus')==9001,after=before)
    next_observation('Down')  # Second row of the observed four-column Settings grid.
    find_label('Interface','Right',3)
    before=press('Return')
    wait_for('Interface settings',lambda s:s.get('window')==10032,after=before)
    next_observation('Right')
    screenshot('10-interface-settings')
    before=press('Return')
    wait_for('Native skin-selection dialog',lambda s:s.get('dialog')==12000,after=before)
    screenshot('11-skin-chooser')
    find_label('Estuary','Down',5)
    before=press('Return')
    wait_for('Native skin keep/revert confirmation',lambda s:s.get('skin')=='skin.estuary' and s.get('dialog')==10100,after=before)
    screenshot('12-skin-keep-revert')
    before=state()['sequence']
    wait_for('Automatic revert to Apeture without confirmation',lambda s:s.get('skin')=='skin.apeture' and s.get('dialog')==9999,timeout=40,after=before)
    screenshot('13-skin-reverted')
    for _ in range(4):
        if state().get('window')==HOME: break
        next_observation('Escape')
        time.sleep(0.3)
    wait_for('Home after automatic skin rollback',lambda s:s.get('window')==HOME and s.get('skin')=='skin.apeture' and s.get('dialog')==9999)
    checks.append({'check':'skin-auto-revert-and-home','state':state()})
    log=(out/'logs/kodi.log').read_text(errors='replace')
    fatal_markers=('Error loading skin', 'failed to load skin', 'EXCEPTION Thrown (PythonToCppException)', 'Apeture: operation failed')
    errors=[line for line in log.splitlines() if any(marker.lower() in line.lower() for marker in fatal_markers)]
    if errors: raise AssertionError('Skin/plugin errors in Kodi log: '+'\n'.join(errors))
    result={'status':'passed','scope':'Kodi 21 keyboard navigation, empty-library destinations, dialogs, configuration Cancel and automatic skin rollback',
            'checks':checks,'limitations':['No ZIP-install or accepted skin-switch check','No Pi/hardware/controller/playback/core acceptance','No media-present playback-controls check','Visual design still needs screenshot review']}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: real Kodi GUI navigation, empty-library destinations, Power/Favourites, game config Cancel and skin auto-revert verified.',flush=True)
except Exception as exc:
    try: screenshot('failure')
    except Exception: pass
    result={'status':'failed','reason':str(exc),'checks':checks,'last_state':last,'traceback':traceback.format_exc()}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    raise
PY

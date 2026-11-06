#!/usr/bin/env python3
"""One dimensions-only perturbation, scheduled independently of Kodi's GUI loop."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import traceback

from labwc_relaunch_driver import Driver, DiagnosticFailure, home_state, main as lifecycle_main

FIRST_OFFSET = 2.903
RESTORE_OFFSET = 3.640
TIMING_TOLERANCE = .100
MODES = ((3840, 2160, 30), (1920, 1080, 60))
STAMP = re.compile(r'(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3})')
PROTOCOL = re.compile(r'\[\s*(\d+\.\d+)\].*(?:configure\(|ack_configure\(|\.commit\(|\.frame\(|\.done\(|wl_output.*mode\()')
LIMITATIONS = [
    'Dimensions-only headless custom modes, not HDMI/EDID disappearance, zero-Hz output or audio/PipeWire enumeration churn',
    'No physical Raspberry Pi, V3D driver, HDMI, CEC, controller or production profile',
    'Incident 1080p refresh is unknown; synthetic 1080p uses 60 Hz, while 4K uses 30 Hz',
    'Offsets match the first Kodi log timestamp, not necessarily the incident lifecycle phase: incident Home loaded at +0.638 s',
    '100 ms maximum request/observation lateness; measured times retained, no phase shift or timing sweep',
    'No production fix or workaround',
]


def timestamp(line):
    match = STAMP.search(line)
    return datetime.strptime(match[1], '%Y-%m-%d %H:%M:%S.%f').replace(tzinfo=timezone.utc).timestamp() if match else None


def validate_anchor(line, pid, started, observed):
    anchor = timestamp(line)
    thread = re.search(r'\bT:(\d+)\b', line)
    # Every launch has a newly created, unique KODI_TEMP directory. Also require
    # the current main-thread PID and a timestamp after this process spawn.
    if anchor is None or not thread or int(thread[1]) != pid or not started - .001 <= anchor <= observed:
        raise DiagnosticFailure('missed_injection_timing', 'First log is not fresh evidence for the current Kodi PID')
    return anchor


def current_mode(text, output):
    sections = re.split(r'(?=^\S)', text, flags=re.M)
    section = next((part for part in sections if part.startswith(output + ' ')), '')
    matches = re.findall(r'^\s+(\d+)x(\d+) px, ([\d.]+) Hz \([^\n]*current[^\n]*\)', section, re.M)
    if len(matches) != 1 or not re.search(r'^\s+Enabled: yes$', section, re.M):
        raise DiagnosticFailure('unsupported_output_mode', 'No unique enabled current mode: ' + text)
    if not re.search(r'^\s+Scale: 1(?:\.0+)?$', section, re.M) or not re.search(r'^\s+Transform: normal$', section, re.M):
        raise DiagnosticFailure('harness_failure', 'Unexpected output scaling or transform')
    width, height, refresh = matches[0]
    return int(width), int(height), float(refresh)


def require_mode(observed, expected):
    if observed[:2] != expected[:2] or abs(observed[2] - expected[2]) > .01:
        raise DiagnosticFailure('unsupported_output_mode', f'Requested {expected}, observed {observed}')


def require_timing(request_elapsed, observed_elapsed, offset):
    if not 0 <= request_elapsed - offset <= TIMING_TOLERANCE or not 0 <= observed_elapsed - offset <= TIMING_TOLERANCE:
        raise DiagnosticFailure('missed_injection_timing',
            f'Offset {offset}: requested {request_elapsed}, observed {observed_elapsed}; tolerance {TIMING_TOLERANCE}')


def milestones(log, anchor):
    markers = {'skin_includes': 'Loading skin includes from ', 'skin_loaded': 'skin loaded...',
               'home_window_init': 'Window Init (Home.xml)', 'home_file_load': 'Loading skin file: Home.xml'}
    result = {}
    for line in log.splitlines():
        stamp = timestamp(line)
        if stamp is not None:
            for name, marker in markers.items():
                if marker in line and name not in result:
                    result[name] = dict(timestamp=stamp, elapsed=stamp - anchor, line=line)
    result['incident_home_file_load_elapsed'] = .638
    home = result.get('home_file_load', {}).get('elapsed')
    result['home_loaded_before_first_change'] = home is not None and home < FIRST_OFFSET
    return result


def size_application_evidence(log, anchor):
    """Separate protocol delivery from Kodi processing/application/coalescing."""
    records = []
    for line in log.splitlines():
        kind = None
        match = re.search(r'ProcessMessages: Configure serial (\d+): size (\d+)x(\d+)', line)
        if match:
            kind = 'processed'
        else:
            match = re.search(r'ApplyNextState: Applying next state: serial (\d+) configured size (\d+)x(\d+)', line)
            if match:
                kind = 'applied'
        if kind:
            stamp = timestamp(line)
            records.append(dict(kind=kind, serial=int(match[1]), size=[int(match[2]), int(match[3])],
                                timestamp=stamp, elapsed=stamp - anchor if stamp else None, line=line))
        change = re.search(r'UpdateSizeVariables: (Configured|Surface|Buffer) size changed: (\d+)x(\d+) -> (\d+)x(\d+)', line)
        if change:
            stamp = timestamp(line)
            records.append(dict(kind=change[1].lower() + '_size_changed',
                                previous_size=[int(change[2]), int(change[3])], size=[int(change[4]), int(change[5])],
                                timestamp=stamp, elapsed=stamp - anchor if stamp else None, line=line))
    applied = any(r['kind'] == 'applied' and r['size'] == [1920, 1080] for r in records)
    processed = any(r['kind'] == 'processed' and r['size'] == [1920, 1080] for r in records)
    changed = {kind: any(r['kind'] == kind + '_size_changed' and r['size'] == [1920, 1080] for r in records)
               for kind in ('configured', 'surface', 'buffer')}
    roundtrips = {}
    for kind in ('configured', 'surface', 'buffer'):
        changes = [r for r in records if r['kind'] == kind + '_size_changed']
        down = next((i for i, r in enumerate(changes) if r['previous_size'] == [3840, 2160] and r['size'] == [1920, 1080]), None)
        roundtrips[kind] = down is not None and any(r['previous_size'] == [1920, 1080] and r['size'] == [3840, 2160]
                                                 for r in changes[down + 1:])
    return dict(records=records, intermediate_1080p_processed=processed, intermediate_1080p_applied=applied,
                intermediate_1080p_size_changes=changed,
                size_change_roundtrips=roundtrips,
                incident_applied_size_sequence_observed=applied and all(roundtrips.values()),
                interpretation=('Intermediate 1080p application observed' if applied else
                                'Intermediate 1080p application not observed; queued configures may have coalesced'))


def configure_evidence(text):
    """Require ordered real configures and final apply/ack/commit/frame completion.

    Protocol timestamps retain their original clock domain. File line indices
    establish ordering; receipt timestamps are separately recorded live.
    """
    lines = text.splitlines()
    configs, pending = [], None
    for index, line in enumerate(lines):
        match = re.search(r'xdg_toplevel[#@](\d+)\.configure\((\d+), (\d+),', line)
        if match:
            pending = dict(line_index=index, toplevel=int(match[1]), width=int(match[2]), height=int(match[3]),
                           raw_line=line, protocol_ms=float(PROTOCOL.search(line)[1]) if PROTOCOL.search(line) else None)
        serial = re.search(r'xdg_surface[#@](\d+)\.configure\((\d+)\)', line)
        if serial and pending:
            configs.append(dict(pending, surface=int(serial[1]), serial=int(serial[2]), serial_line_index=index))
            pending = None
    sizes = []
    ordered = []
    expected = [(3840, 2160), (1920, 1080), (3840, 2160)]
    for config in configs:
        size = config['width'], config['height']
        if not sizes or size != sizes[-1]:
            sizes.append(size)
        if len(ordered) < len(expected) and size == expected[len(ordered)]:
            ordered.append(config)
    if len(ordered) != 3:
        raise DiagnosticFailure('harness_configure_validation_failure', f'Actual xdg configures did not include ordered 4K/1080p/4K: {sizes}')
    final = [c for c in configs if c['line_index'] >= ordered[2]['line_index']][-1]
    if (final['width'], final['height']) != expected[-1]:
        raise DiagnosticFailure('harness_configure_validation_failure', 'Last configure did not restore 4K')
    serial, surface = final['serial'], final['surface']
    apply = next((i for i, line in enumerate(lines) if i > final['serial_line_index'] and re.search(
        rf'ApplyNextState: Applying next state: serial {serial} configured size 3840x2160', line)), None)
    ack = next((i for i, line in enumerate(lines) if i > (apply if apply is not None else len(lines)) and re.search(
        rf'xdg_surface[#@]{surface}\.ack_configure\({serial}\)', line)), None)
    bind = next((re.search(rf'get_xdg_surface\(new id xdg_surface[#@]{surface}, wl_surface[#@](\d+)\)', line)
                 for line in lines if re.search(rf'get_xdg_surface\(new id xdg_surface[#@]{surface}, wl_surface[#@](\d+)\)', line)), None)
    if bind is None:
        raise DiagnosticFailure('harness_configure_validation_failure', 'Missing xdg/wl surface binding')
    if apply is None or ack is None:
        raise DiagnosticFailure('product_reproduction_candidate', f'Restored configure serial {serial} lacks eventual ApplyNextState/ack/surface binding')
    wl_surface = int(bind[1])
    frame = next(((i, int(match[1])) for i, line in enumerate(lines) if i > ack and
                  (match := re.search(rf'wl_surface[#@]{wl_surface}\.frame\(new id wl_callback[#@](\d+)\)', line))), None)
    commit = next((i for i, line in enumerate(lines) if frame and i > frame[0] and
                   re.search(rf'wl_surface[#@]{wl_surface}\.commit\(', line)), None)
    done = next((i for i, line in enumerate(lines) if commit is not None and i > commit and
                 re.search(rf'wl_callback[#@]{frame[1]}\.done\(', line)), None)
    if frame is None or commit is None or done is None:
        raise DiagnosticFailure('product_reproduction_candidate', f'Restored serial {serial} lacks subsequent surface frame/commit/callback completion')
    return dict(configures=configs, ordered_size_configures=ordered, final_configure=final,
        final_apply_line=lines[apply], final_ack_line=lines[ack], subsequent_frame_line=lines[frame[0]],
        subsequent_commit_line=lines[commit], subsequent_frame_done_line=lines[done],
        line_order=[apply, ack, frame[0], commit, done], wl_surface=wl_surface)


class ChurnDriver(Driver):
    expected_size = (3840, 2160)

    def __init__(self):
        self.worker = None
        self.stop = threading.Event()
        self.injection_error = None
        self.injection_complete = False
        self.anchor = None
        super().__init__()
        self.env['TZ'] = 'UTC'

    def set_mode(self, mode, name, offset=None):
        width, height, refresh = mode
        requested_wall, requested_mono = time.time(), time.monotonic()
        if offset is not None and not 0 <= requested_wall - self.anchor - offset <= TIMING_TOLERANCE:
            raise DiagnosticFailure('missed_injection_timing', 'Target deadline missed before mode request; no catch-up injection')
        self.record('output-mode-requested', mode=list(mode), stage=name, scheduled_elapsed=offset,
                    requested_wall=requested_wall, requested_monotonic=requested_mono,
                    elapsed=requested_wall - self.anchor if self.anchor is not None else None)
        args = ['wlr-randr', '--output', self.output, '--custom-mode', f'{width}x{height}@{refresh}Hz']
        command = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=5)
        (self.out / (name + '-request.txt')).write_text(command.stdout)
        if command.returncode:
            raise DiagnosticFailure('unsupported_output_mode', f'{args} failed: {command.stdout}')
        output = subprocess.check_output(['wlr-randr'], text=True, timeout=5)
        observed_wall, observed_mono = time.time(), time.monotonic()
        (self.out / (name + '-observed.txt')).write_text(output)
        observed = current_mode(output, self.output)
        self.record('output-mode-observed', mode=list(observed), stage=name, scheduled_elapsed=offset,
                    observed_wall=observed_wall, observed_monotonic=observed_mono,
                    elapsed=observed_wall - self.anchor if self.anchor is not None else None)
        require_mode(observed, mode)
        if offset is not None:
            require_timing(requested_wall - self.anchor, observed_wall - self.anchor, offset)
            self.record('output-injection-step-passed', scheduled_elapsed=offset, stage=name)

    def setup_display(self):
        super().setup_display()
        for index, mode in enumerate((MODES[0], MODES[1], MODES[0])):
            self.set_mode(mode, f'preflight-{index + 1}')
        self.record('output-mode-preflight-passed', start_mode=list(MODES[0]), transient_mode=list(MODES[1]),
                    incident_1080p_refresh_known=False, limitations=LIMITATIONS)

    def launch_started(self):
        self.stop.clear()
        self.injection_error = None
        self.injection_complete = False
        self.anchor = None
        self.worker = threading.Thread(target=self.observe_and_schedule, daemon=True)
        self.worker.start()

    def observe_and_schedule(self):
        try:
            log = self.session / 'kodi.log'
            deadline = time.monotonic() + 30
            while not self.stop.is_set():
                if log.exists():
                    with log.open(errors='replace') as first_log:
                        first = first_log.readline()
                    if timestamp(first) is not None:
                        self.anchor = validate_anchor(first, self.process.pid, self.spawn_started_wall, time.time())
                        break
                if time.monotonic() > deadline:
                    raise DiagnosticFailure('missed_injection_timing', 'First Kodi log timestamp unavailable within 30 s')
                self.stop.wait(.005)
            if self.stop.is_set():
                return
            now_wall, now_mono = time.time(), time.monotonic()
            anchor_mono = now_mono - (now_wall - self.anchor)
            if self.launch == 2 and now_wall - self.anchor >= FIRST_OFFSET:
                raise DiagnosticFailure('missed_injection_timing', 'First log discovered after first target; no catch-up injection')
            self.record('first-kodi-log-anchor', first_log_timestamp=self.anchor, first_log_line=first.rstrip(),
                        current_pid=self.process.pid, spawn_started_wall=self.spawn_started_wall, log_path=str(log),
                        detected_elapsed=now_wall - self.anchor, anchor_monotonic=anchor_mono,
                        scheduled_offsets=[FIRST_OFFSET, RESTORE_OFFSET] if self.launch == 2 else [])
            schedule = [(FIRST_OFFSET, MODES[1], 'launch-2-downsize'), (RESTORE_OFFSET, MODES[0], 'launch-2-restore')] if self.launch == 2 else []
            position = 0
            with (self.session / 'kodi-stdout.log').open('rb') as source, (self.session / 'protocol-receipts.jsonl').open('w', buffering=1) as receipts:
                while not self.stop.is_set():
                    if abs((time.time() - self.anchor) - (time.monotonic() - anchor_mono)) > .020:
                        raise DiagnosticFailure('missed_injection_timing', 'Wall/monotonic clocks diverged by more than 20 ms')
                    if schedule and time.monotonic() >= anchor_mono + schedule[0][0]:
                        offset, mode, name = schedule.pop(0)
                        self.set_mode(mode, name, offset)
                        if not schedule:
                            self.injection_complete = True
                    source.seek(position)
                    chunk = source.read()
                    complete = chunk[:chunk.rfind(b'\n') + 1]
                    position += len(complete)
                    for line in complete.decode('utf-8', errors='replace').splitlines():
                        match = PROTOCOL.search(line)
                        if match:
                            receipts.write(json.dumps(dict(observed_wall=time.time(), observed_monotonic=time.monotonic(),
                                elapsed=time.time() - self.anchor, protocol_ms=float(match[1]), raw_line=line)) + '\n')
                    self.stop.wait(.005)
        except Exception as error:
            self.injection_error = error
            (self.session / 'injection-error.txt').write_text(traceback.format_exc())

    def state(self):
        if self.injection_error is not None:
            raise self.injection_error
        return super().state()

    def stop_observer(self):
        self.stop.set()
        if self.worker:
            self.worker.join(timeout=7)
            if self.worker.is_alive():
                raise DiagnosticFailure('harness_failure', 'Output scheduler did not stop')
            self.worker = None

    def before_home_capture(self):
        if self.launch == 2:
            # No synthetic input until both precisely scheduled mode observations
            # and real Kodi configure/application evidence have been established.
            deadline = time.monotonic() + 10
            while not self.injection_complete and time.monotonic() < deadline:
                self.state()
                time.sleep(.01)
            if not self.injection_complete:
                raise DiagnosticFailure('missed_injection_timing', 'Scheduled perturbation did not complete')
            # The screenshot must be after restoration and eventual application,
            # even if this runner reaches Home before the scheduled perturbation.
            deadline = time.monotonic() + 60
            while True:
                self.state()
                try:
                    configure_evidence((self.session / 'kodi-stdout.log').read_text(errors='replace'))
                    break
                except DiagnosticFailure:
                    if time.monotonic() >= deadline:
                        raise
                time.sleep(.05)
            return self.wait('fresh restored Home at capture',
                             lambda state: home_state(state, self.skin, self.process.pid, self.expected_size),
                             after=self.state().get('sequence', 0), category='product_reproduction_candidate')

    def validate_home_before_input(self):
        self.stop_observer()
        self.state()
        if self.anchor is None:
            raise DiagnosticFailure('harness_failure', 'Missing first log anchor')
        log = (self.session / 'kodi.log').read_text(errors='replace')
        phases = milestones(log, self.anchor)
        (self.session / 'lifecycle-milestones.json').write_text(json.dumps(phases, indent=2) + '\n')
        self.record('lifecycle-milestones', milestones=phases, synthetic_keys_sent=0)
        output = self.command(['wlr-randr'], f'launch-{self.launch}-final-output.txt')
        require_mode(current_mode(output, self.output), MODES[0])
        if self.launch == 2:
            evidence = configure_evidence((self.session / 'kodi-stdout.log').read_text(errors='replace'))
            evidence['kodi_size_application'] = size_application_evidence(log, self.anchor)
            (self.session / 'churn-configure-evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
            self.record('output-churn-before-input-passed', final_serial=evidence['final_configure']['serial'],
                        sizes=[[c['width'], c['height']] for c in evidence['ordered_size_configures']], synthetic_keys_sent=0)

    def cleanup(self):
        try:
            self.stop_observer()
        finally:
            super().cleanup()


def main():
    rc = lifecycle_main(ChurnDriver)
    path = Path(os.environ['APERTURE_WAYLAND_OUT']) / 'result.json'
    result = json.loads(path.read_text())
    result['experiment'] = 'output-size-churn'
    result['limitations'] = LIMITATIONS
    result['injection_launch'] = 2
    result['scheduled_offsets_seconds'] = [FIRST_OFFSET, RESTORE_OFFSET]
    result['timing_tolerance_seconds'] = TIMING_TOLERANCE
    # Preserve evidence on failure too. A missing final apply/ack may be the
    # reproduction; lack of an actual ordered perturbation must not be called one.
    for event in result.get('checks', []):
        if event['event'] != 'first-kodi-log-anchor':
            continue
        session = path.parent / ('launch-' + str(event['launch']))
        if (session / 'kodi.log').exists():
            log = (session / 'kodi.log').read_text(errors='replace')
            phases = milestones(log, event['first_log_timestamp'])
            application = size_application_evidence(log, event['first_log_timestamp'])
            (session / 'size-application-evidence.json').write_text(json.dumps(application, indent=2) + '\n')
            if event['launch'] == 2:
                result['kodi_size_application'] = application
                result['launch_2_milestones'] = phases
            (session / 'lifecycle-milestones.json').write_text(json.dumps(phases, indent=2) + '\n')
    launch2 = path.parent / 'launch-2'
    validated_steps = {c['scheduled_elapsed'] for c in result.get('checks', [])
                       if c['event'] == 'output-injection-step-passed'}
    qualified = False
    if (launch2 / 'kodi-stdout.log').exists():
        try:
            trace = configure_evidence((launch2 / 'kodi-stdout.log').read_text(errors='replace'))
            qualified = True
            trace['kodi_size_application'] = result.get('kodi_size_application', {})
            (launch2 / 'churn-configure-evidence.json').write_text(json.dumps(trace, indent=2) + '\n')
        except DiagnosticFailure as error:
            result['configure_validation'] = dict(status=error.category, reason=str(error))
            qualified = error.category == 'product_reproduction_candidate'
    qualified = qualified and validated_steps == {FIRST_OFFSET, RESTORE_OFFSET}
    result['perturbation_qualified'] = qualified
    if result['status'] == 'product_reproduction_candidate' and result.get('launch') == 2 and not qualified:
        result['unverified_candidate_status'] = result['status']
        result['status'] = 'inconclusive_perturbation_failure'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print('APERTURE_OUTPUT_CHURN_RESULT ' + json.dumps(result), flush=True)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""One explicitly event-aligned companion to the retained first-log experiments."""
import json
import os
from pathlib import Path
import re
import time
import traceback

from labwc_output_churn import (ChurnDriver, MODES, PROTOCOL, TIMING_TOLERANCE,
    LIMITATIONS, timestamp, validate_anchor, milestones, current_mode,
    require_mode, configure_evidence, size_application_evidence)
from labwc_relaunch_driver import Driver, DiagnosticFailure, main as lifecycle_main

HOME_OFFSETS = (2.265, 3.002)
PHASE_LIMITATIONS = [item for item in LIMITATIONS if not item.startswith('Offsets match')] + [
    'Event-aligned companion: changes are +2.265/+3.002 s from fresh current-PID Home.xml load, not the original first-log offsets',
    'These differences match incident Home +0.638 s and changes +2.903/+3.640 s, but do not reproduce identical first-log timing',
]


def home_anchor(log, pid, first_log, observed):
    """The first current-process Home file-load entry, never a retained session."""
    for line in log.splitlines():
        if 'Loading skin file: Home.xml,' not in line:
            continue
        thread = re.search(r'\bT:(\d+)\b', line)
        stamp = timestamp(line)
        if not thread or int(thread[1]) != pid or stamp is None or not first_log <= stamp <= observed:
            raise DiagnosticFailure('missed_injection_timing', 'Home load is not fresh current-PID evidence')
        return stamp, line
    return None


def require_applied_roundtrip(application):
    if not (application['intermediate_1080p_processed'] and application['intermediate_1080p_applied']
            and set(application['size_change_roundtrips']) == {'configured', 'surface', 'buffer'}
            and all(application['size_change_roundtrips'].values())):
        raise DiagnosticFailure('inconclusive_perturbation_failure',
            'Phase-aligned run did not establish applied 4K/1080p/4K configured, surface and buffer sizes')


class HomePhaseDriver(ChurnDriver):
    def setup_display(self):
        Driver.setup_display(self)
        for index, mode in enumerate((MODES[0], MODES[1], MODES[0])):
            self.set_mode(mode, f'preflight-{index + 1}')
        self.record('output-mode-preflight-passed', start_mode=list(MODES[0]), transient_mode=list(MODES[1]),
                    incident_1080p_refresh_known=False, limitations=PHASE_LIMITATIONS)

    def launch_started(self):
        self.home_anchor_wall = None
        self.first_log_offsets = None
        self.phase_steps = []
        super().launch_started()

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
            first_mono = now_mono - (now_wall - self.anchor)
            self.record('first-kodi-log-anchor', first_log_timestamp=self.anchor, first_log_line=first.rstrip(),
                        current_pid=self.process.pid, spawn_started_wall=self.spawn_started_wall, log_path=str(log),
                        detected_elapsed=now_wall - self.anchor, anchor_monotonic=first_mono,
                        schedule_reference='fresh Home.xml file-load timestamp')
            schedule, position = None, 0
            with (self.session / 'kodi-stdout.log').open('rb') as source, (self.session / 'protocol-receipts.jsonl').open('w', buffering=1) as receipts:
                while not self.stop.is_set():
                    if abs((time.time() - self.anchor) - (time.monotonic() - first_mono)) > .020:
                        raise DiagnosticFailure('missed_injection_timing', 'Wall/monotonic clocks diverged by more than 20 ms')
                    if self.home_anchor_wall is None:
                        found = home_anchor(log.read_text(errors='replace'), self.process.pid, self.anchor, time.time())
                        if found:
                            self.home_anchor_wall, line = found
                            now_wall, now_mono = time.time(), time.monotonic()
                            home_mono = first_mono + self.home_anchor_wall - self.anchor
                            self.first_log_offsets = [self.home_anchor_wall - self.anchor + offset for offset in HOME_OFFSETS]
                            if self.launch == 2 and now_wall - self.home_anchor_wall >= HOME_OFFSETS[0]:
                                raise DiagnosticFailure('missed_injection_timing', 'Home discovered after first target; no catch-up injection')
                            self.record('home-phase-anchor', current_pid=self.process.pid, home_load_timestamp=self.home_anchor_wall,
                                home_load_line=line, first_log_timestamp=self.anchor,
                                first_log_relative_home=self.home_anchor_wall - self.anchor,
                                detected_after_home=now_wall - self.home_anchor_wall, anchor_monotonic=home_mono,
                                scheduled_home_offsets=list(HOME_OFFSETS) if self.launch == 2 else [],
                                scheduled_first_log_offsets=self.first_log_offsets if self.launch == 2 else [])
                            schedule = list(zip(HOME_OFFSETS, self.first_log_offsets, (MODES[1], MODES[0]),
                                ('launch-2-phase-downsize', 'launch-2-phase-restore'))) if self.launch == 2 else []
                    if schedule and time.monotonic() >= first_mono + schedule[0][1]:
                        phase_offset, first_offset, mode, name = schedule.pop(0)
                        # Reuse the unchanged actual request/observation timing
                        # checks, expressed in the original first-log clock.
                        self.set_mode(mode, name, first_offset)
                        evidence = dict(scheduled_home_elapsed=phase_offset, scheduled_first_log_elapsed=first_offset,
                                        home_anchor=self.home_anchor_wall, first_log_anchor=self.anchor, stage=name)
                        for event in self.checks:
                            if event.get('stage') != name:
                                continue
                            if event['event'] == 'output-mode-requested':
                                evidence['actual_home_request_elapsed'] = event['requested_wall'] - self.home_anchor_wall
                                evidence['actual_first_log_request_elapsed'] = event['elapsed']
                            elif event['event'] == 'output-mode-observed':
                                evidence['actual_home_observation_elapsed'] = event['observed_wall'] - self.home_anchor_wall
                                evidence['actual_first_log_observation_elapsed'] = event['elapsed']
                        self.phase_steps.append(evidence)
                        self.record('home-phase-injection-step-passed', **evidence)
                        if not schedule:
                            self.injection_complete = True
                    source.seek(position)
                    chunk = source.read()
                    complete = chunk[:chunk.rfind(b'\n') + 1]
                    position += len(complete)
                    for line in complete.decode('utf-8', errors='replace').splitlines():
                        match = PROTOCOL.search(line)
                        if match:
                            now = time.time()
                            receipts.write(json.dumps(dict(observed_wall=now, observed_monotonic=time.monotonic(),
                                elapsed=now - self.anchor, home_elapsed=now - self.home_anchor_wall if self.home_anchor_wall else None,
                                protocol_ms=float(match[1]), raw_line=line)) + '\n')
                    self.stop.wait(.005)
        except Exception as error:
            self.injection_error = error
            (self.session / 'injection-error.txt').write_text(traceback.format_exc())

    def validate_home_before_input(self):
        self.stop_observer()
        self.state()
        if self.anchor is None or self.home_anchor_wall is None:
            raise DiagnosticFailure('harness_failure', 'Missing fresh first-log or Home phase anchor')
        log = (self.session / 'kodi.log').read_text(errors='replace')
        phases = milestones(log, self.anchor)
        phases.update(schedule_reference='Home.xml load', scheduled_home_offsets=list(HOME_OFFSETS) if self.launch == 2 else [],
                      scheduled_first_log_offsets=self.first_log_offsets if self.launch == 2 else [],
                      home_loaded_before_first_change=True if self.launch == 2 else None)
        (self.session / 'lifecycle-milestones.json').write_text(json.dumps(phases, indent=2) + '\n')
        self.record('lifecycle-milestones', milestones=phases, synthetic_keys_sent=0)
        output = self.command(['wlr-randr'], f'launch-{self.launch}-final-output.txt')
        require_mode(current_mode(output, self.output), MODES[0])
        if self.launch == 2:
            evidence = configure_evidence((self.session / 'kodi-stdout.log').read_text(errors='replace'))
            application = size_application_evidence(log, self.anchor)
            evidence['kodi_size_application'] = application
            (self.session / 'churn-configure-evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
            require_applied_roundtrip(application)
            if len(self.phase_steps) != 2:
                raise DiagnosticFailure('missed_injection_timing', 'Missing two verified Home-phase changes')
            self.record('home-phase-sequence-before-input-passed', final_serial=evidence['final_configure']['serial'],
                        sizes=[[c['width'], c['height']] for c in evidence['ordered_size_configures']],
                        intermediate_1080p_applied=True, size_change_roundtrips=application['size_change_roundtrips'],
                        scheduled_home_offsets=list(HOME_OFFSETS), scheduled_first_log_offsets=self.first_log_offsets,
                        synthetic_keys_sent=0)


def main():
    rc = lifecycle_main(HomePhaseDriver)
    path = Path(os.environ['APERTURE_WAYLAND_OUT']) / 'result.json'
    result = json.loads(path.read_text())
    result.update(experiment='home-phase-aligned-output-size-churn', limitations=PHASE_LIMITATIONS,
                  injection_launch=2, schedule_reference='fresh current-PID Home.xml file-load timestamp',
                  scheduled_home_offsets_seconds=list(HOME_OFFSETS), timing_tolerance_seconds=TIMING_TOLERANCE)
    anchors = {event['launch']: event for event in result.get('checks', []) if event['event'] == 'home-phase-anchor'}
    for event in result.get('checks', []):
        if event['event'] != 'first-kodi-log-anchor':
            continue
        session = path.parent / ('launch-' + str(event['launch']))
        if not (session / 'kodi.log').exists():
            continue
        log = (session / 'kodi.log').read_text(errors='replace')
        phases = milestones(log, event['first_log_timestamp'])
        anchor = anchors.get(event['launch'], {})
        phases.update(schedule_reference='Home.xml load',
            scheduled_home_offsets=anchor.get('scheduled_home_offsets'),
            scheduled_first_log_offsets=anchor.get('scheduled_first_log_offsets'),
            home_loaded_before_first_change=bool(anchor) if event['launch'] == 2 else None)
        application = size_application_evidence(log, event['first_log_timestamp'])
        (session / 'lifecycle-milestones.json').write_text(json.dumps(phases, indent=2) + '\n')
        (session / 'size-application-evidence.json').write_text(json.dumps(application, indent=2) + '\n')
        if event['launch'] == 2:
            result.update(launch_2_milestones=phases, kodi_size_application=application)
    qualified = any(event['event'] == 'home-phase-sequence-before-input-passed' for event in result.get('checks', []))
    result['phase_sequence_qualified'] = qualified
    if result['status'] == 'product_reproduction_candidate' and result.get('launch') == 2 and not qualified:
        result['unverified_candidate_status'] = result['status']
        result['status'] = 'inconclusive_perturbation_failure'
    if result['status'] == 'passed' and not qualified:
        result.update(status='harness_failure', reason='Passed lifecycle lacked applied phase-sequence evidence')
        rc = 1
    path.write_text(json.dumps(result, indent=2) + '\n')
    print('APERTURE_HOME_PHASE_RESULT ' + json.dumps(result), flush=True)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())

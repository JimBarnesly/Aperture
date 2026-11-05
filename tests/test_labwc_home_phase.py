"""Explicit Home-phase alignment without changing retained first-log experiments."""
import hashlib
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import labwc_home_phase_churn as phase
from labwc_relaunch_driver import DiagnosticFailure


class HomePhaseTests(unittest.TestCase):
    def test_offsets_are_incident_home_relative_differences(self):
        self.assertAlmostEqual(phase.HOME_OFFSETS[0], 2.903 - .638)
        self.assertAlmostEqual(phase.HOME_OFFSETS[1], 3.640 - .638)
        self.assertAlmostEqual(phase.HOME_OFFSETS[1] - phase.HOME_OFFSETS[0], .737)

    def test_first_current_pid_home_load_is_the_anchor(self):
        first = phase.timestamp('2026-11-05 14:45:08.618 T:99 info: first')
        line = '2026-11-05 14:45:14.906 T:99 info: Loading skin file: Home.xml, load type: KEEP_IN_MEMORY'
        result = phase.home_anchor(line + '\n' + line.replace('14.906', '15.906'), 99, first, first + 8)
        self.assertAlmostEqual(result[0] - first, 6.288, places=3)
        self.assertEqual(result[1], line)

    def test_stale_wrong_pid_and_future_home_load_rejected(self):
        line = '2026-11-05 14:45:14.906 T:99 info: Loading skin file: Home.xml, load type: KEEP_IN_MEMORY'
        stamp = phase.timestamp(line)
        for pid, first, now in [(98, stamp - 1, stamp + 1), (99, stamp + 1, stamp + 2), (99, stamp - 1, stamp - .1)]:
            with self.assertRaises(DiagnosticFailure):
                phase.home_anchor(line, pid, first, now)

    def test_window_init_without_home_file_load_is_not_an_anchor(self):
        self.assertIsNone(phase.home_anchor('2026-11-05 14:45:14.906 T:99 debug: Window Init (Home.xml)', 99, 0, 9999999999))

    def test_every_application_and_size_roundtrip_required(self):
        value = dict(intermediate_1080p_processed=True, intermediate_1080p_applied=True,
                     size_change_roundtrips=dict(configured=True, surface=True, buffer=True))
        phase.require_applied_roundtrip(value)
        for flag in ('intermediate_1080p_processed', 'intermediate_1080p_applied'):
            with self.assertRaises(DiagnosticFailure):
                phase.require_applied_roundtrip(dict(value, **{flag:False}))
        with self.assertRaises(DiagnosticFailure):
            phase.require_applied_roundtrip(dict(value, size_change_roundtrips={}))
        for kind in ('configured', 'surface', 'buffer'):
            with self.assertRaises(DiagnosticFailure):
                phase.require_applied_roundtrip(dict(value, size_change_roundtrips=dict(value['size_change_roundtrips'], **{kind:False})))

    def test_previous_driver_and_timing_are_byte_identical(self):
        root = Path(phase.__file__).parents[1]
        expected = {'tools/labwc_output_churn.py':'d4041a64e927496286b38c531a9645e58ae2707fec18cb2e76e0039c78ff3eed',
                    'tools/labwc_relaunch_driver.py':'f25df0b1da45c6d31283f22d4957eb53777f0c155075de259656738e55d2b0e2',
                    'tools/ci_labwc_relaunch.sh':'64b763422b7c92db360c9fd74e0088a83d2d15f8286e59c25dd602786bc04717'}
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), digest)

    def test_phase_session_changes_only_driver_selection(self):
        root = Path(phase.__file__).parents[1]
        baseline = (root / 'tools/ci_labwc_relaunch.sh').read_text()
        companion = (root / 'tools/ci_labwc_home_phase_session.sh').read_text()
        prefix = baseline[:baseline.index('case "${APERTURE_WAYLAND_EXPERIMENT:-baseline}" in')]
        suffix = baseline[baseline.index('\nSESSION', len(prefix)):]
        self.assertTrue(companion.startswith(prefix))
        self.assertTrue(companion.endswith(suffix))
        self.assertIn('home-phase-churn', companion)
        self.assertIn('labwc_home_phase_churn.py', companion)

    def test_companion_calls_inherited_pre_capture_barrier(self):
        self.assertIs(phase.HomePhaseDriver.before_home_capture, phase.ChurnDriver.before_home_capture)
        self.assertIs(phase.HomePhaseDriver.exit_native, phase.ChurnDriver.exit_native)
        self.assertIs(phase.HomePhaseDriver.set_mode, phase.ChurnDriver.set_mode)


if __name__ == '__main__':
    unittest.main()

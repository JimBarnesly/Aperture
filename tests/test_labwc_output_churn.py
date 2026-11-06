"""Fail closed on unsupported modes, missed timing and incomplete protocol evidence."""
import sys
from pathlib import Path
import tempfile
import unittest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import labwc_output_churn as churn
from labwc_relaunch_driver import DiagnosticFailure, home_state, pixel_evidence

MODE = '''HEADLESS-1 "Headless output 1"
  Enabled: yes
  Modes:
    3840x2160 px, 30.000000 Hz (current)
  Transform: normal
  Scale: 1.000000
'''
TRACE = '''[100.0] -> xdg_wm_base#9.get_xdg_surface(new id xdg_surface#22, wl_surface#11)
[101.0] xdg_toplevel#24.configure(3840, 2160, array[4])
[102.0] xdg_surface#22.configure(19)
[3000.0] xdg_toplevel#24.configure(1920, 1080, array[4])
[3001.0] xdg_surface#22.configure(22)
[3700.0] xdg_toplevel#24.configure(3840, 2160, array[4])
[3701.0] xdg_surface#22.configure(25)
2026-11-05 13:59:37.502 T:8253 debug: ApplyNextState: Applying next state: serial 25 configured size 3840x2160 scale 1 state activated,fullscreen
[6001.0] -> xdg_surface#22.ack_configure(25)
[6002.0] -> wl_surface#11.frame(new id wl_callback#31)
[6003.0] -> wl_surface#11.commit()
[6004.0] wl_callback#31.done(292788)
'''


class OutputChurnTests(unittest.TestCase):
    def test_current_mode_exact_output_and_refresh(self):
        mode = churn.current_mode(MODE, 'HEADLESS-1')
        self.assertEqual(mode, (3840, 2160, 30.0))
        churn.require_mode(mode, churn.MODES[0])
        with self.assertRaises(DiagnosticFailure):
            churn.require_mode(mode, (3840, 2160, 60))

    def test_wrong_disabled_missing_and_scaled_outputs_rejected(self):
        for value in (MODE.replace('HEADLESS-1', 'HEADLESS-2'), MODE.replace('yes', 'no'),
                      MODE.replace('(current)', ''), MODE.replace('1.000000', '2.000000')):
            with self.assertRaises(DiagnosticFailure):
                churn.current_mode(value, 'HEADLESS-1')

    def test_requested_and_observed_timing_required(self):
        churn.require_timing(2.904, 2.920, churn.FIRST_OFFSET)
        for requested, observed in [(2.8, 2.95), (3.01, 3.02), (2.904, 3.01)]:
            with self.assertRaises(DiagnosticFailure) as error:
                churn.require_timing(requested, observed, churn.FIRST_OFFSET)
            self.assertEqual(error.exception.category, 'missed_injection_timing')

    def test_stale_or_wrong_pid_anchor_rejected(self):
        line = '2026-11-05 13:59:31.233 T:99 info: first'
        anchor = churn.timestamp(line)
        self.assertEqual(churn.validate_anchor(line, 99, anchor - .02, anchor + .01), anchor)
        for pid, started in [(98, anchor - .02), (99, anchor + 1)]:
            with self.assertRaises(DiagnosticFailure):
                churn.validate_anchor(line, pid, started, anchor + 2)

    def test_utc_log_anchor_and_milestones(self):
        anchor = churn.timestamp('\ufeff2026-11-05 13:59:31.233 T:1 info: first')
        phases = churn.milestones('2026-11-05 13:59:37.470 T:1 info: Loading skin file: Home.xml, load type: KEEP_IN_MEMORY', anchor)
        self.assertAlmostEqual(phases['home_file_load']['elapsed'], 6.237, places=3)
        self.assertFalse(phases['home_loaded_before_first_change'])
        self.assertEqual(phases['incident_home_file_load_elapsed'], .638)

    def test_intermediate_processing_and_application_are_not_assumed(self):
        line = '2026-11-05 13:59:31.233 T:99 debug: '
        anchor = churn.timestamp(line)
        coalesced = churn.size_application_evidence(line + 'ApplyNextState: Applying next state: serial 25 configured size 3840x2160', anchor)
        self.assertFalse(coalesced['intermediate_1080p_applied'])
        self.assertFalse(coalesced['incident_applied_size_sequence_observed'])
        log = '\n'.join(line + event for event in [
            'ProcessMessages: Configure serial 22: size 1920x1080',
            'ApplyNextState: Applying next state: serial 22 configured size 1920x1080',
            *[f'UpdateSizeVariables: {kind} size changed: 3840x2160 -> 1920x1080' for kind in ('Configured', 'Surface', 'Buffer')],
            *[f'UpdateSizeVariables: {kind} size changed: 1920x1080 -> 3840x2160' for kind in ('Configured', 'Surface', 'Buffer')]])
        applied = churn.size_application_evidence(log, anchor)
        self.assertTrue(applied['intermediate_1080p_processed'])
        self.assertTrue(applied['intermediate_1080p_applied'])
        self.assertTrue(applied['incident_applied_size_sequence_observed'])

    def test_real_sequence_final_apply_ack_and_same_surface_frame(self):
        evidence = churn.configure_evidence(TRACE)
        self.assertEqual(evidence['final_configure']['serial'], 25)
        self.assertEqual(evidence['wl_surface'], 11)
        self.assertEqual(evidence['line_order'], sorted(evidence['line_order']))
        self.assertEqual([c['width'] for c in evidence['ordered_size_configures']], [3840, 1920, 3840])

    def test_missing_or_reordered_size_is_harness_failure(self):
        for value in (TRACE.replace('1920, 1080', '3840, 2160'), TRACE.replace('3840, 2160', '1920, 1080', 1)):
            with self.assertRaises(DiagnosticFailure) as error:
                churn.configure_evidence(value)
            self.assertEqual(error.exception.category, 'harness_configure_validation_failure')

    def test_no_apply_wrong_ack_surface_or_incomplete_frame_cannot_pass(self):
        for old, new in [('Applying next state: serial 25', 'Applying next state: serial 22'),
                         ('ack_configure(25)', 'ack_configure(22)'),
                         ('wl_surface#11.commit()', 'wl_surface#12.commit()'),
                         ('wl_callback#31.done', 'wl_callback#32.done')]:
            with self.assertRaises(DiagnosticFailure) as error:
                churn.configure_evidence(TRACE.replace(old, new))
            self.assertEqual(error.exception.category, 'product_reproduction_candidate')

    def test_baseline_dimensions_are_unchanged_and_4k_is_explicit(self):
        state = dict(pid=99, skin='skin.aperture', window=10000, dialog=9999,
                     home_visible=True, width=3840, height=2160)
        self.assertFalse(home_state(state, 'skin.aperture', 99))
        self.assertTrue(home_state(state, 'skin.aperture', 99, (3840, 2160)))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'frame.png'
            Image.effect_noise((3840, 2160), 80).convert('RGB').save(path)
            self.assertFalse(pixel_evidence(path, 'Movies Music Games')['home_pixels'])
            self.assertTrue(pixel_evidence(path, 'Movies Music Games', (3840, 2160))['home_pixels'])
            Image.new('RGB', (3840, 2160)).save(path)
            self.assertFalse(pixel_evidence(path, 'Movies Music Games', (3840, 2160))['home_pixels'])
            self.assertTrue(pixel_evidence(path, '', (3840, 2160))['black_frame'])

    def test_only_second_launch_is_perturbed_no_baseline_workflow_changes(self):
        source = (Path(churn.__file__)).read_text()
        self.assertIn('if self.launch == 2 else []', source)
        workflow = (Path(churn.__file__).parents[1] / '.github/workflows/labwc-output-churn.yml').read_text()
        self.assertIn('branches: [test/labwc-relaunch]', workflow)
        self.assertIn('APERTURE_WAYLAND_SKIN: aperture', workflow)
        self.assertIn('ubuntu-24.04-arm', workflow)


if __name__ == '__main__':
    unittest.main()

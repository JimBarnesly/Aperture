"""Exercise diagnostic capture with a tiny child, never the installed Kodi."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / 'tools/movies_native_debug.sh'


@unittest.skipUnless(shutil.which('gdb') and shutil.which('cc'), 'gdb/cc required for native capture probe')
class NativeCaptureTests(unittest.TestCase):
    def test_signal_records_faulting_frame_and_nonzero_exit(self):
        self.probe(True)

    def test_normal_exit_is_not_reported_as_crash(self):
        self.probe(False)

    def probe(self, crash):
        self.assertTrue(LAUNCHER.exists(), 'Native SIGSEGV currently loses all faulting frames')
        with tempfile.TemporaryDirectory(prefix='aperture-movies-qa.') as tmp:
            runtime = Path(tmp)
            out = runtime / 'out'
            out.mkdir()
            (runtime / 'home').mkdir()
            (runtime / 'data').mkdir()
            source = runtime / 'probe.c'
            source.write_text('void fault_here(void) { *(volatile int *)0 = 1; }\n'
                              'int main(void) { ' + ('fault_here(); ' if crash else '') + 'return 0; }\n')
            binary = runtime / 'probe'
            subprocess.run(['cc', '-g', '-O0', str(source), '-o', str(binary)], check=True,
                           capture_output=True, timeout=20)
            env = dict(os.environ, APERTURE_MOVIES_RUNTIME=tmp, APERTURE_MOVIES_OUT=str(out),
                       HOME=str(runtime / 'home'), KODI_DATA=str(runtime / 'data'))
            run = subprocess.run(['timeout', '--kill-after=2s', '15s', 'bash', str(LAUNCHER), str(binary)],
                                 env=env, capture_output=True, text=True, timeout=20)
            trace = (out / 'native-backtrace.txt').read_text()
            self.assertNotIn('Operation not permitted', trace, 'ptrace must actually exercise the child')
            self.assertNotIn('SIGTERM', trace, 'Capture must complete before the outer bound')
            if crash:
                self.assertNotEqual(run.returncode, 0)
                self.assertIn('SIGSEGV', trace)
                self.assertIn('fault_here', trace)
                self.assertIn('#0', trace)
            else:
                self.assertEqual(run.returncode, 0, trace)
                self.assertNotIn('SIGSEGV', trace)
            self.assertTrue((out / 'native-environment.txt').is_file())

    def test_launcher_refuses_non_disposable_profile(self):
        self.assertTrue(LAUNCHER.exists())
        env = dict(os.environ, APERTURE_MOVIES_RUNTIME='/not-a-disposable-runtime')
        run = subprocess.run(['bash', str(LAUNCHER), '/bin/true'], env=env,
                             capture_output=True, text=True, timeout=5)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('disposable', run.stderr)

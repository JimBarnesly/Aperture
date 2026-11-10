"""Exercise smoke bootstrap without launching Kodi or probing packages."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SmokeScratchTests(unittest.TestCase):
    def test_runtime_uses_tmpdir_even_with_spaces(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            scratch = root / 'scratch with spaces'
            scratch.mkdir()
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            record = root / 'mktemp.json'
            real_mktemp = shutil.which('mktemp')
            self.assertIsNotNone(real_mktemp)
            # Refuse an out-of-scratch allocation even on the unfixed script.
            # Then let real mktemp prove quoting and actual directory creation.
            wrapper = bin_dir / 'mktemp'
            wrapper.write_text(f'''#!{sys.executable}
import json, os, sys
from pathlib import Path
Path(os.environ['MKTEMP_RECORD']).write_text(json.dumps(sys.argv[1:]))
if Path(sys.argv[-1]).parent != Path(os.environ['TMPDIR']):
    sys.exit(97)
os.execv({real_mktemp!r}, ['mktemp'] + sys.argv[1:])
''')
            wrapper.chmod(0o700)
            # Stop before native prerequisites; no dpkg, Kodi, X or audio access.
            stop = bin_dir / 'dpkg'
            stop.write_text('#!/bin/sh\nprintf "/synthetic/kodi.bin\\n"\nexit 99\n')
            stop.chmod(0o700)
            env = dict(os.environ, TMPDIR=str(scratch), MKTEMP_RECORD=str(record),
                       APERTURE_MOVIES_OUT=str(root / 'out'), APERTURE_MOVIES_SCENARIO='single',
                       PATH=str(bin_dir) + os.pathsep + os.environ['PATH'])
            result = subprocess.run(['bash', str(ROOT / 'tools/movies_smoke.sh')],
                                    env=env, capture_output=True, text=True, timeout=10)
            args = json.loads(record.read_text())
            self.assertEqual(Path(args[-1]).parent, scratch, 'Smoke runtime ignored TMPDIR')
            self.assertEqual(result.returncode, 99, result.stdout + result.stderr)
            runtimes = list(scratch.glob('aperture-movies-qa.*'))
            self.assertEqual(len(runtimes), 1)
            self.assertTrue((runtimes[0] / 'home').is_dir())

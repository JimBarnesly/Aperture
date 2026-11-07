#!/usr/bin/env python3
"""Verify pinned source hashes against the archived signed Raspberry Pi index."""
import gzip
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
root = Path(__file__).resolve().parent
p = root / 'provenance'
keyring = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory() as temp:
    verified = Path(temp) / 'Release'
    subprocess.run(['sqv', '--keyring', str(keyring), '--cleartext',
                    '--output', str(verified), str(p / 'InRelease')], check=True)
    release = verified.read_text()
section = release.split('\nSHA256:\n', 1)[1].split('\nSHA512:', 1)[0]
entries = [line.split() for line in section.splitlines() if line.strip()]
entry = next(row for row in entries if len(row) == 3 and row[2] == 'main/source/Sources.gz')
data = (p / 'Sources.gz').read_bytes()
assert hashlib.sha256(data).hexdigest() == entry[0]
assert len(data) == int(entry[1])
stanzas = gzip.decompress(data).decode().split('\n\n')
matching = [s for s in stanzas if s.startswith('Package: kodi\n') and '\nVersion: 3:21.3+dfsg-1+rpt3\n' in s]
assert len(matching) == 1
lines = matching[0].split('Checksums-Sha256:', 1)[1].splitlines()
expected = {}
for line in lines:
    if not line.strip():
        continue
    if not line.startswith(' '):
        break
    digest, size, name = line.split()
    expected[name] = digest
actual = dict((name, digest) for digest, name in
              (line.split() for line in (root / 'source.sha256').read_text().splitlines()))
assert expected == actual, 'Pinned source set differs from authenticated Sources stanza'
print('PASS: archive signature -> Sources.gz hash/size -> exact Kodi source hashes')

#!/usr/bin/env python3
"""Record the checked-out source, never GitHub's pull-request merge SHA."""
import json
import os
from pathlib import Path
import subprocess
import sys


def record_source(root, out, expected=''):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()

    commit = git('rev-parse', 'HEAD')
    tree = git('rev-parse', 'HEAD^{tree}')
    dirty = bool(git('status', '--porcelain', '--untracked-files=no'))
    evidence = dict(commit=commit, tree=tree, expected_commit=expected or None,
                    tracked_worktree_clean=not dirty,
                    github_event_sha=os.environ.get('GITHUB_SHA'))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'commit.txt').write_text(commit + '\n')
    (out / 'tree.txt').write_text(tree + '\n')
    (out / 'source-provenance.json').write_text(json.dumps(evidence, indent=2) + '\n')
    if expected and expected != commit:
        raise ValueError(f'Checked-out HEAD {commit} differs from expected {expected}')
    if dirty:
        raise ValueError('Tracked source differs from checked-out HEAD')
    return evidence


def main():
    out = Path(sys.argv[2])
    try:
        evidence = record_source(Path(sys.argv[1]), out,
                                 os.environ.get('APERTURE_EXPECTED_COMMIT', ''))
    except Exception as error:
        out.mkdir(parents=True, exist_ok=True)
        (out / 'result.json').write_text(json.dumps(dict(status='harness_failure',
            stage='source_provenance', reason=str(error)), indent=2) + '\n')
        raise SystemExit(str(error))
    print(json.dumps(dict(event='source-provenance-verified', **evidence)), flush=True)


if __name__ == '__main__':
    main()

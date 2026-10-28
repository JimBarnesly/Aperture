#!/usr/bin/env python3
"""Build a complete Apeture skin from pinned official Kodi Omega Estuary.

This is a build-time vendor operation, never an installed Kodi service.
Only the Estuary sparse tree is materialized; no full XBMC history is cloned.
The source override directory is deliberately NOT an installable skin itself.
"""
from __future__ import annotations
import argparse
import json
import io
import tarfile
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from vendor_estuary_assets import generate

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = 'https://github.com/xbmc/xbmc.git'
REVISION = 'f8815ee40f49a700c047982d752be4b2a61420e2'
SKIN_TREE = 'efc84d521908a2999e65718fa443a967941a38c6'
SUBTREE = 'addons/skin.estuary'
DEFAULT_CACHE = ROOT/'build'/'upstream'/'xbmc-omega'


def git(directory: Path, *args: str, capture=False):
    result = subprocess.run(['git', '-C', str(directory), *args], check=True,
                            text=True, stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else None


def checkout(cache: Path):
    cache.mkdir(parents=True, exist_ok=True)
    if not (cache/'.git').is_dir():
        if any(cache.iterdir()):
            raise RuntimeError(f'Refusing to initialize a nonempty cache: {cache}')
        git(cache, 'init', '--quiet')
        git(cache, 'remote', 'add', 'origin', UPSTREAM)
        git(cache, 'config', 'remote.origin.promisor', 'true')
        git(cache, 'config', 'remote.origin.partialclonefilter', 'blob:none')
        git(cache, 'sparse-checkout', 'init', '--cone')
        git(cache, 'sparse-checkout', 'set', SUBTREE, 'LICENSES')
    if git(cache, 'remote', 'get-url', 'origin', capture=True) != UPSTREAM:
        raise RuntimeError(f'Unexpected upstream remote in {cache}')
    have_revision = subprocess.run(['git','-C',str(cache),'cat-file','-e',REVISION+'^{commit}'],
                                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode == 0
    if not have_revision:
        git(cache, 'fetch', '--filter=blob:none', '--depth=1', 'origin', REVISION)
    git(cache, 'checkout', '--detach', REVISION)
    if git(cache, 'rev-parse', 'HEAD', capture=True) != REVISION:
        raise RuntimeError('Upstream revision verification failed')
    if git(cache, 'rev-parse', f'{REVISION}:{SUBTREE}', capture=True) != SKIN_TREE:
        raise RuntimeError('Upstream skin tree verification failed')
    # Guard against a caller supplying a dirty cache: every byte copied must be pinned.
    dirty = git(cache,'status','--porcelain','--untracked-files=all','--',SUBTREE,'LICENSES',capture=True)
    if dirty:
        raise RuntimeError(f'Upstream cache has changes; use a clean cache: {dirty}')
    if not (cache/SUBTREE/'xml/DialogConfirm.xml').is_file():
        raise RuntimeError('Sparse upstream checkout is incomplete')
    return cache/SUBTREE


def materialize(output: Path, cache: Path):
    output = output.resolve()
    overrides = ROOT/'addons'/'skin.apeture'
    # Build only into a new directory or one previously marked by this builder.
    # Never overwrite authored source, the repository, or an arbitrary user folder.
    if output == ROOT or output == overrides or overrides in output.parents or output in overrides.parents:
        raise ValueError('Output must not overlap the source tree')
    marker = output/'APETURE_BUILD.json'
    if output.exists() and any(output.iterdir()) and not marker.is_file():
        raise ValueError(f'Refusing to replace unmarked nonempty output: {output}')
    source = checkout(cache.resolve())
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='apeture-skin-',dir=output.parent) as tmp:
        staged = Path(tmp)/'skin.apeture'
        # Export Git objects, not worktree contents: ignored/untracked files can
        # never leak into a distributable, even in an externally supplied cache.
        archive = subprocess.check_output(['git','-C',str(cache),'archive',f'{REVISION}:{SUBTREE}'])
        staged.mkdir()
        baseline_file_count = 0
        with tarfile.open(fileobj=io.BytesIO(archive),mode='r:') as bundle:
            for member in bundle.getmembers():
                relative = Path(member.name)
                if relative.is_absolute() or '..' in relative.parts or not (member.isfile() or member.isdir()):
                    raise RuntimeError(f'Unsupported upstream archive entry: {member.name}')
                destination = staged/relative
                if member.isdir(): destination.mkdir(parents=True,exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    with bundle.extractfile(member) as src, destination.open('wb') as dst:
                        shutil.copyfileobj(src,dst)
                    baseline_file_count += 1
        # Upstream marketing images are not Apeture screenshots or assets.
        for name in ('icon.png','fanart.jpg'):
            (staged/'resources'/name).unlink(missing_ok=True)
        for picture in (staged/'resources').glob('screenshot*'):
            picture.unlink()
        shutil.copytree(overrides,staged,dirs_exist_ok=True)
        generate(staged)
        shutil.copy2(ROOT/'docs'/'UPSTREAM.md',staged/'UPSTREAM.md')
        shutil.copy2(ROOT/'docs'/'DESIGN.md',staged/'DESIGN.md')
        # Preserve upstream's original LICENSE.txt and every font license verbatim.
        licenses=staged/'licenses';licenses.mkdir(exist_ok=True)
        for license_name in ('GPL-2.0-only','GPL-2.0-or-later'):
            license_bytes = subprocess.check_output(['git','-C',str(cache),'show',f'{REVISION}:LICENSES/{license_name}'])
            if len(license_bytes) < 10000: raise RuntimeError('Incomplete upstream GPL license text')
            (licenses/f'{license_name}.txt').write_bytes(license_bytes)
        # Remove source-only metadata that could be confused with a new release.
        version = ET.parse(staged/'addon.xml').getroot().attrib['version']
        (staged/'changelog.txt').write_text(f'Apeture {version}: original home on pinned Kodi Omega Estuary. See UPSTREAM.md and DESIGN.md.\n',encoding='utf-8')
        manifest={'upstream':UPSTREAM,'revision':REVISION,'skin_tree':SKIN_TREE,
                  'addon':'skin.apeture','version':version,'baseline_file_count':baseline_file_count,
                  'overrides':sorted(str(p.relative_to(overrides)) for p in overrides.rglob('*') if p.is_file())}
        (staged/'APETURE_BUILD.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        for xml in staged.rglob('*.xml'):
            ET.parse(xml)
        if output.exists():shutil.rmtree(output)
        shutil.move(str(staged),str(output))
    print(f'Materialized {output} from official Kodi commit {REVISION}')
    return output


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cache',type=Path,default=DEFAULT_CACHE,help='Clean sparse Git cache')
    args=parser.parse_args()
    materialize(args.output,args.cache)

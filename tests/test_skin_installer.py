import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]

class SkinInstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.profile=self.root/'profile with spaces';self.skin=self.root/'estuary'
        (self.skin/'xml').mkdir(parents=True);(self.skin/'fonts').mkdir()
        (self.skin/'addon.xml').write_text('<?xml version="1.0"?>\n<addon id="skin.estuary" version="4.0.0" name="Estuary"><requires><import addon="xbmc.gui" version="5.17.0"/></requires></addon>\n')
        (self.skin/'xml/Font.xml').write_text('<fonts>\n<filename>regular.ttf</filename>\n<filename>arial.ttf</filename>\n</fonts>')
        (self.skin/'fonts/regular.ttf').write_bytes(b'original font')
        for file in ('Home.xml','Settings.xml','SettingsCategory.xml','DialogConfirm.xml'):
            (self.skin/'xml'/file).write_text('<window/>')
        self.bin=self.root/'bin';self.bin.mkdir()
        self.fake('pgrep','exit 1')
        self.env=dict(os.environ,PATH=str(self.bin)+':'+os.environ['PATH'],APERTURE_KODI_HOME=str(self.profile),APERTURE_SKIN_SOURCE=str(self.skin),APERTURE_SOURCE_DIR=str(ROOT))
        self.target=self.profile/'addons/skin.aperture'

    def fake(self,name,script):
        p=self.bin/name;p.write_text('#!/bin/sh\n'+script+'\n');p.chmod(0o755)

    def run_install(self,*args):
        return subprocess.run(['sh',str(ROOT/'install.sh'),*args],env=self.env,text=True,capture_output=True)

    def existing(self):
        self.target.mkdir(parents=True)
        (self.target/'addon.xml').write_text('<addon id="skin.aperture" version="4.0.0"/>')
        (self.target/'keep.txt').write_text('old skin')

    def test_installs_versioned_complete_skin(self):
        r=self.run_install();self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(ET.parse(self.target/'addon.xml').getroot().get('version'),'4.0.1~rc1')
        self.assertEqual((self.target/'xml/Home.xml').read_bytes(),(ROOT/'skin/xml/Home.xml').read_bytes())
        self.assertFalse((self.profile/'.aperture-skin-install.lock').exists())

    def test_baseline_retains_official_home(self):
        r=self.run_install('--baseline');self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual((self.target/'xml/Home.xml').read_text(),'<window/>')

    def test_reinstall_preserves_every_previous_copy_outside_addons(self):
        self.existing();old=self.target.with_name('skin.aperture.previous');shutil.copytree(self.target,old)
        r=self.run_install();self.assertEqual(r.returncode,0,r.stderr)
        self.assertFalse(old.exists())
        self.assertEqual(len(list((self.profile/'aperture-backups').glob('*/skin.aperture/keep.txt'))),2)
        self.assertEqual([p.name for p in (self.profile/'addons').iterdir()],['skin.aperture'])

    def test_running_kodi_refused(self):
        self.fake('pgrep','exit 0');r=self.run_install()
        self.assertNotEqual(r.returncode,0);self.assertFalse(self.profile.exists())

    def test_missing_font_never_replaces(self):
        self.existing();(self.skin/'fonts/regular.ttf').unlink();r=self.run_install()
        self.assertNotEqual(r.returncode,0);self.assertTrue((self.target/'keep.txt').exists())

    def test_bad_home_hash_never_replaces(self):
        self.existing();bad=self.root/'badsource';(bad/'skin/xml').mkdir(parents=True);(bad/'skin/xml/Home.xml').write_text('<window/>')
        self.env['APERTURE_SOURCE_DIR']=str(bad);r=self.run_install()
        self.assertNotEqual(r.returncode,0);self.assertTrue((self.target/'keep.txt').exists())

    def test_resolves_relative_font_links(self):
        p=self.skin/'fonts/regular.ttf';p.unlink();(self.root/'font.ttf').write_bytes(b'font bytes');p.symlink_to('../../font.ttf')
        r=self.run_install();self.assertEqual(r.returncode,0,r.stderr)
        self.assertFalse((self.target/'fonts/regular.ttf').is_symlink())
        self.assertEqual((self.target/'fonts/regular.ttf').read_bytes(),b'font bytes')

    def test_failed_swap_restores_previous_skin(self):
        self.existing()
        self.fake('mv', 'case "$1" in */.aperture-skin.*/skin.aperture) exit 1;; esac\nexec /usr/bin/mv "$@"')
        r=self.run_install();self.assertNotEqual(r.returncode,0)
        self.assertTrue((self.target/'keep.txt').exists())

    def test_lock_is_not_stolen(self):
        lock=self.profile/'.aperture-skin-install.lock';lock.mkdir(parents=True)
        r=self.run_install();self.assertNotEqual(r.returncode,0);self.assertTrue(lock.exists())

    def test_symlink_target_is_not_replaced(self):
        self.target.parent.mkdir(parents=True);real=self.root/'precious';real.mkdir();self.target.symlink_to(real,target_is_directory=True)
        r=self.run_install();self.assertNotEqual(r.returncode,0);self.assertTrue(self.target.is_symlink());self.assertTrue(real.exists())

if __name__=='__main__':unittest.main()

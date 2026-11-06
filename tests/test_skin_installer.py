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
        (self.skin/'xml/Includes.xml').write_text('<includes><include name="DialogBackgroundCommons"><control type="group"/></include></includes>')
        for name in ('Includes_Buttons.xml','Includes_DialogSelect.xml'):
            (self.skin/'xml'/name).write_text('<includes/>')
        for file in ('Home.xml','Settings.xml','SettingsCategory.xml','DialogConfirm.xml'):
            (self.skin/'xml'/file).write_text('<window/>')
        self.bin=self.root/'bin';self.bin.mkdir()
        self.fake('pgrep','exit 1')
        self.env=dict(os.environ,PATH=str(self.bin)+':'+os.environ['PATH'],APERTURE_KODI_HOME=str(self.profile),APERTURE_SKIN_SOURCE=str(self.skin),APERTURE_SOURCE_DIR=str(ROOT))
        self.target=self.profile/'addons/skin.aperture'
        self.fonts=self.root/'system fonts';self.fonts.mkdir()
        self.env['APERTURE_FONT_ROOT']=str(self.fonts)

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

    def test_integrated_skin_and_format_update_preserves_games_and_profile(self):
        self.existing()
        shutil.copytree(ROOT/'games-kodi', self.profile/'addons/plugin.games.aperture',
                        ignore=shutil.ignore_patterns('__pycache__'))
        protected = {
            'userdata/addon_data/plugin.games.aperture/settings.xml': b'configured ROM root',
            'userdata/addon_data/plugin.games.aperture/library-v1/snapshot.json': b'cached seven systems',
            'userdata/addon_data/plugin.games.aperture/library-v1/snapshot.attempt': b'existing attempt',
            'userdata/addon_data/plugin.audio.aperture.format/settings.xml': b'preserved Format endpoint',
            'userdata/Savestates/existing.sav': b'game save',
            'userdata/addon_data/game.libretro.nestopia/save.sav': b'core save data',
            'addons/game.libretro.nestopia/core.so': b'installed core',
            'addons/plugin.video.aperture.movies/addon.py': b'installed Movies client',
            'userdata/guisettings.xml': b'current skin and preferences',
            'userdata/sources.xml': b'current media sources',
        }
        for relative, content in protected.items():
            path=self.profile/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
        game_root=self.profile/'addons/plugin.games.aperture'
        game_before={str(p.relative_to(game_root)):p.read_bytes() for p in game_root.rglob('*') if p.is_file()}
        skin_result=self.run_install()
        self.assertEqual(skin_result.returncode,0,skin_result.stderr)
        self.fake('pidof','exit 1')
        result=subprocess.run(['sh',str(ROOT/'install-format.sh')],env=self.env,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(game_before,{str(p.relative_to(game_root)):p.read_bytes() for p in game_root.rglob('*') if p.is_file()})
        for relative,content in protected.items():
            self.assertEqual((self.profile/relative).read_bytes(),content,relative)
        for xml in ('MyGames.xml','MyMusicNav.xml','MusicVisualisation.xml'):
            self.assertEqual((self.target/'xml'/xml).read_bytes(),(ROOT/'skin/xml'/xml).read_bytes())
        for original in (ROOT/'skin/media/aperture/games/systems').iterdir():
            self.assertEqual((self.target/'media/aperture/games/systems'/original.name).read_bytes(),original.read_bytes())
        self.assertEqual(ET.parse(self.profile/'addons/plugin.audio.aperture.format/addon.xml').getroot().get('version'),'0.4.0')

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

    def broken_pi_font(self):
        p=self.skin/'fonts/Roboto-Thin.ttf'
        p.symlink_to('../../../fonts/truetype/roboto/Roboto-Thin.ttf')
        (self.skin/'xml/Font.xml').write_text('<fonts>\n<filename>regular.ttf</filename>\n<filename>Roboto-Thin.ttf</filename>\n<filename>arial.ttf</filename>\n</fonts>')
        actual=self.fonts/'truetype/roboto/unhinted/RobotoTTF/Roboto-Thin.ttf'
        actual.parent.mkdir(parents=True)
        return p,actual

    def assert_previous_preserved(self, result):
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((self.target/'keep.txt').read_text(),'old skin')
        self.assertFalse((self.profile/'.aperture-skin-install.lock').exists())
        self.assertEqual(list(self.profile.glob('.aperture-skin.*')),[])
        self.assertFalse((self.profile/'aperture-backups').exists())

    def without_python(self):
        # Only the installer's shell utilities, with no ambient Python search path.
        for name in ('sh','id','grep','dirname','mkdir','mktemp','cp','sed','sha256sum','sort','mv','rm','rmdir','cat'):
            (self.bin/name).symlink_to(shutil.which(name))
        self.env['PATH']=str(self.bin)

    def test_pi_relocated_font_is_materialized_without_system_or_profile_edits(self):
        self.existing();link,actual=self.broken_pi_font();actual.write_bytes(b'Pi Roboto Thin fixture')
        license_file=self.skin/'fonts/LICENSE.txt';license_file.write_text('Original font license')
        user=self.profile/'userdata';user.mkdir();(user/'guisettings.xml').write_text('existing settings')
        (user/'Database').mkdir();(user/'Database/Addons.db').write_bytes(b'existing database')
        r=self.run_install();self.assertEqual(r.returncode,0,r.stderr)
        installed=self.target/'fonts/Roboto-Thin.ttf'
        self.assertFalse(installed.is_symlink());self.assertEqual(installed.read_bytes(),actual.read_bytes())
        self.assertTrue(link.is_symlink());self.assertFalse(link.exists())
        self.assertEqual(actual.read_bytes(),b'Pi Roboto Thin fixture')
        self.assertEqual((self.target/'fonts/LICENSE.txt').read_text(),'Original font license')
        self.assertEqual((user/'guisettings.xml').read_text(),'existing settings')
        self.assertEqual((user/'Database/Addons.db').read_bytes(),b'existing database')
        self.assertEqual(len(list((self.profile/'aperture-backups').glob('*/skin.aperture/keep.txt'))),1)

    def test_missing_relocated_font_preserves_previous_and_cleans_stage(self):
        self.existing();self.broken_pi_font()
        r=self.run_install();self.assert_previous_preserved(r)
        self.assertIn('Unresolved distribution resource',r.stderr)

    def test_ambiguous_relocated_font_preserves_previous(self):
        self.existing();_,actual=self.broken_pi_font();actual.write_bytes(b'first')
        (self.fonts/'Roboto-Thin.ttf').write_bytes(b'other')
        r=self.run_install();self.assert_previous_preserved(r)
        self.assertIn('Ambiguous distribution font',r.stderr)

    def test_empty_relocated_font_preserves_previous(self):
        self.existing();_,actual=self.broken_pi_font();actual.touch()
        r=self.run_install();self.assert_previous_preserved(r)
        self.assertIn('Empty distribution font',r.stderr)

    def test_missing_non_font_does_not_search_font_root(self):
        self.existing();(self.skin/'missing.png').symlink_to('absent.png')
        (self.fonts/'missing.png').write_bytes(b'not the resource')
        r=self.run_install();self.assert_previous_preserved(r)
        self.assertIn('Unresolved distribution resource',r.stderr)

    def test_pythonless_install_still_materializes_intact_links(self):
        self.without_python();link=self.skin/'fonts/regular.ttf';link.unlink()
        real=self.root/'real font.ttf';real.write_bytes(b'valid installed font');link.symlink_to(real)
        r=self.run_install();self.assertEqual(r.returncode,0,r.stderr)
        self.assertFalse((self.target/'fonts/regular.ttf').is_symlink())
        self.assertEqual((self.target/'fonts/regular.ttf').read_bytes(),real.read_bytes())

    def test_pythonless_broken_font_preserves_previous(self):
        self.existing();self.broken_pi_font();self.without_python()
        r=self.run_install();self.assert_previous_preserved(r)
        self.assertIn('use Python 3 with the complete checkout',r.stderr)

    def test_intact_directory_symlink_remains_supported(self):
        actual=self.root/'distribution media';actual.mkdir();(actual/'image.png').write_bytes(b'image fixture')
        (self.skin/'media').symlink_to(actual,target_is_directory=True)
        r=self.run_install();self.assertEqual(r.returncode,0,r.stderr)
        self.assertFalse((self.target/'media').is_symlink())
        self.assertEqual((self.target/'media/image.png').read_bytes(),b'image fixture')

    def test_relative_font_root_refused_before_profile_creation(self):
        self.env['APERTURE_FONT_ROOT']='relative/fonts'
        r=self.run_install();self.assertNotEqual(r.returncode,0)
        self.assertFalse(self.profile.exists())

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

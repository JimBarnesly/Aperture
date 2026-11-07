import importlib.util
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
spec = importlib.util.spec_from_file_location('build_skin', ROOT/'tools/build_skin.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class SkinBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root/'source'
        (self.source/'xml').mkdir(parents=True)
        (self.source/'fonts').mkdir()
        (self.source/'fonts/regular.ttf').write_bytes(b'font fixture')
        (self.source/'xml/Includes.xml').write_text('<includes><include name="DialogBackgroundCommons"><control type="group"/></include></includes>')
        for name in ('Includes_Buttons.xml','Includes_DialogSelect.xml'):
            (self.source/'xml'/name).write_text('<includes/>')
        (self.source/'addon.xml').write_text('<addon id="skin.estuary" version="4.0.0"><requires><import addon="xbmc.gui" version="5.17.0"/></requires><extension point="xbmc.addon.metadata"><license>Original</license></extension></addon>')
        (self.source/'xml/Font.xml').write_text('<fonts><fontset><font><name>font32</name><filename>regular.ttf</filename></font><font><name>font13</name><filename>regular.ttf</filename></font><font><name>font60</name><filename>regular.ttf</filename></font><font><name>font_clock</name><filename>regular.ttf</filename></font><font><name>font10</name><filename>regular.ttf</filename></font></fontset></fonts>')
        for name in ('Home.xml', 'Settings.xml', 'SettingsCategory.xml', 'DialogConfirm.xml'):
            (self.source/'xml'/name).write_text('<window/>')
        self.out = self.root/'skin.aperture'

    def assemble(self):
        return build.assemble(self.source, self.out, ROOT/'skin/xml/Home.xml')

    def test_manifest_upgrade_and_license_preserved(self):
        self.assemble()
        root = ET.parse(self.out/'addon.xml').getroot()
        self.assertEqual(root.get('id'), 'skin.aperture')
        self.assertEqual(root.get('version'), '4.0.1~rc1')
        self.assertEqual(root.findtext('./extension/license'), 'Original')
        self.assertEqual(ET.parse(self.source/'addon.xml').getroot().get('id'), 'skin.estuary')

    def test_music_overlay_is_complete_and_exact(self):
        self.assemble()
        for filename in ('DialogSeekBar.xml', 'Custom_1109_TopBarOverlay.xml', 'MusicOSD.xml'):
            self.assertEqual((self.out/'xml'/filename).read_bytes(), (ROOT/'skin/xml'/filename).read_bytes())

    def test_packaging_is_reproducible(self):
        self.assemble()
        a = build.package(self.out, self.root/'one.zip')
        b = build.package(self.out, self.root/'two.zip')
        self.assertEqual(a,b)

    def test_default_build_matches_exact_fresh_zip_acceptance_set(self):
        from zip_smoke_fixture import packages
        repo = self.root / 'repo'
        repo.mkdir()
        for name in ('skin', 'format-kodi', 'movies-kodi', 'docs', 'LICENSE'):
            (repo / name).symlink_to(ROOT / name)
        with patch.object(build, 'ROOT', repo), patch.object(sys, 'argv',
                ['build_skin.py', '--source', str(self.source), '--output', str(self.out)]), patch('builtins.print'):
            build.main()
        rows = packages(repo / 'dist')
        self.assertEqual([row['addon'] for row in rows],
                         ['plugin.audio.aperture.format', 'plugin.video.aperture.movies', 'skin.aperture'])
        self.assertEqual([row['version'] for row in rows], [
            ET.parse(ROOT / 'format-kodi/addon.xml').getroot().get('version'),
            ET.parse(ROOT / 'movies-kodi/addon.xml').getroot().get('version'), build.VERSION])

    def test_unknown_font_rejected(self):
        self.assemble()
        p=self.out/'xml/Home.xml'; p.write_text(p.read_text().replace('font32','font30'))
        with self.assertRaisesRegex(ValueError, 'undefined font'):
            build.validate_skin(self.out)

    def test_dangling_navigation_rejected(self):
        self.assemble()
        p=self.out/'xml/Home.xml'; p.write_text(p.read_text().replace('<onup>106</onup>','<onup>999</onup>'))
        with self.assertRaisesRegex(ValueError, 'missing Home control'):
            build.validate_skin(self.out)

    def test_dereferences_relative_font(self):
        font = self.source/'fonts/regular.ttf'
        font.unlink(); (self.root/'external.ttf').write_bytes(b'official font fixture')
        font.symlink_to('../../external.ttf')
        self.assemble()
        self.assertFalse((self.out/'fonts/regular.ttf').is_symlink())
        self.assertEqual((self.out/'fonts/regular.ttf').read_bytes(),b'official font fixture')

    def test_exact_font_name_resolution_and_canonical_deduplication(self):
        link=self.source/'fonts/regular.ttf';link.unlink();link.symlink_to('missing.ttf')
        roots=self.root/'fonts';roots.mkdir();actual=roots/'regular.ttf';actual.write_bytes(b'exact')
        alias=roots/'other';alias.mkdir();(alias/'regular.ttf').symlink_to(actual)
        build.copy_skin(self.source,self.out,[roots,roots])
        self.assertEqual((self.out/'fonts/regular.ttf').read_bytes(),b'exact')
        self.assertTrue(link.is_symlink());self.assertFalse(link.exists())

    def test_font_name_is_literal_not_a_glob(self):
        (self.source/'fonts/f[1].ttf').symlink_to('missing.ttf')
        roots=self.root/'fonts';roots.mkdir();(roots/'f1.ttf').write_bytes(b'wrong name')
        (roots/'f[1].ttf').write_bytes(b'literal name')
        build.copy_skin(self.source,self.out,[roots])
        self.assertEqual((self.out/'fonts/f[1].ttf').read_bytes(),b'literal name')

    def test_regular_empty_font_is_rejected(self):
        (self.source/'fonts/regular.ttf').write_bytes(b'')
        with self.assertRaisesRegex(ValueError,'Empty distribution font'):
            build.copy_skin(self.source,self.out)

    def test_copy_only_cannot_replace_existing_directory(self):
        self.out.mkdir();(self.out/'keep').write_text('valuable')
        r=subprocess.run([sys.executable,str(ROOT/'tools/build_skin.py'),'--copy-only','--source',str(self.source),'--output',str(self.out)],text=True,capture_output=True)
        self.assertNotEqual(r.returncode,0)
        self.assertEqual((self.out/'keep').read_text(),'valuable')

    def test_copy_only_uses_only_explicit_font_root_and_does_not_assemble(self):
        link=self.source/'fonts/regular.ttf';link.unlink();link.symlink_to('missing.ttf')
        roots=self.root/'fonts';roots.mkdir();(roots/'regular.ttf').write_bytes(b'explicit font')
        r=subprocess.run([sys.executable,str(ROOT/'tools/build_skin.py'),'--copy-only','--source',str(self.source),'--output',str(self.out),'--font-root',str(roots)],text=True,capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(ET.parse(self.out/'addon.xml').getroot().get('id'),'skin.estuary')
        self.assertFalse((self.out/'APERTURE_BUILD.json').exists())
        self.assertEqual((self.out/'fonts/regular.ttf').read_bytes(),b'explicit font')

    def test_explicit_font_root_replaces_default_search_path(self):
        with patch.object(sys, 'argv', ['build_skin.py','--copy-only','--font-root',str(self.root)]), patch.object(build,'copy_skin') as copy:
            build.main()
        self.assertEqual(copy.call_args.args[2],[self.root])

    def test_missing_resource_does_not_replace_good_output(self):
        self.assemble()
        old=(self.out/'addon.xml').read_bytes()
        (self.source/'missing').symlink_to('absent')
        with self.assertRaisesRegex(ValueError,'Unresolved'):
            self.assemble()
        self.assertEqual((self.out/'addon.xml').read_bytes(),old)

    def test_unknown_output_is_not_deleted(self):
        self.out.mkdir(); (self.out/'keep').write_text('valuable')
        with self.assertRaisesRegex(ValueError,'unmarked'):
            self.assemble()
        self.assertTrue((self.out/'keep').exists())

    def test_requires_omega_gui(self):
        p=self.source/'addon.xml'; p.write_text(p.read_text().replace('5.17.0','5.15.0'))
        with self.assertRaisesRegex(ValueError,'Kodi 21'):
            self.assemble()

    def test_complete_home_focus_graph(self):
        home=ET.parse(ROOT/'skin/xml/Home.xml').getroot()
        controls={c.get('id'):c for c in home.iter('control') if c.get('id') and c.get('type')=='button'}
        pending=[home.findtext('defaultcontrol')];seen=set()
        while pending:
            current=pending.pop()
            if current in seen:continue
            seen.add(current)
            pending.extend(controls[current].findtext(key) for key in ('onup','ondown','onleft','onright') if controls[current].findtext(key) in controls)
        self.assertEqual(seen,set(controls))

if __name__=='__main__':
    unittest.main()

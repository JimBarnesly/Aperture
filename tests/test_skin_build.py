import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
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

    def test_packaging_is_reproducible(self):
        self.assemble()
        a = build.package(self.out, self.root/'one.zip')
        b = build.package(self.out, self.root/'two.zip')
        self.assertEqual(a,b)

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
        controls={c.get('id'):c for c in home.iter('control') if c.get('id')}
        pending=[home.findtext('defaultcontrol')];seen=set()
        while pending:
            current=pending.pop()
            if current in seen:continue
            seen.add(current)
            pending.extend(controls[current].findtext(key) for key in ('onup','ondown','onleft','onright') if controls[current].findtext(key) in controls)
        self.assertEqual(seen,set(controls))

if __name__=='__main__':
    unittest.main()

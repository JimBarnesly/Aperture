"""Pure fixture safety/byte checks; these tests never launch a GUI or install."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('zip_fixture', ROOT / 'tools/zip_smoke_fixture.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class ZipFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='apeture-kodi-smoke.')
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name)
        self.root = self.runtime / 'repo'
        (self.root / 'dist').mkdir(parents=True)
        (self.root / 'tools').mkdir()
        (self.root / 'tools/zip_smoke_observer.py').write_text('# unit-test stub, never run\n', encoding='utf-8')
        self.rows = []
        for addon in fixture.SUBJECTS:
            filename = addon + '-1.0.0~rc1.zip'
            path = self.root / 'dist' / filename
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr(addon + '/addon.xml', '<addon id="{}" name="Aperture" version="1.0.0~rc1"/>'.format(addon))
                archive.writestr(addon + '/payload.txt', 'non-ASCII fixture: café')
            self.rows.append({'addon': addon, 'version': '1.0.0~rc1', 'file': filename,
                              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        self.write_manifest()
        self.system = self.runtime / 'system'
        (self.system / 'system').mkdir(parents=True)
        for addon in (*fixture.SUBJECTS, 'skin.estuary', 'service.apeture.cismoke', 'service.apeture.musicsmoke'):
            (self.system / 'addons' / addon).mkdir(parents=True)
            (self.system / 'addons' / addon / 'addon.xml').write_text('<addon/>')
        (self.system / 'system/addon-manifest.xml').write_text('<addons>' + ''.join('<addon>{}</addon>'.format(a)
            for a in (*fixture.SUBJECTS, 'skin.estuary', 'service.apeture.cismoke')) + '</addons>')

    def write_manifest(self):
        (self.root / 'dist/checksums.json').write_text(json.dumps(self.rows), encoding='utf-8')

    def prepare(self):
        return fixture.prepare(self.root, self.runtime, self.system, self.runtime / 'evidence')

    def test_fresh_profile_has_stock_skin_no_subjects_and_sources_off(self):
        target, rows = self.prepare()
        self.assertEqual(rows, self.rows)
        self.assertFalse((target / 'data/addons').exists())
        self.assertFalse((target / 'data/userdata/Database').exists())
        for addon in fixture.SUBJECTS:
            self.assertFalse((target / 'system/addons' / addon).exists())
        manifest = ET.parse(target / 'system/system/addon-manifest.xml')
        self.assertEqual({x.text for x in manifest.getroot()}, {'skin.estuary', fixture.OBSERVER})
        settings = ET.parse(target / 'data/userdata/guisettings.xml')
        self.assertEqual(settings.findtext("./setting[@id='lookandfeel.skin']"), 'skin.estuary')
        self.assertEqual(settings.findtext("./setting[@id='addons.unknownsources']"), 'false')
        self.assertTrue(all(item.text == 'false' for item in settings.findall('setting') if item.get('id').startswith('services.')))
        self.assertEqual({p.name for p in (target / 'packages').iterdir()}, {r['file'] for r in rows})

    def test_existing_target_is_never_replaced(self):
        self.prepare()
        with self.assertRaises(ValueError):
            self.prepare()

    def test_unmarked_or_mismatched_system_is_rejected(self):
        with self.assertRaises(ValueError):
            fixture.prepare(self.root, self.runtime, self.root, self.runtime / 'evidence')

    def test_wrong_hash_is_rejected_before_profile_creation(self):
        self.rows[0]['sha256'] = '0' * 64
        self.write_manifest()
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse((self.runtime / 'fresh-zip').exists())

    def test_extra_addon_is_never_accepted(self):
        self.rows.append(dict(self.rows[0], addon='unrecognized.other'))
        self.write_manifest()
        with self.assertRaises(ValueError):
            self.prepare()

    def test_unsafe_zip_member_is_rejected(self):
        row = self.rows[0]
        path = self.root / 'dist' / row['file']
        with zipfile.ZipFile(path, 'a') as archive:
            archive.writestr(row['addon'] + '/../outside.txt', 'bad')
        row['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write_manifest()
        with self.assertRaises(ValueError):
            self.prepare()

    def test_installed_byte_verifier_detects_missing_and_modified_files(self):
        target, rows = self.prepare()
        with self.assertRaises(AssertionError):
            fixture.verify_installed(target / 'packages', target / 'data', rows)
        # Simulated extraction here tests only the comparator, not installation.
        for row in rows:
            with zipfile.ZipFile(target / 'packages' / row['file']) as archive:
                archive.extractall(target / 'data/addons')
        result = fixture.verify_installed(target / 'packages', target / 'data', rows)
        self.assertEqual([item['files_verified'] for item in result], [2, 2, 2])
        (target / 'data/addons/skin.apeture/payload.txt').write_text('changed')
        with self.assertRaises(AssertionError):
            fixture.verify_installed(target / 'packages', target / 'data', rows)


if __name__ == '__main__':
    unittest.main()

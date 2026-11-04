"""Cinematic movie view contracts, native navigation, and distributable artwork."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
XML = ROOT / 'skin/xml/MyVideoNav.xml'

class MovieSkinTests(unittest.TestCase):
    def setUp(self):
        self.tree = ET.parse(XML)
        self.view = self.tree.find('.//control[@id="61"]')

    def test_plugin_only_native_container(self):
        self.assertIsNotNone(self.view)
        self.assertEqual(self.view.findtext('visible'), 'String.IsEqual(Container.PluginName,plugin.video.aperture.movies)')
        self.assertIsNone(self.view.find('content'))
        self.assertEqual(list(self.view.iter('onclick')), [])
        self.assertEqual(self.view.findtext('viewtype'), 'icon')
        for direction in ('onleft', 'onright', 'onup', 'ondown'):
            self.assertEqual(self.view.findtext(direction), '61')

    def test_native_views_remain_and_control_ids_are_unique(self):
        self.assertEqual(self.tree.findtext('defaultcontrol'), '50')
        views = set(self.tree.findtext('views').split(','))
        self.assertTrue({'61','50','51','52','53','54','55','500','501','502'}.issubset(views))
        native = self.tree.find('./controls/control')
        self.assertEqual(native.findtext('visible'), '!Control.IsVisible(61)')
        self.assertTrue(any(i.text == 'View_50_List' for i in native.iter('include')))
        ids = [c.get('id') for c in self.tree.iter('control') if c.get('id')]
        self.assertEqual(len(ids), len(set(ids)))

    def test_dynamic_art_has_original_packaged_fallback(self):
        for texture in self.tree.iter('texture'):
            for path in (texture.text, texture.get('fallback')):
                if path and path.startswith('aperture/movies/'):
                    image = ROOT / 'skin/media' / path
                    self.assertTrue(image.is_file(), str(image))
                    with Image.open(image) as im:
                        im.verify()
        dynamic = [n for n in self.tree.iter('texture') if n.text and 'ListItem.Art' in n.text]
        self.assertTrue(any('fanart' in n.text for n in dynamic))
        self.assertTrue(any('poster' in n.text for n in dynamic))
        self.assertTrue(all(n.get('fallback') for n in dynamic))

    def test_no_filler_plot_or_unsupported_arrow_glyphs(self):
        labels = [node.text or '' for node in self.tree.iter('label')]
        self.assertFalse(any('Your collection. A world of stories.' in label for label in labels))
        self.assertFalse(any('←' in label or '→' in label for label in labels))
        self.assertTrue(any(label.startswith('Left / Right  Browse') for label in labels))

    def test_focus_is_visible_and_filmstrip_fits(self):
        self.assertEqual(self.view.findtext('orientation'), 'horizontal')
        for name in ('itemlayout','focusedlayout'):
            layout = self.view.find(name)
            self.assertLessEqual(int(layout.get('height')), int(self.view.findtext('height')))
        focused = self.view.find('focusedlayout')
        self.assertTrue(any(n.text == 'aperture/movies/accent.png' for n in focused.iter('texture')))
        self.assertFalse(any('http' in (n.text or '') for n in self.tree.iter('texture')))

if __name__ == '__main__':
    unittest.main()

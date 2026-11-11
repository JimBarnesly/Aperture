"""XML focus contract; physical held-key acceptance remains native-only."""
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[1]


class SourceNavigationTests(unittest.TestCase):
    def test_single_press_header_button_reaches_nonmodal_source_directory(self):
        root = ET.parse(ROOT / 'skin/xml/MyVideoNav.xml').getroot()
        button = root.find('.//control[@id="716"]')
        self.assertIsNotNone(button, 'Choose source must be a visible D-pad action, not long press')
        self.assertEqual(button.findtext('label'), 'Choose source')
        self.assertEqual(root.findtext('.//control[@id="715"]/onright'), '716')
        self.assertEqual(button.findtext('ondown'), '61')
        self.assertIn('Container(61).ListItem.Property(Aperture.MovieID)', button.findtext('onclick'))
        self.assertIn('action=torrentio_sources', button.findtext('onclick'))
        self.assertIn('resume=$INFO[Container(61).ListItem.Property(Aperture.SourceResume)]', button.findtext('onclick'))
        self.assertIn('Container.Update', button.findtext('onclick'))
        self.assertIn('Container.Content(files)', root.findtext('.//control[@id="61"]/visible'))

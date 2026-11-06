"""Home playback bar contracts; native state/navigation covered by menu smoke."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as E
ROOT = Path(__file__).resolve().parents[1]
class HomeNowPlaying(unittest.TestCase):
 def setUp(self):
  self.root = E.parse(ROOT/'skin/xml/Home.xml')
  self.bar = self.root.find('.//control[@id="120"]')
 def test_visible_only_for_audio_or_video_including_pause(self):
  self.assertEqual(self.bar.findtext('visible'),'Player.HasAudio | Player.HasVideo')
  self.assertEqual(self.bar.find('visible').get('allowhiddenfocus'),'true')
 def test_remote_routes_preserve_idle_navigation(self):
  for ident in range(100,107):
   b=self.root.find('.//control[@id="%s"]'%ident)
   self.assertEqual(b.find('onright').text,'120')
   self.assertEqual(len(b.findall('onright')),2)
  for direction in ('onleft','onright','onup','ondown'):
   self.assertEqual(self.bar.findtext(direction),'103')
  self.assertEqual(self.bar.findtext('onback'),'SetFocus(103)')
 def test_actions_reuse_home_destinations(self):
  actions=self.bar.findall('onclick')
  for ident in ('100','101','103'):
   for source in self.root.findall('.//control[@id="'+ident+'"]/onclick'):
    self.assertTrue(any(a.text==source.text for a in actions))
  self.assertTrue(all('Player.Has' in a.get('condition','') for a in actions))
  self.assertFalse(any('PlayMedia' in a.text or 'PlayerControl' in a.text for a in actions))
 def test_metadata_has_fallback_pause_and_no_path(self):
  text=E.tostring(self.root.find('.//control[@id="119"]'),encoding='unicode')
  for part in ('Current media','PAUSED','Player.Title','MusicPlayer.Artist','VideoPlayer.TVShowTitle'):
   self.assertIn(part,text)
  self.assertNotIn('Filename',text)
  self.assertNotIn('Path',text)

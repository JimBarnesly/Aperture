from pathlib import Path
import hashlib
import re
import unittest
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
class BrowserSkinTests(unittest.TestCase):
 def test_views_keep_native_fallback_and_unique_ids(self):
  tree=ET.parse(ROOT/'skin/xml/MyGames.xml')
  self.assertEqual(tree.findtext('defaultcontrol'),'50')
  self.assertTrue({'59','60','50','55'}.issubset(tree.findtext('views').split(',')))
  ids=[e.get('id') for e in tree.iter('control') if e.get('id')]
  self.assertEqual(len(ids),len(set(ids)))
  for vid in ('59','60'):
   c=tree.find('.//control[@id="'+vid+'"]')
   kind='systems' if vid=='59' else 'games'
   self.assertEqual(c.findtext('visible'),'String.IsEqual(Container.PluginName,plugin.games.aperture) + String.IsEqual(Container.Property(Aperture.View),'+kind+')')
   self.assertIsNone(c.find('content'))
   self.assertEqual(list(c.iter('onclick')),[])
 def test_directory_switch_prefers_the_eligible_custom_view(self):
  tree=ET.parse(ROOT/'skin/xml/MyGames.xml')
  # Kodi first falls back to an eligible view of the current type. Both
  # custom views must precede the native views and share that type so Back
  # from the game list selects cards rather than a native list fallback.
  self.assertEqual(tree.findtext('views').split(',')[:2],['59','60'])
  for vid in ('59','60'):
   self.assertEqual(tree.find('.//control[@id="'+vid+'"]/viewtype').text,'list')
 def test_static_game_textures_are_packaged(self):
  for node in ET.parse(ROOT/'skin/xml/MyGames.xml').iter('texture'):
   if node.text and node.text.startswith('aperture/games/'):
    self.assertTrue((ROOT/'skin/media'/node.text).is_file())
 def test_installer_checks_browser_integrity(self):
  expected=re.search(r'GAMES_SHA=([a-f0-9]{64})',(ROOT/'install.sh').read_text()).group(1)
  self.assertEqual(expected,hashlib.sha256((ROOT/'skin/xml/MyGames.xml').read_bytes()).hexdigest())

class SystemCarouselTests(unittest.TestCase):
 def setUp(self):
  self.tree=ET.parse(ROOT/'skin/xml/MyGames.xml')
  self.carousel=self.tree.find('.//control[@id="59"]')

 def test_real_horizontal_centered_wraplist_owns_selection(self):
  self.assertEqual(self.carousel.get('type'),'wraplist')
  self.assertEqual(self.carousel.findtext('orientation'),'horizontal')
  self.assertEqual(self.carousel.findtext('focusposition'),'1')
  self.assertEqual(self.carousel.findtext('width'),'1860')
  for tag in ('itemlayout','focusedlayout'):
   self.assertEqual(self.carousel.find(tag).get('width'),'620')
  # Do not replace Kodi's folder selection or Back history with click handlers.
  self.assertFalse(list(self.carousel.iter('onclick')))
  self.assertIsNone(self.carousel.find('onback'))
  self.assertIsNone(self.carousel.find('content'))

 def test_every_supported_system_has_distinct_original_art(self):
  import importlib.util, struct
  spec=importlib.util.spec_from_file_location('game_art',ROOT/'tools/build_game_art.py')
  art=importlib.util.module_from_spec(spec);spec.loader.exec_module(art)
  catalog_spec=importlib.util.spec_from_file_location('game_catalog',ROOT/'games-kodi/resources/lib/apeture_library/catalog.py')
  catalog=importlib.util.module_from_spec(catalog_spec);catalog_spec.loader.exec_module(catalog)
  hashes=[];geometries=[]
  for system in catalog.SYSTEMS:
   with self.subTest(system=system.id):
    source=ROOT/'skin/artwork/games'/(system.id+'.svg')
    self.assertEqual(source.read_text(),art.svg(system.id)+'\n')
    ET.parse(source)
    png=(ROOT/'skin/media/aperture/games/systems'/(system.id+'.png')).read_bytes()
    self.assertEqual(png[:8],b'\x89PNG\r\n\x1a\n')
    self.assertEqual(struct.unpack('>II',png[16:24]),(640,560))
    hashes.append(hashlib.sha256(png).hexdigest())
    geometries.append(art.console(system.id))
  self.assertEqual(len(set(hashes)),len(catalog.SYSTEMS))
  self.assertEqual(len(set(geometries)),len(catalog.SYSTEMS))

 def test_actions_and_back_are_not_disguised_as_consoles(self):
  for tag in ('itemlayout','focusedlayout'):
   layout=self.carousel.find(tag)
   images=layout.findall('./control[@type="image"]')
   textures={c.findtext('texture'):c.findtext('visible') for c in images}
   system='$INFO[ListItem.Property(Aperture.System),aperture/games/systems/,.png]'
   self.assertIn('String.IsEmpty(ListItem.Property(Aperture.Action))',textures[system])
   self.assertIn('!ListItem.IsParentFolder',textures[system])
   for action in ('settings','help','refresh'):
    self.assertIn('aperture/games/systems/utility-'+action+'.png',textures)
   self.assertEqual(textures['aperture/games/systems/utility-back.png'],'ListItem.IsParentFolder')
   self.assertTrue(any(c.findtext('label')=='Back' and c.findtext('visible')=='ListItem.IsParentFolder' for c in layout.findall('control')))
   self.assertTrue(any('Aperture.Action),root)' in c.findtext('visible','') for c in images))

 def test_unknown_art_falls_back_and_count_uses_cached_property(self):
  images=[c for c in self.carousel.findall('.//control[@type="image"]') if c.findtext('texture','').startswith('$INFO')]
  self.assertEqual(len(images),2)
  for image in images:
   self.assertEqual(image.find('texture').get('fallback'),'aperture/games/systems/default.png')
  labels=[c for c in self.tree.findall('.//control[@type="label"]') if 'Aperture.GameCount' in c.findtext('label','')]
  self.assertTrue(labels)
  self.assertTrue(all('String.IsEmpty(ListItem.Property(Aperture.GameCount))' in c.findtext('visible','') for c in labels))

 def test_runtime_assets_have_redistribution_notice(self):
  notice=(ROOT/'skin/licenses/APERTURE_GAME_ART.md').read_text()
  self.assertIn('GPL-3.0-or-later',notice)
  self.assertIn('original',notice)

if __name__=='__main__':unittest.main()

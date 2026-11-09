from pathlib import Path
import importlib.util
import unittest
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('discovery', ROOT/'movies-kodi/resources/lib/discovery.py')
discovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(discovery)


class DiscoveryModelTests(unittest.TestCase):
    def test_unknown_inputs_are_bounded(self):
        params, state, _ = discovery.request({'start':['bad'], 'collection':['anything'], 'search':['x'*250]})
        self.assertEqual(params['limits'], {'start':0, 'end':60})
        self.assertEqual(state['collection'], 'all')
        self.assertEqual(len(state['search']),200)
        for start, expected in [('-1',0),('999999999',1000000)]:
            self.assertEqual(discovery.request({'start':[start]})[0]['limits']['start'],expected)
    def test_collection_sorting(self):
        for collection, method in [('all','title'),('recent','dateadded'),('rated','rating'),('resume','lastplayed')]:
            params, _, _ = discovery.request({'collection':[collection]})
            self.assertEqual(params['sort']['method'],method)
    def test_clear_state_does_not_keep_empty_filters(self):
        params, state, _ = discovery.request({'search':['  '],'genre':['']})
        self.assertNotIn('filter',params);self.assertNotIn('search',state)
    def test_navigation_has_closed_focus_graph(self):
        root=ET.parse(ROOT/'skin/xml/MyVideoNav.xml')
        for n in range(710,716):
            button=root.find(f".//control[@id='{n}']")
            self.assertIsNotNone(button)
            for direction in ('onleft','onright'):
                self.assertIn(int(button.findtext(direction)),range(710,716))
            self.assertEqual(button.findtext('ondown'),'61')
        self.assertEqual(root.find(".//control[@id='61']/onup").text,'710')

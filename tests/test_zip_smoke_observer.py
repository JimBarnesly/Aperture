"""Read-only observer concurrency regressions, not graphical acceptance."""
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
import types
import unittest
from unittest.mock import patch


class ZipObserverTests(unittest.TestCase):
    def setUp(self):
        modules = {name: types.ModuleType(name) for name in ('xbmc', 'xbmcaddon', 'xbmcgui')}
        with patch.dict(sys.modules, modules):
            source = Path(__file__).resolve().parents[1] / 'tools/zip_smoke_observer.py'
            spec = importlib.util.spec_from_file_location('zip_observer', source)
            self.observer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.observer)

    def test_blocked_setting_read_does_not_freeze_modal_observation(self):
        entered, release, stopped = threading.Event(), threading.Event(), threading.Event()
        class Monitor:
            def abortRequested(self): return stopped.is_set()
            def waitForAbort(self, timeout): return stopped.wait(timeout)
        class Window:
            def getFocusId(self): return 10
            def getControl(self, identifier): raise RuntimeError('No fixture control')
            def getProperty(self, key): return ''
        def blocked_rpc(payload):
            self.assertEqual(json.loads(payload)['method'], 'Settings.GetSettingValue')
            entered.set()
            if not release.wait(2): raise RuntimeError('Test settings read did not release')
            return json.dumps({'result': {'value': True}})
        o = self.observer
        o.xbmc.executeJSONRPC = blocked_rpc
        o.xbmcgui.getCurrentWindowId = lambda: 10016
        o.xbmcgui.getCurrentWindowDialogId = lambda: 10100
        o.xbmcgui.Window = lambda *args: Window()
        o.xbmcgui.getScreenWidth = lambda: 1920
        o.xbmcgui.getScreenHeight = lambda: 1080
        o.xbmc.getCondVisibility = lambda *args: False
        o.xbmc.getSkinDir = lambda: 'skin.estuary'
        o.xbmc.getInfoLabel = lambda label: 'No' if label == 'System.CurrentControl' else ''
        reader = o.SettingsReader(Monitor())
        reader.thread.start()
        try:
            self.assertTrue(entered.wait(1))
            first, second = o.observe(1, reader), o.observe(2, reader)
            self.assertEqual((first['dialog'], second['sequence'], second['control_label']), (10100, 2, 'No'))
            self.assertIsNone(second['unknown_sources'])
            self.assertEqual(second['unknown_sources_read_completed'], 0)
            release.set()
            until = time.monotonic() + 1
            while reader.snapshot()['unknown_sources'] is None and time.monotonic() < until:
                time.sleep(0.01)
            state = o.observe(3, reader)
            self.assertIs(state['unknown_sources'], True)
            self.assertGreaterEqual(state['unknown_sources_read_completed'], state['unknown_sources_read_started'])
        finally:
            release.set()
            stopped.set()
            reader.thread.join(2)
        self.assertFalse(reader.thread.is_alive())

    def test_invalid_setting_reply_is_not_silently_assumed_false(self):
        o = self.observer
        o.xbmc.executeJSONRPC = lambda payload: '{"error": {"message": "Unavailable"}}'
        monitor = types.SimpleNamespace(abortRequested=lambda: False)
        reader = o.SettingsReader(monitor)
        reader.run()
        with self.assertRaisesRegex(RuntimeError, 'Cannot observe Unknown sources'):
            reader.snapshot()


if __name__ == '__main__': unittest.main()

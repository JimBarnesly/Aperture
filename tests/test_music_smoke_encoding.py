"""Regression for Kodi's embedded Python using an ASCII process locale.

These are fixture-I/O tests, not native GUI/playback acceptance.
"""
import ast
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MusicSmokeEncodingTests(unittest.TestCase):
    def test_observer_history_and_atomic_state_preserve_unicode_under_ascii_locale(self):
        code = r'''
import importlib.util, json, locale, pathlib, sys, tempfile, types
assert locale.getpreferredencoding(False).lower() in ("ascii", "ansi_x3.4-1968")
root = pathlib.Path(sys.argv[1])
for name in ("xbmc", "xbmcaddon", "xbmcgui"):
    sys.modules[name] = types.ModuleType(name)
class Monitor:
    def abortRequested(self): return False
    def waitForAbort(self, timeout): return True
sys.modules["xbmc"].Monitor = Monitor
spec = importlib.util.spec_from_file_location("observer", root / "tools/music_smoke_observer.py")
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)
payload = {"album": "SYNTHETIC QA \u2014 Double", "artist": "Caf\u00e9 \u97f3\u697d"}
with tempfile.TemporaryDirectory() as directory:
    out = pathlib.Path(directory)
    observer.verified_config = lambda: {"out": str(out)}
    observer.snapshot = lambda *args: payload
    observer.main()
    for name in ("music-state.json", "music-states.jsonl"):
        raw = (out / name).read_bytes()
        assert b"\xe2\x80\x94" in raw
        assert json.loads(raw.decode("utf-8")) == payload
    assert not (out / "music-state.json.tmp").exists()
spec = importlib.util.spec_from_file_location("fixture", root / "tools/music_smoke_fixture.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
assert len(fixture.verify()["albums"]) == 7
'''
        env = dict(os.environ, LC_ALL="C", LANG="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0")
        result = subprocess.run([sys.executable, "-X", "utf8=0", "-c", code, str(ROOT)],
                                env=env, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))

    def test_music_fixture_text_io_declares_utf8(self):
        # Covers command/result/error paths as well as the observer history.
        for name in ("observer", "fixture", "driver"):
            path = ROOT / ("tools/music_smoke_" + name + ".py")
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                method = node.func.attr
                if method == "open":
                    mode = node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) else None
                    if not isinstance(mode, str) or "b" in mode:
                        continue
                elif method not in ("read_text", "write_text"):
                    continue
                encoding = next((kw.value for kw in node.keywords if kw.arg == "encoding"), None)
                self.assertIsInstance(encoding, ast.Constant, (path.name, node.lineno))
                self.assertEqual(encoding.value, "utf-8", (path.name, node.lineno))


if __name__ == "__main__":
    unittest.main()

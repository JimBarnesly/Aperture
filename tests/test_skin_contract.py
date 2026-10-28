"""Static contracts for authored Home controls, not renderer/playback tests."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT / "addons/skin.apeture"


class HomeContractTests(unittest.TestCase):
    def setUp(self):
        self.home = ET.parse(SKIN / "xml/Home.xml").getroot()
        self.controls = {node.get("id"): node for node in self.home.iter("control") if node.get("id")}

    def test_default_control_and_neighbors_exist(self):
        self.assertIn(self.home.findtext("defaultcontrol"), self.controls)
        for identifier, node in self.controls.items():
            for direction in ("onup", "ondown", "onleft", "onright"):
                neighbor = node.findtext(direction)
                if neighbor and neighbor.isdigit() and neighbor != "0":
                    with self.subTest(control=identifier, direction=direction):
                        self.assertIn(neighbor, self.controls)

    def test_game_entry_uses_native_games_window(self):
        actions = [node.text or "" for node in self.home.iter("onclick")]
        routes = [action for action in actions if "plugin://plugin.games.apeture/" in action]
        self.assertTrue(routes)
        for route in routes:
            self.assertTrue(route.startswith("ActivateWindow(Games,"), route)

    def test_home_fonts_exist(self):
        fonts = {node.findtext("name") for node in ET.parse(SKIN / "xml/Font.xml").iter("font")}
        for node in self.home.iter("font"):
            self.assertIn(node.text, fonts)

    def test_focusable_controls_have_visible_focus(self):
        for identifier, node in self.controls.items():
            if node.get("type") == "button":
                with self.subTest(control=identifier):
                    self.assertTrue(node.findtext("texturefocus"))
                    self.assertTrue(node.findtext("label"))

    def test_playback_controls_have_no_media_feedback(self):
        actions = self.controls["9202"].findall("onclick")
        self.assertTrue(any(node.get("condition") == "Player.HasMedia" and node.text == "ActivateWindow(playercontrols)" for node in actions))
        self.assertTrue(any(node.get("condition") == "!Player.HasMedia" and (node.text or "").startswith("Notification(") for node in actions))


if __name__ == "__main__":
    unittest.main()

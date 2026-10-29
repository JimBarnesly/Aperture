"""Games-only XML contract checks; real Kodi renderer evidence is separate."""

from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT / "addons/skin.apeture"


class GamesSkinTests(unittest.TestCase):
    def setUp(self):
        self.window = ET.parse(SKIN / "xml/MyGames.xml").getroot()
        self.controls = {node.get("id"): node for node in self.window.iter("control") if node.get("id")}

    def test_native_directory_list_is_only_registered_view(self):
        self.assertEqual(self.window.findtext("defaultcontrol"), "50")
        self.assertEqual(self.window.findtext("views"), "50")
        self.assertEqual(self.controls["50"].get("type"), "list")
        self.assertIsNone(self.controls["50"].find("content"))
        self.assertIsNone(self.controls["50"].find("onclick"))
        self.assertEqual(self.controls["50"].findtext("pagecontrol"), "50600")

    def test_ids_are_unique_and_navigation_targets_exist(self):
        ids = [node.get("id") for node in self.window.iter("control") if node.get("id")]
        self.assertEqual(len(ids), len(set(ids)))
        for node in self.window.iter("control"):
            for direction in ("onleft", "onright", "onup", "ondown"):
                for target in node.findall(direction):
                    if (target.text or "").isdigit():
                        self.assertIn(target.text, self.controls)

    def test_setup_refresh_help_and_back_have_safe_fixed_actions(self):
        self.assertEqual(self.controls["9401"].findtext("onclick"),
                         "RunPlugin(plugin://plugin.games.apeture/?action=settings)")
        self.assertEqual(self.controls["9402"].findtext("onclick"), "Container.Refresh")
        self.assertEqual(self.controls["9403"].findtext("onclick"),
                         "RunPlugin(plugin://plugin.games.apeture/?action=help)")
        self.assertEqual(self.controls["9400"].findtext("onclick"), "Action(Back)")

    def test_native_menu_source_actions_and_now_playing_are_retained(self):
        includes = [node.text for node in self.window.iter("include")]
        for name in ("MediaMenuCommon", "MediaMenuListCommon", "MediaMenuNowPlaying", "MediaMenuMouseOverlay"):
            self.assertIn(name, includes)
        self.assertEqual(self.window.findtext("menucontrol"), "9000")
        self.assertIn("addons://more/game/", self.controls["621"].findtext("onclick"))
        self.assertIn("Container.PluginName", self.controls["624"].findtext("onclick"))

    def test_no_giant_selected_icon_or_duplicate_breadcrumb_include(self):
        textures = [node.text or "" for node in self.window.iter("texture")]
        self.assertFalse(any("ListItem" in texture for texture in textures))
        includes = [node.text for node in self.window.iter("include")]
        self.assertNotIn("TopBar", includes)
        self.assertNotIn("ListThumbInfoPanel", includes)

    def test_custom_copy_depends_on_real_plugin_state(self):
        labels = [node.text or "" for node in self.window.iter("label")]
        for prop in ("Apeture.Heading", "Apeture.Description", "Apeture.Summary"):
            self.assertTrue(any("Container.Property({})".format(prop) in label for label in labels))
        source = (SKIN / "xml/MyGames.xml").read_text()
        self.assertIn("!String.IsEqual(Container.PluginName,plugin.games.apeture)", source)
        self.assertNotIn("retroarch.exe", source.lower())

    def test_fonts_exist_in_each_shipped_fontset(self):
        used = {node.text for node in self.window.iter("font")}
        for fontset in ET.parse(SKIN / "xml/Font.xml").getroot():
            names = {node.findtext("name") for node in fontset.findall("font")}
            self.assertTrue(used <= names)


if __name__ == "__main__":
    unittest.main()

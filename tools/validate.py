#!/usr/bin/env python3
"""Static packaging/skin sanity checks; not a substitute for running Kodi."""
from pathlib import Path
import ast
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def validate() -> list[str]:
    errors = []
    sources = [ROOT / "addons/plugin.games.apeture", ROOT / "addons/script.apeture.music", ROOT / "build/skin.apeture"]
    for source in sources:
        manifest = source / "addon.xml"
        if not manifest.exists():
            errors.append(f"Missing materialized addon: {manifest.relative_to(ROOT)}")
            continue
        for path in source.rglob("*.xml"):
            try:
                ET.parse(path)
            except ET.ParseError as exc:
                errors.append(f"{path}: {exc}")
        for path in source.rglob("*.py"):
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (SyntaxError, UnicodeError) as exc:
                errors.append(f"{path}: {exc}")
        try:
            addon = ET.parse(manifest).getroot()
            if addon.get("id") != source.name:
                errors.append(f"Addon ID differs from package directory: {source}")
            for asset in addon.findall("extension[@point='xbmc.addon.metadata']/assets/*"):
                if asset.text and not (source / asset.text).is_file():
                    errors.append(f"Missing declared addon asset: {asset.text}")
            for ext in addon.findall("extension"):
                if ext.get("point") in ("xbmc.python.pluginsource", "xbmc.python.script"):
                    library = ext.get("library", "")
                    if not library or not (source / library).is_file():
                        errors.append(f"Missing plugin entry point: {library}")
                elif ext.get("point") == "xbmc.gui.skin":
                    resolutions = ext.findall("res")
                    if not resolutions:
                        errors.append("Skin declares no resolution")
                    for res in resolutions:
                        folder = source / res.get("folder", "")
                        for name in ("Home.xml", "Font.xml", "Includes.xml", "DialogConfirm.xml",
                                     "Settings.xml", "SettingsCategory.xml", "MyVideoNav.xml",
                                     "MyMusicNav.xml", "MyGames.xml"):
                            if not (folder / name).is_file():
                                errors.append(f"Missing complete-skin window: {folder / name}")
                        if (folder / "Home.xml").is_file():
                            home = ET.parse(folder / "Home.xml").getroot()
                            for node in home.iter():
                                if node.tag in ("texture", "texturefocus", "texturenofocus") and node.text and node.text.startswith("apeture/"):
                                    if not (source / "media" / node.text).is_file():
                                        errors.append(f"Missing authored Home texture: {node.text}")
                        if (folder / "Font.xml").is_file():
                            for node in ET.parse(folder / "Font.xml").iter("filename"):
                                if node.text and node.text != "arial.ttf" and not (source / "fonts" / node.text).is_file():
                                    errors.append(f"Missing packaged font: {node.text}")
                    gui = addon.find("requires/import[@addon='xbmc.gui']")
                    if gui is None or gui.get("version") != "5.17.0":
                        errors.append("First slice must target Kodi21/Omega GUI5.17.0")
        except ET.ParseError:
            pass
    return errors


if __name__ == "__main__":
    errors = validate()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)
    print("Static addon checks passed. Kodi runtime and Pi playback are NOT validated.")

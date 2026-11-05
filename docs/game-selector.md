# Artwork-led Games system selector

This candidate replaces the four small generic tiles with a centered horizontal
carousel. Left and Right move through large, distinct illustrations of all 13
supported consoles and handhelds. The selected system stays in the centre,
with neighbouring artwork visible. Its name and cached game count sit below.
Settings, Help, library refresh, background preparation and Back have separate
utility illustrations rather than pretending to be a game console.

## Reference and originality

The requested reference is the Powkiddy X55's artwork-led system selector.
X55 themes vary. The [X55 starter guide](https://retrogamecorps.com/2023/07/05/powkiddy-x55-starter-guide/)
describes the Multi System configuration. The primary
[Art Book Next JELOS theme](https://github.com/anthonycaccese/art-book-next-jelos/blob/main/theme.xml)
defines the horizontal, multiple-artwork carousel used as the interaction
reference. This is an Aperture interpretation, not a claim to reproduce every
X55 theme or that user's exact theme.

All 13 system pictures are original vector illustrations with individually
drawn hardware and controllers, with editable SVG sources and packaged PNGs.
No theme image, commercial game image, system logo or ROM was copied. They are
licensed GPL-3.0-or-later; see `skin/licenses/APERTURE_GAME_ART.md`.
To regenerate the PNGs with an installed official Inkscape:

    python3 tools/build_game_art.py

Kodi does not need Inkscape, Pillow, SVG support or internet access. It loads the
checked-in PNGs, at 640 × 560 each. They use about 2.6 MiB compressed on disk.
The existing game-detail artwork remains untouched by this selector patch.

## Native navigation contract

- Control 59 is a native horizontal `wraplist` with centre focus, not custom
  scripted selection or a static screenshot. Control 60 is still the game list.
- Both retain the `list` view type and are first in the view preference list.
  This preserves Kodi's fallback to the correct view when Back restores a
  directory. Native non-Aperture game views remain available.
- No click or Back handlers override Kodi directory navigation. A guarded
  control-focus action skips the parent tile only when a ready root currently
  selects that tile and its next entry is an actual system. It does not intercept
  Left/Right or change the global parent-folder setting. A restored real-system
  selection does not match the guard.
- System identities and cached counts come from the companion Games add-on.
  `Aperture.Action` distinguishes utility items. Combine with the persistent
  library-cache candidate, not the old add-on that rescans on entry.
- No scan is invoked by the skin. Refresh is a deliberate add-on action.
- No installation refs, default deployment pins, physical device or game data
  are changed by this patch. Only the XML integrity hash changes in install.sh.

## Verification boundaries

Unit tests check the horizontal wraplist, native view fallback contract,
original source/PNG coverage for every system, utility/fallback art, and XML
integrity. The complete skin must also assemble from the official Kodi 21
Estuary source and include every referenced PNG.

`tools/preview_game_selector.py` renders labelled **design previews** from the
final XML coordinates and original PNGs with synthetic library data. These
previews are not Kodi screenshots and cannot certify navigation or hardware.

Native Kodi 21 acceptance must check Left/Right, first/last wrap, selecting a
system, Back from a game list, Stop followed by Back, Settings/Help dismissal,
background preparation and repeated Home → Games entry. Capture both selected
system and return states at the candidate's exact commit. The isolated cloud
runtime's display/socket denial prevents local real-Kodi screenshots here;
use the gaming CI run, not a recreated preview, for that acceptance.
Physical Pi/controller/TV acceptance remains a separate gate.

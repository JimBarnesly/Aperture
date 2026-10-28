# Upstream foundation and reproducible skin build

## Provenance

Apeture 0.1.0 uses the **complete Estuary skin from Kodi 21 Omega**, rather than
pretending a standalone `Home.xml` is an installable skin.

- Official repository: <https://github.com/xbmc/xbmc>
- Branch observed: `Omega`
- Immutable revision: `f8815ee40f49a700c047982d752be4b2a61420e2`
- Subtree: `addons/skin.estuary`
- Git tree identity: `efc84d521908a2999e65718fa443a967941a38c6`
- Pinned source: <https://github.com/xbmc/xbmc/tree/f8815ee40f49a700c047982d752be4b2a61420e2/addons/skin.estuary>
- Attribution: Estuary by phil65 / Team Kodi, with contributors credited upstream.

The foundation supplies settings, media windows, modal dialogs (including the
critical skin keep/revert `DialogConfirm.xml`), keyboard, player OSD, game OSD,
fonts, translations, includes, playlists, color themes and textures. This is not
an attempt to re-create Kodi's runtime in a website. No user settings, sources,
ROMs, BIOS files, emulator binaries or background services are bundled or changed.

## Build contract

`addons/skin.apeture/` contains **text overrides only** and cannot be installed as
is. Git and Python 3 with Pillow are build requirements. From the repository root:

```sh
python tools/vendor_estuary.py --output build/skin.apeture
python tools/vendor_estuary_assets.py --output build/skin.apeture \
  --preview build/apeture-design-preview.png
```

The normal `tools/build.py` entry point combines this with companion packaging.
The vendor uses a depth-one, blob-filtered sparse Git checkout; it never clones
all XBMC history. It verifies both the immutable commit and Estuary tree identity
and rejects a dirty upstream cache. Export comes from Git archive objects, not
from the working directory, so ignored or untracked cache files cannot ship. The cache is `build/upstream/xbmc-omega`, or
an explicit `--cache` path. Once populated, the same cache supports offline
rebuilds. For a fresh offline machine, carry the complete cache or built ZIP.
The package includes an `APETURE_BUILD.json` provenance manifest.

Every upstream skin window and include is retained; Home, Font and
SkinSettings have the explicit overrides described below. Source-only Home overrides are overlaid on
that complete tree. Original procedural art is then generated from source; no
opaque source binaries need to be committed. Runtime textures are ordinary PNGs,
so Kodi TexturePacker is not required. Upstream add-on icon, fanart, screenshots
and release metadata are removed/replaced: none are represented as Apeture's UI.

## Changes and behavior

- `addon.xml`: new `skin.apeture` identity, version `0.1.0`, Kodi GUI `5.17.0`,
  original description and assets, 1920×1080 / 16:9 design space.
- `xml/Home.xml`: original luminous midnight home; Games, Movies, TV, Music,
  Files and Settings. A six-item up/down focus ring wraps; right reaches each
  section's contextual action; left reaches the utility row. Every visible
  button has a real Kodi action, including Power, Favourites and Playback.
- Games opens `ActivateWindow(Games,plugin://plugin.games.apeture/,return)`,
  explicitly using Kodi's game window, not Programs or an external process.
  When the add-on is absent/disabled, a real modal explains installation and
  offers Add-ons without automatically installing or enabling anything.
- Movies and TV route to their respective native libraries, or video sources
  if empty. Music opens native albums or music files if empty. Empty-state copy
  reflects real Kodi library conditions; no fabricated collections or counts.
- `xml/Font.xml`: retains both upstream fontsets and adds named Apeture roles.
  The optional Arial fallback is Kodi's system `arial.ttf`, as in Estuary; it is
  not redistributed. Default font files and their upstream notices are bundled.
- `colors/defaults.xml`: a restrained midnight/cyan default palette. Other
  inherited color choices remain available; new Home uses fixed identity colors.
- `xml/Custom_1190_GamesSetup.xml`: original companion installation dialog.
- `media/apeture/*` plus add-on icon/fanart: original procedural artwork from
  `tools/vendor_estuary_assets.py`. Fanart is artwork, not a runtime screenshot.
- `xml/SkinSettings.xml`: removes the inherited Home-widget/menu customization
  panel, which does not apply to Apeture's fixed Home. A note makes that boundary
  explicit. Other skin options and all actual Kodi settings remain available.
- Non-Home browsing and playback windows retain Estuary's existing design and
  behavior in this foundation release. A broader Apeture restyle remains future
  work; this release does not pretend those windows are newly designed.

Music's future Format-inspired direction is an album-cover shelf that opens at
a random album, giving the feeling of reaching into a record collection. That
interaction is **not implemented** in 0.1.0; Music currently means native Kodi
music browsing. The game integration shares the libretro ecosystem with
RetroArch but does not embed the RetroArch frontend or launch its executable.

## License boundaries

The upstream skin's `LICENSE.txt` is preserved verbatim. It states **GPL version
2 for Estuary code** and **Creative Commons Attribution-ShareAlike 4.0 for Estuary
artwork**. We do not silently reinterpret the skin's specific GPLv2 statement as
GPLv3. Modified inherited Font/color/SkinSettings files retain the upstream license. New
Apeture skin XML is offered as GPL-2.0-or-later so the skin can be distributed
alongside its inherited GPLv2 foundation. Original Apeture artwork is CC-BY-SA
4.0. Build scripts are original GPL-3.0-or-later code under the root license.

Full `GPL-2.0-only` and `GPL-2.0-or-later` license texts are always read directly
from pinned Git objects and included in `licenses/`, independent of sparse
checkout contents.
Upstream `fonts/noto_license.txt`, `fonts/roboto_license.txt`,
`fonts/heebo_licence.txt`, and `fonts/mardoto_license.txt` are retained unmodified.
Font licenses apply to their font files, not to Apeture's code. Please retain
all these notices when redistributing. This document is provenance, not legal
advice; the package deliberately preserves the original license statements.

## Verification and limitations

Static verification parses all XML, checks the assembled window foundation,
checks authored navigation, assets and font references, and produces a design
preview from the Home control geometry and actual fonts/textures. The preview
has a permanent **DESIGN PREVIEW — not a Kodi runtime screenshot** label.
The optional preview renderer also uses `fonttools` to disable TrueType hinting
in an in-memory font copy: Pillow otherwise mis-renders the merged upstream
Noto font. Kodi uses `FT_LOAD_TARGET_LIGHT`; the preview uses the same outlines
without bytecode hints. Distributed font files are unchanged. The static clock
in a design preview is illustrative; runtime uses Kodi's real time/date labels.

The renderer is not Kodi: focus/remote behavior, skin confirmation/reversion,
playback, game client installation, CEC and display scaling must still be tested
in Kodi 21 on the target hardware. No Kodi runtime is assumed available in the
build container. 1080p is the authored coordinate space; Kodi performs display
scaling (including 720p and 4K), which needs device validation. This version does
not claim non-16:9 layout support or a fully restyled Estuary browsing experience.

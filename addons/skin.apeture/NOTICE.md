# Apeture skin notices

This directory is **authored source overrides**, not an installable partial skin.
Build using `python tools/build.py` at the repository root. The resulting package
includes the complete pinned Kodi 21 Omega Estuary skin; it does not rely on Kodi
falling back to another installed skin for missing windows.

The upstream `LICENSE.txt`, included unchanged in the built package, attributes
Estuary to phil65 / Team Kodi and licenses its code under GPL version 2 and its
artwork under CC BY-SA 4.0. The original font license files remain in `fonts/`.
`Font.xml`, `SkinSettings.xml` and `colors/defaults.xml` are modified Estuary files and retain that
upstream GPL version 2 license. The original Apeture `Home.xml`, addon metadata
and companion setup dialog are additionally offered under GPL-2.0-or-later to
remain compatible with the skin foundation. Original Apeture art is CC-BY-SA-4.0.
Build and asset-generator Python code is GPL-3.0-or-later under the root license.
The root project's license does not replace third-party licenses.

See `UPSTREAM.md` in the package and `docs/UPSTREAM.md` in the repository for the
pinned revision, exact build process, retained notices and modifications.

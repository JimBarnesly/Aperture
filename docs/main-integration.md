# Comprehensive main integration

This candidate preserves main history and consolidates the current `skin.aperture`
architecture. It is not a deployment, a stable hardware-certified release, or a
fix for the unresolved physical Pi blackout.

## Included source lines

- PR5 `88414c5`: complete Kodi 21 skin, Format library/download controls, local
  Movies, gaming setup, source-preserving installers and baseline tests.
- PR9 `3ef534f` and PR7 `6bb2a7d`, combined by PR10 `425400e`: saved Games library,
  artwork carousel, native music turntable, normal Exit and preservation tests.
- PR6 `8484144`: safe local poster choices. Online missing-poster retrieval is
  not implemented.
- PR8 `ca34b5c`: notification lifecycle coverage, not a CEC change or fix.
- PR11–14 through `3102440`: retained opt-in Labwc diagnostics. Their historical
  failed first-log churn results remain failures, separate from the successful
  Home-aligned companion; none reproduces or clears the physical blackout.
- PR15 `c9a723f`: conservative source identity/removal guard and adversarial
  saved-list confirmation tests. No game files are deleted by clearing a list.

- PR16 `136b385`: playback-aware Home shortcut with remote focus, exact Music/TV/
  Movies destinations and escape after playback stops. Author native menu CI
  passed before integration.

Main remains unchanged until this final combined candidate passes.

## Retained alternatives

PR1–4 (`cc224e7`, `84e3951`, `4e95d00`, `922c1ce`) represent the historical
`skin.apeture` foundation/scenic/local-music/release line. They are not additive
features for the newer `skin.aperture` architecture. Blind merging would restore
obsolete entrypoints, duplicate music ownership and conflicting build recipes.
Their standalone Kodi album shelf (without a Format server), alternative scenic
Home and Windows ZIP preparation aid remain available on their historical line,
not in this candidate. Their branches remain intact; no branch is deleted.

## Gates and boundaries

All final-source unit tests, syntax, package assembly and native startup/Format/
ZIP, Games ARM64+x86 with both skins, Movies and menu acceptance must pass at the
same final head. Experimental casting remains separate and is never installed
by skin integration. Native synthetic software-rendered CI does not certify
physical Pi boot/relaunch, V3D, HDMI/CEC, controllers, drive disconnect or audible
output. No Pi, media drive, deployment pins or backend configuration is modified.

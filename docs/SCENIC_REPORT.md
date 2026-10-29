# Scenic experiment 0.2.0

Historical scenic experiment report (0.2.0), retained for design context.
For current 1.0 RC1 scope and evidence, see [BUILD_REPORT.md](BUILD_REPORT.md).
Version and verification statements below describe this earlier slice only.

## Changes

- Original misty stone-bridge artwork, with a quiet horizontal lower-third menu.
- Native routes, honest empty states, section actions and utilities retained.
- The six categories wrap left/right. Up reaches the section action; Down reaches
  utilities. All 15 focusable Home controls are statically reachable.
- The full pinned Estuary foundation and its license/font notices remain.
- Original artwork is included in the source and package, with provenance in
  DESIGN.md. It is not the exact historical image remembered by the user.

## Validation boundary

45 unit/static contract tests passed before publication. Materialized XML,
fonts/assets and package checks passed. The Games and Music images were visually
reviewed as labelled layout previews, not runtime screenshots.

The new opt-in CI GUI workflow must actually complete before any GUI pass is
claimed. It tests an ephemeral Kodi 21 installation with a private software
display and test observer. It never uses personal media or profiles and does not
enable Kodi's remote-control servers. Captures, state history and logs record
what happened. A successful result still excludes ZIP installation/skin rollback,
Pi hardware, physical controller, real media playback and emulator-core support.

No changes to main or deployment to a device are implied by this experiment.

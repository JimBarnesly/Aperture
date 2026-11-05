# Integrated Games and native turntable candidate

This candidate combines the tested Games/selector source at
`3ef534f917d49614e35f5cf5dcee9a518dcba087` with the native music presentation and
normal Exit/relaunch coverage at `6bb2a7dcdace40695f5bc4db0dd5a641774dde58`.
It is a separate candidate, not deployment permission or a black-display fix.

The Games add-on, cache service, selector XML and Games artwork remain byte-for-
byte unchanged from the Games pin. The integrated skin includes both that
selector and MusicVisualisation; Format client 0.4.0 supplies guarded explicit
album-play entry. The Format server and Movies client are unchanged.

## Coordinated update scope

Do not install the old standalone turntable branch over the newer Games skin.
Wait until the relaunch rendering issue is understood and the device owner has
coordinated any required interruption. Do not run overlapping update sessions.
Use a separate checkout of the exact tested integrated commit.

With Kodi already stopped under the separately approved coordination, only the
existing skin installer (`sh install.sh`) and Format-client installer
(`sh install-format.sh`) are needed. Run as the Kodi desktop user. Each stages
and validates its own replacement and retains its previous code in the profile's
backup directory. Do not rerun the Games/emulator installer or its add-on updater.
Do not erase or refresh the saved Games library for this update.

Both installers preserve Games code, configured ROM roots, cached library and
scan-attempt records, cores, saves, media sources, Format endpoint settings and
the Movies client. Regression tests perform both installs against a disposable
profile and compare those bytes, the resulting selector/artwork, and both music
windows. Rollback restores only the prior skin and Format-client code while Kodi
is stopped; keep the current Games code and all profile data intact.

## Evidence and remaining gates

The integrated head must pass the full startup/Format/fresh-ZIP suite, all four
ARM64/x86 and Aperture/Estuary Games jobs, native menu checks and Movies checks.
Read the exact-head run results, not a successful result from either parent pin.

Those suites use disposable synthetic media and software rendering. They do not
establish physical Pi Wayland/Labwc rendering, visible output, controller/audio
behavior, real-library reuse or a fix for the intermittent dark relaunch frame.
Do not change display, CEC, backend, permissions or operating-system packages as
part of this candidate. Preserve diagnostic evidence and those separate gates.

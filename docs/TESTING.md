# Testing and acceptance

Automated checks are necessary, but XML parsing is not a Kodi render test.

## Automated

Run the repository's validation, Python unit tests and package build. Check ZIP
root names against their add-on identifiers, reject path traversal and omit caches.
Generated upstream dependencies must come from pinned official source revisions.

## Pi 5 / Kodi 21 smoke test (not performed in the build container)

1. Back up Kodi's profile. Keep the existing default skin installed.
2. Install the companion game-library ZIP, then the skin ZIP. Accept the skin
   change only if the keep/revert confirmation is visible and usable.
3. Navigate every Home destination using only a keyboard/remote/controller.
   Repeat left/right/up/down, Back and select; no invisible focus or trapped paths.
   Repeat on the real game controller and HDMI-CEC TV remote. Check D-pad/arrows,
   OK/select and Back, including held/repeated inputs. Keyboard CI does not prove
   physical controller mapping or a particular television's CEC behaviour.
4. Open and close Settings, file browser, source setup, keyboard and yes/no dialogs.
   Confirm changing back to the previous skin works.
5. Check no-library and populated-library Music, Movies and TV states.
6. Configure a test ROM directory containing empty, supported, unsupported and
   nested system folders. Only supported populated systems should be listed.
7. Test a legally held compatible game with the corresponding Kodi game add-on.
   Check missing-core/cancel paths, then stop gameplay and return to the library.
8. Play video and music; inspect fullscreen OSD, subtitles, volume, pause/stop and
   return navigation. Check 720p/1080p scaling and the actual TV's overscan settings.
9. Restart Kodi and repeat entry/exit. Confirm scan failures never modify files.

Record the OS, Kodi version, controller, cores, tested games and observed results.
Do not mark this checklist passed from desktop mock-ups, XML checks or unit tests.

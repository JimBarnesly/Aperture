# Verification and recovery

## Automated layers

- Unit tests: manifest/GUI contract, complete fonts, focus graph, deterministic
  packaging, safe installer swap/rollback, missing downloads/resources, settings
  preservation, Format metadata/IDs/order/failure handling.
- Installer font regression: disposable profiles reproduce a broken Estuary
  Roboto-Thin link with the font under the Pi OS RobotoTTF layout. Tests verify
  exact-name resolution, rejection of missing/empty/ambiguous matches, source and
  profile-setting preservation, cleanup, rollback, and Python-free intact links.
  These filesystem fixtures are not tests on a physical Raspberry Pi.
- Real GUI: official Kodi 21.3, isolated fresh profile, accepted Aperture switch,
  repeated native navigation, cancel/back, recovery to Estuary, timeout rollback.
- Fresh ZIP GUI acceptance: a second empty profile installs exactly the three
  packages produced by `tools/build_skin.py`: Format, Movies, then the complete
  skin. Each is selected through Kodi's native ZIP installer, observed enabled
  at its expected user add-on path/version, and checked byte-for-byte against its
  SHA256-verified archive. Missing, duplicate, unexpected and unlisted stale ZIPs
  are rejected. All three add-ons must remain enabled at the same paths/versions
  after restart and accepted Estuary recovery. Unknown sources is restored off.
  The installed Home exercises direct Format Music entry and Movies' no-source setup
  guidance with dismissal, Back and reopening. No real video source is added.
  The optional Games add-on is not produced by this build and remains covered by
  its separate gaming acceptance, not the fresh ZIP phase.
- Format GUI fixture: synthetic original tones, artwork and mock acquisition
  state on loopback only. Covers native album/list views, artists/search,
  catalogue preview, declined/confirmed actions, independent protected-mode
  capabilities, permission revocation while confirming, missing/malformed/failed
  health, queue-only controls, ordered playback and offline recovery. Fullscreen
  music checks clean startup/track-change frames while Kodi's automatic info
  flag is active, native Left/Right seeks, pause, Up/Down navigation, retained
  manual OSD actions, caption order and no metadata popup throughout. Skin switches
  verify the owned fullscreen-only keymap loads/removes without changing others. Exactly
  three permitted mock POSTs are required; navigation and cancelled actions
  must not replay writes.
  This fixture is not a replacement for anyone's library or proof of access to
  their Format server. Clocked discard audio is not an audible-output test.

The latest run's `result.json`, package hashes, `kodi-version.txt`, screenshots and
full Kodi logs must all correspond to the same commit. A failed or incomplete
run is not a pass. Review actual screenshots, not only observer state.

## Pi acceptance still required

1. Record OS, Kodi version and installed add-on versions.
2. Check Estuary starts and plays an owned test track.
3. Install complete candidate ZIPs, enable them in My add-ons, select Aperture,
   verify Keep/revert and restart persistence.
4. Verify every Home destination and Back; Settings must remain reachable.
5. Test the actual controller and LG HDMI-CEC separately. Keyboard simulation
   does not prove physical input compatibility.
6. Confirm the real Format server address is reachable from the Pi; open an album,
   play its full queue and test pause, next, previous, Back and reopening.
7. Verify audible output and real video playback with the intended TV/audio path.
8. Switch back to Estuary and back to Aperture. Stop at the first failure.

No emulator/core/gameplay, receiver-service or OS-migration claim follows from a
skin pass. Those are separate acceptance tests.

## Recovery

If the skin works enough to navigate, use Settings > Interface > Skin > Estuary.
If the Keep/revert dialog is visible but unusable, wait for automatic rollback.

If Kodi cannot reach its UI, first stop Kodi using the normal OS-specific method.
Back up `userdata/guisettings.xml`, then change only the `lookandfeel.skin` setting
to `skin.estuary`. Start Kodi again. Do not edit a running profile or delete the
add-on database to force enablement. On Raspberry Pi OS the profile is normally
`~/.kodi`; on LibreELEC it is `/storage/.kodi`.

A complete `kodi.log` from a failed start is needed for a reliable diagnosis.
Redact passwords, tokens, remote URLs containing credentials and private paths
before sharing logs publicly. A DBus/UPower warning alone does not establish why
skin activation froze.

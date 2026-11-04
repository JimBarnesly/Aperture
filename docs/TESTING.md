# Verification and recovery

## Automated layers

- Unit tests: manifest/GUI contract, complete fonts, focus graph, deterministic
  packaging, safe installer swap/rollback, missing downloads/resources, settings
  preservation, Format metadata/IDs/order/failure handling.
- Real GUI: official Kodi 21.3, isolated fresh profile, accepted Aperture switch,
  repeated native navigation, cancel/back, recovery to Estuary, timeout rollback.
- Format GUI fixture: synthetic original tones and artwork on loopback only.
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

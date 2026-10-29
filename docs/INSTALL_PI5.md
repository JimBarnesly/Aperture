# First Pi 5 install

Aperture 1.0 RC1, prepared 29 October 2026. Not a stable/hardware-accepted release.
Use a test card/profile first; keep the original skin.

## Optional Windows preparation

The extracted test kit includes `installer/Prepare-Aperture.ps1` and
`installer/README.md`. Read that README before running the script on a computer
you are authorised to use. It verifies and stages the three ZIPs, optionally onto
a separately identified USB data stick. It does not image the SD, configure Kodi,
install add-ons or bypass work-machine policy. Windows/USB runtime validation is
not yet established; Linux static checks are not hardware evidence. The following
imaging and on-Pi actions remain manual, not one-click provisioning.

## 1. Write the system image

1. Back up anything needed from the microSD card. **Writing an image erases the
   entire selected device.** Check the card's name and capacity before writing.
2. From [LibreELEC's official Raspberry Pi page](https://libreelec.tv/downloads/raspberry/),
   choose the **Raspberry Pi 5** stable image. The image recorded during 28 October preparation was
   `LibreELEC-RPi5.aarch64-12.2.1.img.gz`, containing Kodi **21.3 Omega**.
   Do not choose Pi 4, Generic PC, nightly or an update-only download.
3. Open [Raspberry Pi Imager](https://www.raspberrypi.com/software/) on a computer
   you are allowed to use. Select Pi 5, **Use Custom** for the downloaded image,
   then the correct microSD card. Write, allow verification to finish, and eject.
   Formatting the card and copying the image file onto it is not sufficient.
4. If the work laptop requests administrator rights or blocks the writer, use
   the employer-approved route or another permitted computer. Do not bypass it.
5. With the Pi powered off, insert the card and connect its display/input devices.
   Boot and finish LibreELEC's first-run setup. LibreELEC already includes Kodi.

[Official image-writing instructions](https://www.raspberrypi.com/documentation/computers/getting-started.html#install-using-imager).

## 2. Try Aperture

1. Confirm the stock Kodi interface works and reports Kodi 21.x. Back up the new
   profile before experimenting. Keep Estuary installed for recovery.
2. If the download is an outer kit/GitHub artifact ZIP, extract that wrapper on
   your computer first. Transfer the **three inner add-on ZIPs** to storage Kodi
   can browse, such as a USB drive; leave those inner ZIPs zipped. This release-candidate
   kit contains:
   - `plugin.games.apeture-1.0.0~rc1.zip` — optional game library.
   - `script.apeture.music-1.0.0~rc1.zip` — optional native album shelf.
   - `skin.apeture-1.0.0~rc1.zip` — complete skin, installed/selected last.

   In **Add-ons → Add-on browser → Install from ZIP file**, install each desired
   companion, wait for its notification, then install the skin. Neither companion
   is a hard dependency of the skin: missing Music helper falls back to Kodi
   Music; missing Games helper shows setup guidance. If a companion is disabled,
   review it under **Add-ons → My add-ons** before expecting its Home integration.
3. Kodi may ask you to review its Unknown sources setting for ZIP installation.
   Decide on that warning yourself after reviewing the package/source. Aperture
   does not enable it automatically.
4. Select **Settings → Interface → Skin → Aperture**. Confirm the change only if
   the screen is readable and controls respond. If not, let Kodi's timer revert.
5. Test all six Home destinations and Back. Start at a readable 16:9 display mode
   (1080p is the authored layout). Verify the actual controller or TV remote/CEC
   independently; desktop keyboard tests do not establish either one.

The ZIPs already contain their code, required skin windows and default fonts.
Kodi 21 supplies their `xbmc.python` and `xbmc.gui` APIs. Do **not** install Python,
Node/npm, run a Format server, enable SSH, or copy build directories merely to
install this kit. The GitHub source ZIP and `addons/skin.apeture` source folder
are not installable skin packages. Keep `checksums.json` with the matching ZIPs.

## 3. Populate your own library

**Music:** from the shelf select **Kodi Music**, then **Files → Add music**.
Choose a folder containing correctly tagged music and agree to scan the source
into Kodi's library. Wait for the scan to finish, then reopen or Refresh the
shelf. Adding a file-browser source without scanning does not populate albums.
Additional online metadata/art scraping is optional, not a shelf requirement;
Kodi's guide recommends leaving it off for the first scan. Aperture does not turn
it on. [Official scanning guide](https://kodi.wiki/view/Adding_music_to_the_library).

The shelf uses album tags already indexed by Kodi. Missing/unreadable or remote
artwork may show its original record placeholder. **Play album replaces the
current music queue and disables shuffle** for disc/track order. Cue/shared-file
albums remain playable through native Kodi Music, not this first shelf slice.

**Games:** configure a ROM root containing supported system subfolders, not an
individual game file. The companion's bundled README describes folder names.
Configure a root only when ready; unconfigured/empty states should show guidance,
not invented games. Add movie/TV sources through Kodi separately.

Game/emulator cores, BIOS requirements and controller mapping are separate from
the skin. A detected game file does not guarantee a compatible Pi core exists.

## Acceptance

Desktop native ZIP installation, accepted skin selection, restart persistence and
Estuary recovery passed on commit `296711243206a822caba7997b229a0c885a57384` in
[run 40801720239](https://github.com/JimBarnesly/Apeture/actions/runs/40801720239).
That is not Windows preparation, SD imaging or Pi hardware acceptance. The kit
remains guided preparation, not a fully provisioned SD image. Check
remote/controller focus, TV scaling, skin rollback and actual media playback.
If something fails, record the Kodi version, screen/action and log excerpt.
Use [TESTING.md](TESTING.md) for the complete checklist.

[Kodi ZIP-install instructions](https://kodi.wiki/view/Add-on_manager#How_to_install_from_a_ZIP_file)
and [game add-ons](https://kodi.wiki/view/Game_add-ons).

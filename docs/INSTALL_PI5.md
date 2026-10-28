# First Pi 5 install

Checked 28 October 2026. Use a test card/profile first; keep the original skin.

## 1. Write the system image

1. Back up anything needed from the microSD card. **Writing an image erases the
   entire selected device.** Check the card's name and capacity before writing.
2. From [LibreELEC's official Raspberry Pi page](https://libreelec.tv/downloads/raspberry/),
   choose the **Raspberry Pi 5** stable image. The verified current file is
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

## 2. Try Apeture

1. Confirm the stock Kodi interface works and reports Kodi 21.x. Back up the new
   profile before experimenting. Keep Estuary installed for recovery.
2. Transfer the supplied add-on ZIP files to storage Kodi can browse. Leave them
   zipped. In **Add-ons → Add-on browser → Install from ZIP file**, install the
   game-library ZIP first. For the music-shelf build, also install its script ZIP.
   Install the selected skin ZIP last.
3. Kodi may ask you to review its Unknown sources setting for ZIP installation.
   Decide on that warning yourself after reviewing the package/source. Apeture
   does not enable it automatically.
4. Select **Settings → Interface → Skin → Apeture**. Confirm the change only if
   the screen is readable and controls respond. If not, let Kodi's timer revert.
5. Test all six Home destinations and Back. Configure a ROM root only when ready;
   add music/video sources through Kodi. Missing libraries should show setup
   guidance rather than invented content.

Game/emulator cores, BIOS requirements and controller mapping are separate from
the skin. A detected game file does not guarantee a compatible Pi core exists.

## Acceptance

Desktop Kodi GUI checks are evidence, not a substitute for this Pi test. Check
remote/controller focus, TV scaling, skin rollback and actual media playback.
If something fails, record the Kodi version, screen/action and log excerpt.
Use [TESTING.md](TESTING.md) for the complete checklist.

[Kodi ZIP-install instructions](https://kodi.wiki/view/Add-on_manager#How_to_install_from_a_ZIP_file)
and [game add-ons](https://kodi.wiki/view/Game_add-ons).

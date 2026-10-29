# Aperture — guided Windows SD-card preparation

This helper **verifies and stages the three add-on ZIPs**. It does not promise a
fully configured card: the official imaging application writes LibreELEC, then
Kodi installs the add-ons on the Pi. Internal add-on IDs retain `apeture` for
upgrade compatibility. No programming tools are needed on the Pi.

## Before starting

- A Windows 10/11 PC on which you are authorised to run PowerShell and an official
  disk imager. Ask IT if work-machine policies block either. **Do not bypass
  execution policy, SmartScreen or administrator requirements.**
- Your Pi 5 microSD card and reader, backed up. Imaging erases **all partitions**
  on the selected device. Disconnect unrelated external disks before imaging.
- A **separate USB data stick** for the add-ons. The script will not place files
  on an identified LibreELEC boot volume or write its Linux storage partition.
- A trusted, extracted Aperture release kit containing `checksums.json` and its
  three matching ZIPs. Keep the inner ZIPs zipped. Checksums detect corruption;
  they do not authenticate an untrusted kit whose manifest was also replaced.

The extracted kit can contain `installer/` beside the ZIPs; from a source
checkout, pass `-KitPath .\dist` after building the release.

## 1. Prepare now, even before collecting the card

Open ordinary PowerShell in the extracted kit directory (no elevation needed
for the local-copy operation):

```powershell
.\installer\Prepare-Aperture.ps1 -OpenOfficialDownloads
```

Default output is `Documents\Aperture-ready`. To choose another fresh folder on the Windows system drive:

```powershell
.\installer\Prepare-Aperture.ps1 -KitPath C:\Users\You\Downloads\Aperture-kit -OutputPath C:\Users\You\Downloads\Aperture-ready
```

The helper verifies the manifest, names, sizes and SHA-256 hashes before copying.
It preflights the entire destination, skips identical files and refuses conflicting
files, unexpected files or leftover versions before copying anything. It also copies
these instructions as `INSTALL-WINDOWS.md` beside the ZIPs. `-OutputPath` is
restricted to a positively identified internal Windows system drive; use
`-UsbDriveLetter` for removable storage.
If a copy is interrupted, choose a fresh output folder rather than installing a
partial ZIP. No network download, service, credential, security-setting change,
format or raw disk write occurs. `-OpenOfficialDownloads` only opens two official
web pages in your browser. Inspect the script before running it.

## 2. Write LibreELEC to the microSD — manual, destructive confirmation

1. Obtain `LibreELEC-RPi5.aarch64-12.2.1.img.gz` from the
   [official Raspberry Pi downloads](https://libreelec.tv/downloads/raspberry/).
   This pinned version contains Kodi **21.3 Omega**. Do not substitute Pi 4,
   nightly or Generic. The helper deliberately does not download an unpinned
   image or executable. Review the download's official SHA-256 via its
   `?mirrorlist` link and compare the downloaded file using:
   `Get-FileHash -Algorithm SHA256 -LiteralPath 'path-to-image.img.gz'`.
2. Obtain [Raspberry Pi Imager](https://www.raspberrypi.com/software/) from its
   official site, or use LibreELEC's official USB-SD Creator. Do not grant access
   to a work computer unless permitted. If blocked, use an approved computer.
3. Open the official writer. Select Pi 5 where offered, then **Use Custom** /
   **Select file**, and choose the exact downloaded `.img.gz`. Do not apply
   Raspberry Pi OS customisation settings to LibreELEC.
4. Select the microSD **by matching its identity and capacity**. If uncertain,
   cancel, remove/reinsert it and compare the device list. Never choose the PC's
   system disk; never proceed with an ambiguous target. The helper deliberately
   does not choose a disk or automate the writer's erase confirmation.
5. Backups checked? Confirm **Write** in the official application only now.
   Wait for completion/verification, safely eject, and decline any subsequent
   Windows request to format an unrecognised partition.

Copying the `.img.gz` onto a formatted card is **not** imaging. Do not copy the
add-ons to the card before imaging: imaging would erase them.

## 3. Put the ZIPs on the separate USB data stick

Either manually copy the prepared `Aperture-ready` folder to the USB data stick,
or inspect disks and explicitly copy with the helper (replace **E** with the
verified USB data-volume drive letter, not the microSD):

```powershell
.\installer\Prepare-Aperture.ps1 -ShowDisks
.\installer\Prepare-Aperture.ps1 -UsbDriveLetter E
```

It displays the physical disk identity and requires `COPY E`. It refuses
system/boot disks, unknown/internal buses, unsupported filesystems, ambiguous
mappings and boot-volume markers. This is **file copying, not erasing**. Never
remove/swap media during copying. If Windows cannot provide the disk identity,
it stops rather than guessing; use an approved PC or copy manually after
checking the destination yourself. Safely eject when finished.

## 4. Finish on the Pi (these steps remain manual)

1. With the Pi powered off, insert its microSD, connect display/input and boot.
   Allow initial setup/storage preparation to finish without interrupting power;
   complete LibreELEC's wizard. Prefer Ethernet initially; enter Wi-Fi credentials
   yourself if needed. Do not enable SSH/SMB just for this installation.
2. Confirm stock Kodi works. Insert the USB data stick. In **Add-ons → Add-on
   browser → Install from zip file**, browse `Aperture-ready` on that stick.
3. Review Kodi's Unknown sources warning yourself if shown. The helper does not
   enable it or bypass add-on checks. Install `plugin.games.apeture-<version>.zip`,
   then `script.apeture.music-<version>.zip`, then `skin.apeture-<version>.zip`.
   Wait for each install notification. Use the matching filenames in your kit.
4. Select Aperture in **Settings → Interface → Skin**. Accept the keep/revert
   dialog only if readable and responsive; otherwise let it revert to Estuary.
5. Add/scan your own music and video sources. Configure the games add-on's ROM
   root and install compatible official Kodi game add-ons separately. No games,
   BIOS, emulator cores, accounts or media libraries are supplied/configured.
6. Check controller/CEC, audio, navigation and playback on the actual Pi. Keep
   Estuary available and back up your profile before further experimentation.

## Why not a one-click first-boot installer?

LibreELEC documents `autostart.sh` in `/storage/.config`, not the Windows-visible
boot partition. This helper has no verified supported Windows-only way to inject
and execute that hook on a fresh image. It does not write ext4, alter image boot
scripts, silently install add-ons, or claim that placing ZIPs on FAT installs them.
There is no unattended first-boot implementation in this kit.

## Verification and sources

Prepared 29 October 2026. Static safety tests run in the Linux build workspace.
**Windows PowerShell execution, physical imaging, USB detection and Pi first boot
have not been tested here.** The script is an auditable preparation aid, not a
hardware acceptance result. Versioned add-ons remain release-candidate software.

- [LibreELEC 12.2.1 / Kodi 21.3 announcement](https://libreelec.tv/2025/11/03/libreelec-omega-12-2-1/)
- [LibreELEC official media creation and erase warning](https://wiki.libreelec.tv/installation/create-media)
- [LibreELEC startup hook location](https://wiki.libreelec.tv/configuration/startup-shutdown)
- [Kodi ZIP installation](https://kodi.wiki/view/Add-on_manager#How_to_install_from_a_ZIP_file)

Run source-level regression checks with:
`python -m unittest discover -s tests -p test_installer.py -v`.
These checks do not substitute for a native PowerShell parser or Windows testing.

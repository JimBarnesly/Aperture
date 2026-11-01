# Aperture

Kodi-first TV interface for Raspberry Pi 5, with native Kodi RetroPlayer and integration with [Format](https://github.com/JimBarnesly/Format).

## Status

**Development prototype — not hardware-tested.** The initial skin froze during activation on LibreELEC/Kodi 21.3. A simplified Home.xml and revised installer have been committed, but must be tested on Kodi before treating them as stable.

## Install skin

On LibreELEC (root SSH) or Raspberry Pi OS (SSH as the Kodi desktop user):

```sh
wget -O /tmp/aperture-install.sh https://raw.githubusercontent.com/JimBarnesly/Aperture/main/install.sh
sh /tmp/aperture-install.sh
```

Activate through Kodi's add-on manager and Settings > Interface > Skin. Estuary remains installed. The installer keeps a previous Aperture backup.

## Format Kodi integration

Format is a separate Node.js music server. It exposes `GET /api/library`, `GET /api/cover?id=...`, and `GET /api/audio?id=...`. The initial read-only Kodi client displays Format albums and tracks and passes streaming URLs to Kodi's player.

```sh
wget -O /tmp/aperture-format.sh https://raw.githubusercontent.com/JimBarnesly/Aperture/main/install-format.sh
sh /tmp/aperture-format.sh
```

In Kodi, configure **Format for Aperture** with the reachable Format server URL (default `http://192.168.68.60:4534` is only an example from the original Format deployment). The Format service must be running on a computer/server reachable by the Pi. It is not automatically installed on the Pi.

**Limitations:** Kodi-native music views are used for now, not Format's original web cover-flow UI. Library browsing and playback still need on-device testing. No automatic discovery or remote server provisioning. Kodi skin and Format add-on are independently installable.

## Planned work

1. Confirm Kodi 21.3 skin activation and navigation without hanging.
2. Verify Format library and playback against the actual server.
3. Recreate Format's album-first browsing with a controller-oriented view.
4. Integrate native RetroPlayer game library and system auto-detection.
5. Add audio/video receiver services under Raspberry Pi OS.

## Recovery

Switch to Estuary in Kodi. On LibreELEC, if Kodi hangs:

```sh
systemctl stop kodi
sed -i 's/skin.aperture/skin.estuary/g' /storage/.kodi/userdata/guisettings.xml
systemctl start kodi
```

Estuary's files are copied locally from the installed Kodi distribution. The repository contains Aperture-specific source and installation scripts.

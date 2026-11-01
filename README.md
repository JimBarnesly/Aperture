# Aperture

A unified TV-first Kodi skin for Raspberry Pi 5 and LibreELEC, inspired by classic XBMC, early-2000s media centres and restrained Wii-era gloss.

## Current state — 0.1.0 prototype

This is an **early installable home-screen prototype**, not the completed reference design. It reuses the locally installed Estuary skin for all secondary screens and replaces its home window with an Aperture navigation screen. The Games entry opens Kodi's native Games window; no ROM scanner, console carousel or emulator cores are bundled yet. Real-Debrid, AirPlay and Format are not integrated.

## Install on LibreELEC

Enable SSH in LibreELEC settings. SSH into the Pi, then run:

```sh
wget -O /storage/aperture-install.sh https://raw.githubusercontent.com/JimBarnesly/Aperture/main/install.sh
cat /storage/aperture-install.sh
sh /storage/aperture-install.sh
```

Then in Kodi open **Settings → Interface → Skin → Aperture**. Keep Estuary installed as a fallback.

The installer copies the Estuary skin already installed on the Pi, changes its add-on ID and overlays the new Home.xml. It backs up any prior Aperture install as `skin.aperture.previous`. Requires a LibreELEC build with Estuary under `/usr/share/kodi/addons/skin.estuary`. Requires network access to GitHub.

## Recovery

If the interface becomes unusable, SSH into the Pi and run:

```sh
sed -i 's/skin.aperture/skin.estuary/g' /storage/.kodi/userdata/guisettings.xml
systemctl restart kodi
```

## Roadmap

- Native game library and system detection
- Artwork and polished controller navigation
- Music/Format integration
- Receiver services and session management

GPL-compatible Estuary source is copied **locally from your installed Kodi distribution**; this repository only holds Aperture-specific changes and installation logic.

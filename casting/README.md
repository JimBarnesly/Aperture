# Aperture YouTube Music receiver: experimental, not yet Pi-verified

This optional audio-only sidecar uses DIAL discovery and YouTube Lounge so the
YouTube Music / YouTube phone app can see a TV-like receiver called **Aperture
Music**. It is not a certified Chromecast, general Cast receiver, or Google Home
speaker-group target. Current intended scope is music audio, not TV video.

## Verification status

- Own wrapper tests cover input validation, token-log suppression, private IPC,
  stale playback cancellation, volume bounds, IPC framing/failure and file-load
  confirmation.
- Cloud runtime blocks network-interface enumeration used by SSDP. Cloud tests
  therefore cannot prove phone discovery on the home's LAN.
- Real public music resolution and audio-stream range reads succeeded in the cloud.
- Phone/account behaviour, HDMI audio, reconnect,
  queues and simultaneous Kodi/controller use remain acceptance checks.
- Experimental source is prepared separately from the gaming installer. Do not
  make it part of the normal Pi installation without explicitly opting in.

## Security and operation

The receiver uses the phone's per-track credential-transfer token only in memory
for that video's YouTube request. It does not request account cookies or a Google
password, persist playback tokens, or provide an unauthenticated management web
page. Third-party log text is discarded because it may contain credentials.
The media backend accepts only HTTPS googlevideo.com media URLs, disables mpv
config/scripts/yt-dlp hooks, uses a private user-runtime IPC socket and starts at
20% volume. No Bluetooth settings, sound-device chmod, firewall, kiosk, DRM display
or root service is installed. DIAL itself exposes playback control to devices on
the chosen trusted LAN interface. Do not forward its port to the Internet.

Audio goes through the same user's PulseAudio-compatible PipeWire session. Kodi
must also share that session; direct ALSA or passthrough can monopolize HDMI.
This script intentionally does not change working Kodi output settings. Stop
Kodi for the first audio test if needed. No screen takeover is attempted.

## Dependencies

Requires Node >=20, npm, mpv, a working same-user PulseAudio/PipeWire session,
and user systemd. Existing Raspberry Pi OS packages are preferred. If the OS
only offers Node 18, stop rather than making an unplanned OS/repository change.

The dependency packages are pinned to patrickkfkan/volumio-ytcr commit
7a315b3f9ae077efeedacbfc99ec3020aa14f132:
- yt-cast-receiver-2.1.1-volumio-ytcr.tgz
- volumio-yt-support-2.1.1.tgz

The resolver transitively uses patrickkfkan/Volumio-YouTube.js v1.7.0 and npm
packages. Its required compile step executes during npm install. Node is selected
explicitly for the support helper; a checked patch removes the upstream Deno
probe when Node is selected. A second checked patch adapts the fixed decoder
to CommonJS; another cleans up failed initialization. No Deno is downloaded.
The support helper runs YouTube-supplied player/BotGuard JavaScript, which is why
this remains a separately approved experimental component. Installing it is a separate opt-in from installing the skin or gaming tools.

## Optional Pi installation

Run these from the repository's casting directory, as the same normal user who
runs Kodi, not with sudo. `sh setup.sh --check` is read-only.

If packages are missing, review this Raspberry Pi OS package command before
running it: `sudo apt update && sudo apt install nodejs npm git mpv pulseaudio-utils`.
It does not install or switch the audio server. Check `node --version`: if it is
below 20, stop and arrange an appropriate supported Node version first.
The setup requires an existing working user audio session and user systemd bus.
SSH alone cannot create that desktop/audio session for you.

`sh setup.sh --install PI_LAN_IPV4` installs a private build and a user service,
but does not start it or enable it at boot. It leaves a timestamped backup if
an earlier service unit exists.

For a supervised test: `systemctl --user start aperture-cast`.
Check status with `systemctl --user status aperture-cast`.
Connect the phone to the same LAN, select Aperture Music in YouTube Music's Cast
menu, and try a normal track, pause/resume, seek, next, phone lock and disconnect.
For shutdown: `systemctl --user stop aperture-cast`.

Only after live verification should boot start be considered. No automatic
restart is enabled so an upstream error cannot create a restart/token storm.

## Upstream references

- https://github.com/patrickkfkan/yt-cast-receiver
- https://github.com/patrickkfkan/volumio-ytcr
- https://github.com/ffindog/ytm-cast-receiver (architecture evidence, not deployed)

The recent ffindog receiver reports daily iPhone/YouTube Music use on Debian 12
LXC, not verified Raspberry Pi/Android operation. Its Docker/kiosk deployment is
not used here. Upstream changes to YouTube can break this experimental route.

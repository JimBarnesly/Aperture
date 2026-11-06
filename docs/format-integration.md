# Format inside Aperture

Music is one Format-backed experience. The skin and standalone Format application
share the same server, published library, catalogue and download queue. The Kodi
add-on remains independently installable for users of another skin, but Aperture
does not present it as a separate streaming service or keep a second music library.

## Native controls

- **Albums:** cover shelf and complete ordered-release playback.
- **Artists:** albums grouped by their published album artist.
- **Search library:** search existing published albums and tracks locally in the
  server snapshot, without contacting a catalogue provider.
- **Find music:** artist catalogue search and release preview through Format.
- **Downloads:** acquisition progress and shadow-library publication state, with
  explicit queue actions where the server permits them.
- **Configure Format server:** the existing add-on setting, preserved on upgrade.

Catalogue search is artist-oriented and currently covers the server's first 100
studio-album release groups. It is not an unrestricted track search. Catalogue
availability is not evidence of provider availability or permission to download.
Use authorised sources and only music you have rights to obtain.

The client confirms acquisition and queue changes and rechecks server health at
action time. It does not retry an uncertain write automatically. A cancellation
request is not reported as finished until Format reports it. Acquisition status
and published-library status are distinct: an incomplete or unvalidated release
does not become playable merely because a provider finished.

## Existing protected Pi server

The verified server baseline is Format commit
`1eea9b8a62c0bbdbf41fdef68f4343113fc94589` on draft PR #1:
https://github.com/JimBarnesly/Format/pull/1

Inspect the Pi first. Establish the actual desktop user, HDD UUID/mount, music
folder, existing Format service, source revision and add-on settings. Do not
guess paths, reinstall a healthy service, copy media or rerun gaming setup.

If the server is not installed, use that complete pinned Format checkout in a
persistent directory and follow `deployment/pi/README.md`. Its bootstrap is:

```sh
sh deployment/pi/setup.sh '/verified/existing/HDD/Music'
```

This is a placeholder, not a path to paste unchanged. The folder must already
exist on the identified HDD. The setup preserves media, uses a verified official
Node runtime when needed and runs Format as a protected unprivileged service.
Review package/service changes locally. Do not change mounts, ownership, tags,
credentials, firewall settings or read-only protections as an incidental fix.

For Kodi on the same Pi, configure `http://127.0.0.1:4534` and verify locally:

```sh
systemctl status format-pi --no-pager
curl -f http://127.0.0.1:4534/api/health
```

The server must finish its initial scan. An empty published library may mean
albums are awaiting identification rather than that the disk is empty. Follow
the Format Pi guide's metadata-only rescan/reconcile steps and inspect shadow
status. Do not weaken publication validation, retag files or download missing
tracks to make the shelf look populated.

## Install the matching client and skin

Use one complete Aperture checkout pinned to the exact green commit being tested.
Keep Estuary and a backup of the Kodi profile. Exit Kodi normally and verify it
has stopped; do not kill it during playback or saving. As the Kodi desktop user:

```sh
sh install-format.sh
sh install.sh
```

These installers refuse live replacement and preserve earlier add-ons outside
Kodi's add-on scan directory. They retain saved settings. On restart, enable
Format for Aperture if needed, select Aperture, and choose Keep only after the
screen and controls respond. Configure the existing server URL if it is absent.
There is no need to rerun gaming, movie scanning or OS setup for this update.

## Download boundary on the Pi

The verified default Pi server disables acquisition, cancellation and
prioritising while leaving browsing, playback and publication status available.
The skin does not turn writes on or silently fall back to another server.

Newer servers can report separate `capabilities.acquire`, `capabilities.cancel`
and `capabilities.prioritize` booleans. Each action requires its own exact `true`
value, even when other actions are enabled. A server can keep `readOnly: true`
for existing-library protection while explicitly allowing new downloads. A
present capability object is authoritative: missing or malformed values never
fall back to the broad read-only flag. Only older servers that omit the object
entirely use `readOnly: false` as the legacy permission signal. Unreachable
health checks fail closed; readiness text is never permission.

A download-enabled Pi deployment is not complete merely by changing a flag.
It needs a separately verified server build, a dedicated writable destination,
enough disk space, authorised provider access and compatible staging/publication
on the same filesystem and mount boundary. Preserve the protected profile until
that path is tested. The existing unauthenticated Format API must not be exposed
to an untrusted LAN.

## Acceptance and reporting

CI uses original synthetic audio, a disposable loopback server and mocked download
jobs. Native Kodi checks cover input, artwork, album order, queue/playback clock,
Back/repeated entry, offline recovery and download controls. It does not prove
physical Pi performance, audible output, provider credentials or real acquisition.

On the Pi verify Music enters Format without the old chooser; actual album art,
artists and search; complete album order and playback/Stop; Back/reopen; offline
recovery; and Downloads controls or a truthful disabled/readiness message. Keep existing files, saves
and metadata unchanged. Record exact source/install versions and pass/fail steps.
Public feedback should contain only sanitised technical evidence, never media
paths, personal album lists, hostnames, device IDs, tokens or unredacted logs.

# Torrentio online playback — opt-in first slice

## What is available

Movies → Sources → **Set up online playback (Torrentio)** opens a guided setup menu.
It explains access and storage risks, offers a public provider-browser handoff,
shows local connection status, checks a saved provider manifest on request, and
removes the local connection on confirmation. Discover's normal Select remains
metadata-only. A movie's context menu now offers **Find streams (Torrentio)**.
Search, source selection, and Play each remain explicit actions.

**The guided browser handoff does not complete connection.** Torrentio's reviewed
configuration UI asks for an API key and links to Real-Debrid's API-token page;
there is no supported Torrentio RD device-code flow or secure Kodi return channel
in that source. We do not reuse Aperture's existing RD OAuth grant or manufacture
an OAuth integration. The first wizard choice opens only the public, credential-
free https://torrentio.strem.fun/configure page. If no browser is available, the
wizard displays that public address. Provider-browser and physical Kodi behavior
have not been tested on a device. A truly layperson-complete in-app connection is
**blocked on a supported secure credential handoff**, not shipped as one-click.

## Optional advanced connection (Linux)

For experienced users who already have a configured manifest, the wizard offers
**Advanced: import private configuration file**. This is not the primary setup
path. Do not paste the manifest/token into settings, chat, logs, plugin commands,
a clipboard integration, or screenshots. It is a credential, not a shareable URL.

The picker accepts a local regular `.txt` file owned by the Kodi OS user, with no
group/other permissions (0600), no hard links, and no symlink in its path. Its sole
line must be the user's HTTPS `torrentio.strem.fun` configured manifest ending in
`/manifest.json`. Only the `realdebrid` credential and known preference keys are
accepted; `debridoptions` must include `nodownloadlinks`, optionally `nocatalog`.
Other debrid providers, unknown keys, unconfigured/P2P manifests, query strings,
fragments, alternate origins and credentials embedded in authority are rejected.
The importer intentionally accepts only a conservative ASCII configuration grammar.
It does not fetch the manifest during import.

After two consent screens, an atomic copy is saved under the add-on profile's
`torrentio-private/connection`: directory 0700, file 0600. The original import file
is **not** deleted. Storage is not encrypted; same-user programs and backups can
read it. Disconnect removes only this saved copy; original files/backups and the
provider-side token grant remain. Revoke/rotate the token on Real-Debrid yourself.
Existing Real-Debrid account-download sign-in and local media are untouched.

**Check saved connection** sends the configured manifest only after confirmation.
A compatible response proves provider protocol reachability, not token validity,
account subscription, rights, cache availability or successful playback. Status is
conservative and does not persist a misleading “connected/working” flag.

## Source and playback contract

- IMDb movie IDs only, from Cinemeta catalogue rows. No title matching or series.
- Search sends the saved configuration/token and selected ID to Torrentio after
  confirmation. It does not directly contact the RD API or acquire a token.
- Only Torrentio's `[RD+]` entries with strict same-origin `/resolve/realdebrid/`
  URLs containing the configured token are selectable. No magnet/infohash,
  external URL, other provider, headers, proxy headers, or P2P fallback.
- Provider labels/titles/filenames never become UI text. Labels expose only a
  recognized resolution plus a numbered selection; codec, language and release
  differentiation are not yet available. `[RD+]` is a provider claim, not proof of
  cached status; the UI does not label results cached or authorized.
- Selected sources are identified in memory by opaque SHA-256 IDs, re-fetched and
  revalidated before resolution. No secret URLs or tokens go into plugin routes,
  settings, disk caches, log messages, exception text or browser launch arguments.
- Playback confirmation explains that the resolver GET may queue an RD transfer,
  add history and use traffic. No client-side P2P exists; Debrid-only does **not**
  mean guaranteed cached-only. Cancellation/navigation is rechecked before the
  lookup and between the re-fetch and resolver. An already-sent GET cannot be undone.
- Lookup/check redirects fail closed. The resolver is requested once without
  following redirects. Only its 302 Location to HTTPS
  `<single-host-label>.download.real-debrid.com`, with a direct video extension,
  no credentials/port/fragment/control characters/Kodi header suffix, is handed to
  Kodi. HTTP, error-video, alternate-CDN and other formats fail with an actionable
  message. No auto-retry or attempt to “upgrade” HTTP to HTTPS.
- Kodi receives only the final RD URL, with the implementation-owned
  `|redirect-limit=0` option. Kodi's own logs may expose that signed download URL.
  Do not share raw Kodi logs. HTTPS playback and this option need native acceptance.
- Provider connections use TLS validation, no environment proxy, public-only DNS
  pinned to the chosen address, 5s DNS wait, 10s connect/socket timeout and a 15s
  post-connect socket shutdown deadline. JSON is capped at 512 KiB, input entries
  at 200 and displayed distinct sources at 60. No retries. Concurrent UI invocations
  are not globally rate-limited. DNS workers are daemon threads and may finish
  after their timeout; no credential is passed to them.
- The final RD hostname is public-DNS checked but Kodi resolves it again. This
  handoff trusts the explicitly allowlisted RD DNS zone and Kodi TLS stack; it
  cannot pin player DNS or enforce another add-on/global player's proxy settings.
  Do not claim universal SSRF protection across Kodi itself. Unexpected resolver
  architectures fail closed rather than returning provider URLs to the player.

## Source evidence (no account or movie requests)

Reviewed official Torrentio repository snapshot
`f347bf5181da82a79a9f2527864125187ea95bd3`:

- [configuration UI](https://github.com/TheBeastLT/torrentio-scraper/blob/f347bf5181da82a79a9f2527864125187ea95bd3/addon/crates/addon/templates/landing.html),
  lines 299–315: API Key field and `https://real-debrid.com/apitoken` link.
- [configuration parser](https://github.com/TheBeastLT/torrentio-scraper/blob/f347bf5181da82a79a9f2527864125187ea95bd3/addon/crates/addon/src/domain/config.rs): pipe-separated key/value config.
- [provider processing](https://github.com/TheBeastLT/torrentio-scraper/blob/f347bf5181da82a79a9f2527864125187ea95bd3/addon/crates/addon/src/providers/mod.rs),
  `populate_cached_links`/`populate_download_links`: RD+ vs download labels.
- [HTTP routes](https://github.com/TheBeastLT/torrentio-scraper/blob/f347bf5181da82a79a9f2527864125187ea95bd3/addon/crates/addon/src/http/server.rs),
  `redirect_response`: resolver returns 302, including error-video redirects.
- [RD resolver](https://github.com/TheBeastLT/torrentio-scraper/blob/f347bf5181da82a79a9f2527864125187ea95bd3/addon/crates/addon/src/providers/realdebrid.rs): may create/recreate torrents and return downloading/error videos.
- [Kodi Omega CurlFile.cpp](https://github.com/xbmc/xbmc/blob/Omega/xbmc/filesystem/CurlFile.cpp):
  `redirect-limit` parsing and `CURLOPT_FOLLOWLOCATION = m_redirectlimit != 0`.

This is source evidence, not confirmation that the live Torrentio deployment runs
that revision. No live manifest/account/search/resolver/media request was made.
Synthetic tests exercise configured lookup → filtering → selection → re-fetch →
302 validation → player handoff, error handling and cancellation. Native Kodi,
real-account HTTPS availability, remote-control dialog readability, browser launch,
seek/play/stop, physical display/audio and deployment acceptance remain pending.

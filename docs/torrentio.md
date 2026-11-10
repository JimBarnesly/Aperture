# Torrentio online playback — explicit opt-in

## Setup without manual token copying

1. Open **Movies → Sources → Set up online playback (Torrentio)**.
2. Choose **Connect with Real-Debrid (no token copying)**. Review storage consent,
   then the separate permission to disclose your **access token** and movie IDs to
   **torrentio.strem.fun**. This token can authorize unrestrict, torrents, downloads
   and user information: it is not restricted to the selected movie.
3. If this profile is not signed in, Aperture shows a Real-Debrid device code.
   Open `https://real-debrid.com/device` on your own device, enter the code, and
   personally review/approve the official shared open-source application (not named
   Aperture). Cancel, navigation away, shutdown, denial or expiry stops setup.
   An existing RD sign-in is reused **only after both consent screens**.
4. Open Discover and select a movie. Read its metadata, then choose the visible
   **Find streams (Torrentio)** action. The context-menu shortcut remains available.
   Confirm search, choose a source, then separately confirm Play. Merely browsing
   metadata never starts a Torrentio request.

This is **not token-free**: only manual credential copying is eliminated. Native
setup saves the marker `rd-oauth-v1` in `torrentio-private/connection`, not another
copy of the token. RD refresh credentials remain in the existing owner-only RD
store. Before each check/search/play, Aperture acquires that store's process lock
and calls `debrid.Client.token()`, refreshing at or within 60 seconds of expiry.
Only the current access token enters an in-memory manifest. Refresh tokens and
client secrets are never disclosed to Torrentio. Configuration/credential grammar
fails closed; unsupported tokens are not silently rewritten.

Setup itself makes no Torrentio request. It may sign in or refresh with RD after
consent. **Check saved connection** separately asks permission before sending the
manifest. A valid manifest proves protocol reachability, not account validity,
subscription, rights, cache availability or successful playback. All status claims
remain conservative. Storage is OS-user-only, not encrypted; same-user programs
and backups can read it.

**Disconnect Torrentio** stops future sharing from this profile under the same
lock used for disclosure. It cannot retract a token already sent or undo an
already-sent resolver request. Revoke the application/token on Real-Debrid to end
prior access. RD sign-in/downloads and local media remain unchanged. A busy lock
fails with a fixed retry-later message instead of racing. Corrupt saved configuration
shows an **unreadable — reset or replace** state; reset/replace verifies inode
ownership/type/permissions without decoding the corrupt secret. Unsafe symlinks,
hard links and non-owner-only targets still fail closed.

## Optional advanced import

Advanced users may import an existing configured manifest in an owner-only local
`.txt` file. This is not required for normal setup. Never put tokens/manifests in
chat, screenshots, plugin commands, settings or shared logs. The picker accepts a
regular 0600 file owned by the Kodi OS user, without hard links or any symlink in
its path. Only the HTTPS `torrentio.strem.fun` origin, `realdebrid` credential,
known preferences and `debridoptions=nodownloadlinks` (optionally `nocatalog`) are
accepted. Unknown providers/options, query strings, fragments and P2P manifests
are rejected. After two consents an atomic private copy is saved (directory 0700,
file 0600), without a provider request. Original files and backups are not deleted.

## Source and playback contract

- IMDb movie IDs only. No title matching, series or direct P2P fallback.
- Only `[RD+]` entries with validated same-origin `/resolve/realdebrid/` URLs and
  the exact configured token are selectable. Reject magnet/infohash, external
  URLs, other providers, custom headers and proxy headers.
- Resolver indices accept digits, `null`, or the official exact `undefined`
  sentinel. Case variants and arbitrary text remain rejected.
- Labels expose bounded recognized resolution, codec and language plus bounded
  numeric size when provided. No raw titles, filenames, URLs, tokens or Kodi
  markup are copied into labels. These are provider claims, not verified media
  properties or proof of caching/authorization.
- Opaque SHA-256 source IDs cover the validated resolver identity **excluding the
  rotating credential**. Before resolution, sources are re-fetched using the
  current token; selection survives rotation but a changed identity requires a
  new selection. No secret routes, disk source caches or logged raw errors.
- Play warns that Torrentio's resolver GET may add history, queue transfers and
  consume traffic. Exactly one resolver request is made; there is no automatic
  mutation retry or polling of queued transfers. Known downloading/access/limit/
  archive/size/opening/removal/unavailable/error-video outcomes produce distinct
  fixed messages. Error videos are never played. A queued transfer may remain on RD.
- Progress dialogs support cancellation. Navigation/shutdown/cancel gates run
  before requests, between re-fetch and resolver, after public DNS, immediately
  before the token-bearing GET following TCP/TLS setup, and after the result.
  The UI supplies the same cancellation state for manifest checks, lookups and
  playback. Cancel during DNS/TLS prevents HTTP transmission once that stage
  returns; it does not forcibly interrupt the blocking stage. Once transmission
  begins it cannot be undone: the bounded request finishes and late results are
  discarded without retry or playback. Device approval uses cancellable short
  waits until expiry. See [transport TDD evidence](torrentio-cancellation-tdd.md).
- Lookup/check redirects fail closed. Resolver redirects are inspected, not followed.
  Only 302 to HTTPS `<single-host-label>.download.real-debrid.com` with a direct
  video extension, no authority credentials/port/fragment/control characters or
  Kodi header suffix, can reach Kodi. No HTTP upgrade or alternate-CDN fallback.
- Final RD URLs carry implementation-owned `|redirect-limit=0`. Kodi's own logs
  may expose signed download URLs; do not share raw logs.
- Torrentio transport validates TLS, ignores environment proxies, checks public
  DNS and pins the chosen address. Limits: 5s DNS wait, 10s connect/socket timeout,
  15s post-connect socket shutdown deadline, 512 KiB JSON, 200 input entries and
  60 distinct displayed sources. DNS daemon workers carry no credentials.
- RD OAuth uses the existing bounded, no-redirect RD client. Final playback DNS is
  public-checked, but Kodi resolves again: the handoff trusts RD's DNS zone and
  Kodi TLS. No claim of universal SSRF protection across Kodi/player proxies.

## Source evidence and remaining acceptance

Official Torrentio snapshot `f347bf5181da82a79a9f2527864125187ea95bd3`:

- [RD HTTP client](https://github.com/TheBeastLT/torrentio-scraper/blob/f347bf5181da82a79a9f2527864125187ea95bd3/addon/crates/debrid/src/realdebrid.rs)
  calls `request.bearer_auth(api_key)`. RD OAuth access tokens are therefore
  **source-compatible**, not live-proven against the hosted service.
- [Resolver support](https://github.com/TheBeastLT/torrentio-scraper/blob/f347bf5181da82a79a9f2527864125187ea95bd3/addon/crates/addon/src/providers/support.rs)
  `index_text(None)` emits `undefined`; the synthetic fixture mirrors this shape.
- [RD resolver](https://github.com/TheBeastLT/torrentio-scraper/blob/f347bf5181da82a79a9f2527864125187ea95bd3/addon/crates/addon/src/providers/realdebrid.rs)
  may create/recreate torrents and return downloading/error outcomes.
- [Static outcomes](https://github.com/TheBeastLT/torrentio-scraper/blob/f347bf5181da82a79a9f2527864125187ea95bd3/addon/crates/addon/src/providers/static_videos.rs)
  supplies the exact allowlisted error-video paths used for fixed messages.
- [Kodi Omega CurlFile.cpp](https://github.com/xbmc/xbmc/blob/Omega/xbmc/filesystem/CurlFile.cpp)
  implements `redirect-limit` and disables following redirects at zero.

No real-account, live manifest/search/resolver/media requests, native Kodi session,
deployment or push were performed. Synthetic tests exercise device approval,
consent, refresh, rotation, cancellation, storage recovery and playback handoff.
Live OAuth compatibility, hosted revision, strict HTTPS media availability,
remote-control dialog readability, playback/seek/stop and physical audio/video
remain acceptance gates. See [review-fix TDD evidence](torrentio-review-tdd.md).

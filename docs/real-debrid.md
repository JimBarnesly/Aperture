# Optional Real-Debrid connector

This candidate adds an **opt-in connector**, not a Stremio catalogue or torrent
search. Discover/Search use the separate Cinemeta metadata adapter; My Kodi
library remains accessible under Collections. Sources can list existing
Real-Debrid download-history video entries (60 per page) and resolve an HTTPS
link the user is authorized to access. It does not add magnets, select torrent
files, scrape indexes, buy subscriptions, or modify account settings.

## Prerequisites and sign-in

1. Obtain an **Aperture application client ID** from Real-Debrid's application
   registration process. This is a public app identifier, not the user's API key.
   No other application's ID is borrowed or shipped. Registration is not performed
   by this implementation. Without this ID the connector cannot sign in.
2. Set the public identifier in Movies add-on settings (Sources > Configure
   application client ID). Never paste an API key, password or client secret there.
3. Choose Sources > Connect Real-Debrid. Read and approve the on-device disclosure
   of account access and local credential storage. Go to
   https://real-debrid.com/device yourself, enter the displayed short-lived code,
   and approve the application. An assistant-driven real grant still requires
   the user's action-time approval. No live grant was created during development.
4. Polling runs only while that sign-in dialog is active, with the returned
   interval (at least five seconds), expiry, Cancel and Kodi shutdown handling.
   Closing/cancelling does not save newly issued credentials. If you approved on
   the website just before cancellation, revoke that grant on Real-Debrid too.

The implementation follows Real-Debrid's open-source device flow and its
provider-specific refresh grant, documented at https://api.real-debrid.com/.
The account must have whatever entitlements Real-Debrid requires for the selected
link. This connector neither buys nor upgrades them. Rate limits stop the current
action; revoked/expired access prompts reconnection rather than retrying forever.

## Privacy and storage

No API key entry is required. A successful device flow stores the user-bound
client credentials and refresh/access tokens in a dedicated owner-only (0700)
profile directory, with atomic 0600 credential files. POSIX support is required;
unsupported permissions/platforms fail closed. This is **not encrypted storage**
and not a system keychain. Other programs running as the same OS user, root and
profile backups can read it. Keep the profile private and exclude its credentials
from shared backups. No changes to existing filesystem permissions are made.

An exclusive process lock prevents concurrent login, refresh and disconnect.
Secrets are not put in add-on settings, plugin navigation URLs or application
logs. Authenticated API requests use TLS and reject redirects. Error messages
are fixed and do not include response bodies, link strings or credentials.
Directory caching on disk is disabled. Resolved playback URLs must reach Kodi's
player in memory, and **Kodi or other player components may log them**. Avoid
debug logging and redact any Kodi logs before sharing them.

Disconnect removes this profile's saved credentials only. To revoke ongoing
server-side access, remove the application in the Real-Debrid account's application
management page. Local disconnect does not claim to revoke the refresh grant.

## Playback and boundaries

Existing downloads are identified in plugin routes by account entry ID and page,
not by a signed URL. Clicking re-reads that page and resolves only a matching
current entry; if the page shifted, reopen it. Existing links may expire: failure
is left to Kodi playback and the user can explicitly resolve the original link
again. The connector does not silently regenerate links or consume extra traffic.

Manual link resolution displays a confirmation before sending the entered link
to Real-Debrid. It can consume account traffic and add a download-history entry.
Remote-traffic mode is disabled. Only HTTPS web links are accepted. No entered
link is fetched directly by the add-on; Real-Debrid resolves it. Returned playback
links reject embedded credentials, literal IP hosts, nonstandard ports, control
characters and Kodi header injection. As with any player, a trusted provider's
playback URLs are passed to Kodi; there is no custom media proxy.

## Verification status

Unit tests mock every API call and exercise OAuth waiting/expiry/cancel,
credential permissions and locking, refresh/revocation, redacted HTTP failures,
redirect refusal, safe routes, download paging and explicit user choices. No
real account sign-in, provider entitlement, link availability, live playback,
physical remote or audible output has been verified. Existing Movies native UI
CI is separate and does not prove the RD dialogs or live provider path.

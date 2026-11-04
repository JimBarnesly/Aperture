# Music-first integration

The current repair candidate keeps Kodi's complete official Estuary foundation,
a minimal Aperture Home, native media/settings dialogs and an independently
installable Format client. An unchanged Estuary Home is available through the
skin installer's `--baseline` diagnostic mode. Switching foundations does not by
itself establish the cause of a freeze; official Confluence can be compared
independently if useful.

Format's existing library/acquisition service stays on the server. The TV add-on
is a read-only HTTP client with cover art, album/track metadata, stable album IDs
and full ordered-release playback. It does not clone the server or provision a
new one. The old private example address is intentionally not a default.

Acceptance covers browsing, covers, streaming, disc/track queue order, back/return,
settings changes and server failure/recovery. A loopback synthetic CI fixture is
separate from the user's server and library. Physical Pi audio and network
acceptance remain required.

Phone control, receiver services and third-party streaming require separate
configuration and permission. The installers do not enable Kodi HTTP control,
open ports, configure authentication or alter service/security settings.

Games/system indexing, native cover-flow refinement and receiver services follow
a stable skin/music baseline. Do not silently substitute a browser UI for Kodi.

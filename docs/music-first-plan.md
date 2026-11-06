# Music-first integration

Music opens Format directly. The native Kodi client shares the existing Format
server with the standalone web application; it does not create a competing
music library, duplicate the server or embed a browser UI.

The skin provides an album shelf and native lists for artists, tracks, library
search, artist catalogue search and downloads. Published releases play in their
intended disc/track order. Catalogue search and acquisition remain server-side,
including provider handling, release validation and publication safeguards.

Writes require the server's explicit writable capability and a confirmed user
action in Kodi. Read-only Pi servers can browse and play; download management
stays unavailable rather than bypassing media protection. The client never
changes service settings, grants operator privileges or exposes a LAN endpoint.

[Installation and acceptance](format-integration.md) distinguish mocked CI from
physical Pi/HDD, provider and audible-output tests. Keep games/controller crash
investigation separate from Format music acceptance.

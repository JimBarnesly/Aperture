# Upstream and package boundaries

The complete skin is assembled from the official Estuary distributed with the
Kodi 21 runtime under test. Its XML, textures, fonts and license notices are
retained. The distribution source and version are recorded in APERTURE_BUILD.json.
Aperture's Home override uses the existing Kodi GUI 5.17.0 contract.

Estuary code is GPL-2.0-compatible and artwork is CC-BY-SA 4.0 as described in its
retained addon.xml and license notices. Fonts retain their individual licenses.
The repository GPL-3.0 license does not relicense these inherited components.
Do not distribute the override directory alone as an installable skin.

The original prototype used relative distribution font links, an undefined
font30 name, and kept duplicate-ID previous copies inside Kodi's add-on scan
folder. These are concrete defects; they do not prove the cause of the reported
Pi freeze without its complete log. A desktop test is not Pi hardware acceptance.

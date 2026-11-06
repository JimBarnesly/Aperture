# Upstream and package boundaries

The complete skin is assembled from the official Estuary distributed with the
Kodi 21 runtime under test. Its XML, textures, fonts and license notices are
retained. The distribution source and version are recorded in APERTURE_BUILD.json.
Aperture's Home and media browser overrides use the existing Kodi GUI 5.17.0
contract. MyMusicNav.xml retains the official Omega Estuary native fallback and
adds Format-specific native containers; its upstream license remains applicable.

Estuary code is GPL-2.0-compatible and artwork is CC-BY-SA 4.0 as described in its
retained addon.xml and license notices. Fonts retain their individual licenses.
The repository GPL-3.0 license does not relicense these inherited components.
Do not distribute the override directory alone as an installable skin.

The original prototype used relative distribution font links, an undefined
font30 name, and kept duplicate-ID previous copies inside Kodi's add-on scan
folder. These are concrete defects; they do not prove the cause of the reported
Pi freeze without its complete log. A desktop test is not Pi hardware acceptance.

## MediaStream reference photograph

`skin/media/aperture/bridge.png` is the unmodified `MediaStream/Media/HomeBGPictures.png`
from Team-Resurgent/XBMC-Skinning-Project, commit
484fa2309eab69291d546398d7444e3d761f8cac. The upstream MediaStream distribution
includes a Creative Commons Attribution-ShareAlike3.0Unported licence; its notice
is retained in `skin/licenses/MediaStream-CC-BY-SA-3.0.txt`.
Source: https://github.com/Team-Resurgent/XBMC-Skinning-Project/blob/484fa2309eab69291d546398d7444e3d761f8cac/MediaStream/Media/HomeBGPictures.png
Licence: https://creativecommons.org/licenses/by-sa/3.0/

The upstream tree does not identify the photographer separately. This records
package provenance rather than claiming independent photo-rights clearance.
No original MediaStream font is included. The single-menu Home layout, fading blade and focus marker are newly authored
for Aperture; Kodi's existing fonts remain.

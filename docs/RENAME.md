# Aperture naming and upgrade compatibility

The product is **Aperture** from 1.0 RC1 onward (29 October 2026).
The previous visible spelling was Apeture.

The existing internal Kodi IDs remain `skin.apeture`, `plugin.games.apeture` and
`script.apeture.music`. Kodi uses these identifiers for installation, settings,
companion discovery and upgrades. Renaming them would create separate add-ons,
strand settings and break existing Home integration, not merely rename a label.
Accordingly the three installable ZIP filenames and source directories retain
`apeture`; display names, install instructions and release branding say Aperture.
No duplicate installations or manual folder renames are necessary.

The `APETURE_BUILD.json` provenance filename also remains compatible. Historical
repository/evidence links use their original paths until a repository rename is
actually verified. The rebrand does not alter upstream attribution or licenses.

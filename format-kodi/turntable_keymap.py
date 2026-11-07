"""Own one narrow fullscreen-music keymap, without editing existing keymaps.

Kodi only reads keymaps from its system/profile directories. Install our four
bindings while Aperture is selected; remove only byte-identical owned content
on skin change or service shutdown. All other files and custom edits are left
alone. The file is never installed by the shell installer itself.
"""
from pathlib import Path


class TurntableKeymap:
    def __init__(self, keymap_directory, source, reload_keymaps, warn):
        self.path = Path(keymap_directory) / 'zz-aperture-turntable.xml'
        self.content = Path(source).read_bytes()
        self.reload_keymaps = reload_keymaps
        self.warn = warn
        self.active = None

    def sync(self, active):
        """Check only on a skin transition, not on every service tick."""
        active = bool(active)
        if active == self.active:
            return
        self.active = active
        try:
            changed = self._install() if active else self._remove()
            if changed:
                self.reload_keymaps()
        except OSError:
            # Playback and the shelf still work with Kodi's original bindings.
            self.warn('Aperture turntable keymap could not be updated; existing files were preserved.')

    def _install(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Exclusive creation refuses collisions (including symlinks).
            with self.path.open('xb') as output:
                output.write(self.content)
        except FileExistsError:
            if self.path.is_symlink() or not self.path.is_file() or self.path.read_bytes() != self.content:
                self.warn('Aperture turntable keymap name is already in use; it was not changed.')
            # A matching file was already loaded by Kodi on startup, or by this
            # service. Do not continually reload or overwrite user changes.
            return False
        return True

    def _remove(self):
        if self.path.is_symlink() or not self.path.is_file():
            return False
        if self.path.read_bytes() != self.content:
            return False
        self.path.unlink()
        return True

    def close(self):
        # Re-check content even after a failed installation; never delete edits.
        self.active = None
        self.sync(False)

"""Consent-first Torrentio wizard and explicit movie source selection."""
import webbrowser
import xbmc
import xbmcgui
from resources.lib.torrentio import Client, Store, ProviderError

PUBLIC_SETUP = 'https://torrentio.strem.fun/configure'


def run(query, profile, base, handle):
    dialog = xbmcgui.Dialog()
    origin = xbmc.getInfoLabel('Container.FolderPath')
    monitor = xbmc.Monitor()

    def current():
        return not monitor.abortRequested() and xbmc.getInfoLabel('Container.FolderPath') == origin

    def consent(title, message):
        return dialog.yesno(title, message) and current()

    store = Store(profile)
    try:
        action = query.get('action', [''])[0]
        if action == 'torrentio_find':
            config = store.load()
            if config is None:
                dialog.ok('Online playback is not connected', 'Open Sources → Set up online playback. Discover remains a metadata catalogue until you connect a source.')
                return
            identifier = query.get('id', [''])[0]
            config.lookup(identifier)  # validate before any consent or network
            if not consent('Find streams with Torrentio?', 'Send this movie ID and your saved RD token to Torrentio? No P2P. Results do not prove rights, availability or cache status. Only use content you may access.'):
                return
            client = Client(config)
            entries = client.streams(identifier)
            if not current():
                return
            if not entries:
                dialog.ok('No supported sources returned', 'No supported Real-Debrid sources were returned for this movie. This is not proof the movie is unavailable. Try again later.')
                return
            selected = dialog.select('Choose a source · availability unverified', [str(i + 1) + '. ' + entry.label for i, entry in enumerate(entries)])
            if selected < 0 or selected >= len(entries) or not current():
                return
            if not consent('Play selected source?', 'Torrentio may add RD history or queue a transfer and use traffic. Kodi may log the final signed URL. Only play content you have permission to access. Continue?'):
                return
            path = client.playback(identifier, entries[selected].id, cancelled=lambda: not current())
            if current():
                xbmc.Player().play(path)
            return
        if action != 'torrentio_setup':
            raise ProviderError()
        config = store.load()
        selected = dialog.select('Set up online playback · ' + ('saved, untested' if config else 'not connected'), [
            '1. Guided setup in provider browser',
            'Advanced: import private configuration file',
            'Check saved connection (no playback)',
            'Connection status and help',
            'Disconnect Torrentio from this profile',
        ])
        if selected < 0 or not current():
            return
        if selected == 0:
            if not consent('Online playback · 1/2', 'Torrentio is a third party. It receives your RD token and movie searches. Real-Debrid access may cost money. No P2P in Aperture; only use content you may access. Continue?'):
                return
            if not consent('Online playback · 2/2', 'Torrentio offers API-token setup, not a Kodi device-code sign-in. Browser setup cannot finish connecting Aperture yet. Open its public setup page without sending existing RD credentials?'):
                return
            opened = webbrowser.open(PUBLIC_SETUP, new=2)
            dialog.ok('Provider setup · connection pending', ('Browser requested. ' if opened else 'Open https://torrentio.strem.fun/configure on your own browser. ') +
                      'Choose Real-Debrid and exclude download links. Aperture is not connected by this step: automatic secure return is unsupported. Do not paste tokens into chat. Advanced private-file import is optional.')
        elif selected == 1:
            if not consent('Advanced import · 1/2', 'This imports a secret Torrentio manifest from an owner-only local file. Torrentio receives its RD token and selected movie IDs when you search. No existing RD grant is reused. Continue?'):
                return
            if not consent('Advanced import · 2/2', 'Save the secret in this profile, OS-user-only but not encrypted? Same-user apps and backups can read it. Kodi may log signed playback URLs. Import only a configuration you trust.'):
                return
            path = dialog.browseSingle(1, 'Choose private local Torrentio configuration', 'files', '.txt', False, False)
            if not path or not current():
                return
            store.import_file(path)
            dialog.ok('Configuration saved · not tested', 'No provider request was made. Use Check saved connection, then Discover → movie context menu → Find streams (Torrentio). Keep the original secret file private or remove it yourself.')
        elif selected == 2:
            if config is None:
                raise ProviderError('missing')
            if not consent('Check saved connection?', 'Send the configured manifest request, including its RD token, to Torrentio? This checks the provider response only, not your RD account or movie playback.'):
                return
            Client(config).check()
            if current():
                dialog.ok('Provider responded', 'Torrentio returned a compatible manifest. RD account, rights, cache status and playback are not verified. Find streams for a movie you may access to continue.')
        elif selected == 3:
            dialog.ok('Online playback status', ('Configuration saved; provider and playback not verified. ' if config else 'Not connected. ') +
                      'Discover is metadata only. Guided setup opens the provider site; secure automatic return is not supported. Advanced import is available. Disconnect removes only this profile copy, not provider access.')
        elif selected == 4:
            if consent('Disconnect Torrentio?', 'Remove this profile’s saved Torrentio secret? This does not revoke the RD token, remove original import files or erase backups. Revoke or rotate the token on Real-Debrid yourself.'):
                store.clear()
                dialog.ok('Torrentio disconnected', 'The local connection is removed. Existing Real-Debrid downloads/sign-in and your movie files are unchanged. Revoke the token on Real-Debrid if needed.')
    except (ProviderError, OSError, ValueError):
        # Never stringify unknown errors, paths, provider labels or credentials.
        import sys
        error = sys.exc_info()[1]
        dialog.ok('Online playback', str(error) if isinstance(error, ProviderError) else 'Could not complete this action safely. Check private storage and retry.')

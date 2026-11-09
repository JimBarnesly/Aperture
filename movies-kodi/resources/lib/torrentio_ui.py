"""Consent-first Torrentio wizard and explicit movie source selection."""
import time
import re
from contextlib import contextmanager
import xbmc
import xbmcgui
from resources.lib.torrentio import Client, Config, Store, ProviderError
from resources.lib.debrid import Client as RDClient, Store as RDStore, DebridError, PUBLIC_CLIENT_ID


def run(query, profile, base, handle):
    dialog = xbmcgui.Dialog()
    origin = xbmc.getInfoLabel('Container.FolderPath')
    monitor = xbmc.Monitor()
    active_progress = [None]
    cancelled_action = [False]

    def current():
        return (not cancelled_action[0] and not monitor.abortRequested() and xbmc.getInfoLabel('Container.FolderPath') == origin
                and (active_progress[0] is None or not active_progress[0].iscanceled()))

    def consent(title, message):
        return dialog.yesno(title, message) and current()

    store = Store(profile)

    @contextmanager
    def connected_client():
        progress = xbmcgui.DialogProgress()
        progress.create('Online playback', 'Waiting for provider (bounded request). Cancel stops further requests and playback. A sent transfer request cannot be undone.')
        active_progress[0] = progress
        try:
            with locked_client() as client:
                yield client
                if not current():
                    raise ProviderError('changed')
        finally:
            # Closing progress must not erase cancellation before outer error
            # handling (including a late refresh failure) checks the action.
            cancelled_action[0] = not current()
            active_progress[0] = None
            progress.close()

    @contextmanager
    def locked_client():
        # Shared lock serializes refresh/disclosure with connect/disconnect.
        with RDStore(profile).locked() as rd_store:
            if not current():
                raise ProviderError('changed')
            config = store.load()
            if config is None:
                raise ProviderError('missing')
            if config == 'rd-oauth-v1':
                config = Config.from_token(RDClient(rd_store).token())
            if not current():
                raise ProviderError('changed')
            yield Client(config)

    try:
        action = query.get('action', [''])[0]
        if action == 'torrentio_find':
            config = store.load()
            if config is None:
                dialog.ok('Online playback is not connected', 'Open Sources → Set up online playback. Discover remains a metadata catalogue until you connect a source.')
                return
            identifier = query.get('id', [''])[0]
            if not isinstance(identifier, str) or not re.fullmatch(r'tt[0-9]{7,10}', identifier):
                raise ProviderError()
            if not consent('Find streams with Torrentio?', 'Send this movie ID and your saved RD token to Torrentio? No P2P. Results do not prove rights, availability or cache status. Only use content you may access.'):
                return
            with connected_client() as client:
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
            with connected_client() as client:
                path = client.playback(identifier, entries[selected].id, cancelled=lambda: not current())
            if current():
                xbmc.Player().play(path)
            return
        if action != 'torrentio_setup':
            raise ProviderError()
        unreadable = False
        try:
            config = store.load()
        except ProviderError:
            config, unreadable = None, True
        selected = dialog.select('Set up online playback · ' + ('unreadable — reset or replace' if unreadable else 'saved, untested' if config else 'not connected'), [
            '1. Connect with Real-Debrid (no token copying)',
            'Advanced: import private configuration file',
            'Check saved connection (no playback)',
            'Connection status and help',
            'Disconnect Torrentio from this profile',
        ])
        if selected < 0 or not current():
            return
        if selected == 0:
            if not consent('Online playback · 1/2', 'Use your Real-Debrid sign-in, or sign in next. Save refresh credentials OS-user-only, not encrypted; same-user apps/backups can read them. Real-Debrid may cost money. No P2P. Only access content you may use. Continue?'):
                return
            if not consent('Share access with Torrentio · 2/2', 'Allow torrentio.strem.fun to receive your access token and movie IDs? It can use unrestrict, torrents, downloads and user information, not just this movie. Never share refresh tokens or client secrets. Allow sharing?'):
                return
            with RDStore(profile).locked() as rd_store:
                rd_client = RDClient(rd_store)
                if rd_store.load() is None:
                    if not consent('Real-Debrid sign-in', 'Use the official shared open-source application, not named Aperture. Permissions include unrestrict, torrents, downloads and user information. Review and approve it yourself on Real-Debrid. Start sign-in?'):
                        return
                    session = rd_client.begin(PUBLIC_CLIENT_ID)
                    progress = xbmcgui.DialogProgress()
                    progress.create('Connect Real-Debrid', 'Open https://real-debrid.com/device\nEnter code: ' + session['user_code'] + '\nReview and approve there, or Cancel here.')
                    def cancelled():
                        return progress.iscanceled() or not current()
                    def wait(seconds):
                        deadline = time.monotonic() + seconds
                        while time.monotonic() < deadline:
                            if cancelled() or monitor.waitForAbort(min(0.1, max(0, deadline - time.monotonic()))):
                                return True
                        return False
                    try:
                        rd_client.connect(session, wait, cancelled)
                    finally:
                        progress.close()
                if not current():
                    return
                Config.from_token(rd_client.token())
                if current():
                    store.enable_native()
            if current():
                dialog.ok('Online playback enabled', 'No token copying needed. Provider and playback not verified. Open Discover → movie details → Find streams (Torrentio). No Torrentio request was made during setup.')
        elif selected == 1:
            if not consent('Advanced import · 1/2', 'This imports a secret Torrentio manifest from an owner-only local file. Torrentio receives its RD token and selected movie IDs when you search. No existing RD grant is reused. Continue?'):
                return
            if not consent('Advanced import · 2/2', 'Save the secret in this profile, OS-user-only but not encrypted? Same-user apps and backups can read it. Kodi may log signed playback URLs. Import only a configuration you trust.'):
                return
            path = dialog.browseSingle(1, 'Choose private local Torrentio configuration', 'files', '.txt', False, False)
            if not path or not current():
                return
            with RDStore(profile).locked():
                if not current():
                    return
                store.import_file(path)
            dialog.ok('Configuration saved · not tested', 'No provider request was made. Use Check saved connection, then Discover → movie context menu → Find streams (Torrentio). Keep the original secret file private or remove it yourself.')
        elif selected == 2:
            if config is None:
                raise ProviderError('missing')
            if not consent('Check saved connection?', 'Send the configured manifest request, including its RD token, to Torrentio? This checks the provider response only, not your RD account or movie playback.'):
                return
            with connected_client() as client:
                client.check()
            if current():
                dialog.ok('Provider responded', 'Torrentio returned a compatible manifest. RD account, rights, cache status and playback are not verified. Find streams for a movie you may access to continue.')
        elif selected == 3:
            dialog.ok('Online playback status', ('Configuration saved; provider and playback not verified. ' if config else 'Not connected. ') +
                      'Connect with Real-Debrid uses device approval or your existing sign-in after separate consent; no manual token copying. Torrentio receives an access token, never refresh credentials. Disconnect stops future sharing, not prior access.')
        elif selected == 4:
            if consent('Disconnect Torrentio?', 'Stop future token sharing from this profile? This cannot retract an access token already disclosed to Torrentio. Revoke the application/token on Real-Debrid to end prior access. Original import files and backups remain.'):
                with RDStore(profile).locked():
                    if not current():
                        return
                    store.clear()
                dialog.ok('Torrentio disconnected', 'The local connection is removed. Existing Real-Debrid downloads/sign-in and your movie files are unchanged. Revoke the token on Real-Debrid if needed.')
    except (ProviderError, DebridError, OSError, ValueError):
        # Never stringify unknown errors, paths, provider labels or credentials.
        import sys
        error = sys.exc_info()[1]
        if not current() or isinstance(error, DebridError) and error.kind == 'cancelled':
            return
        dialog.ok('Online playback', str(error) if isinstance(error, (ProviderError, DebridError)) else 'Could not complete this action safely. Check private storage and retry.')

"""Real-Debrid open-source device OAuth and existing downloads only.

No catalogue search, torrent acquisition, background polling or credential logging.
Transport and clocks are injectable so tests never contact an account.
"""
import ipaddress
import json
import math
import os
import re
import stat
import tempfile
import time
from contextlib import contextmanager
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

API = 'https://api.real-debrid.com/rest/1.0/'
OAUTH = 'https://api.real-debrid.com/oauth/v2/'
GRANT = 'http://oauth.net/grant_type/device/1.0'
PAGE_SIZE = 60


class DebridError(Exception):
    """Only fixed, user-safe messages, never response bodies or URLs."""
    def __init__(self, kind='service'):
        self.kind = kind
        super().__init__({
            'auth': 'Real-Debrid sign-in expired or was revoked. Connect again.',
            'pending': 'Waiting for Real-Debrid approval.',
            'denied': 'Real-Debrid did not authorize this request.',
            'rate': 'Real-Debrid is busy. Wait before trying again.',
            'expired': 'The sign-in code expired. Connect again.',
            'cancelled': 'Sign-in cancelled. No credentials were saved.',
            'storage': 'Private credential storage is unavailable on this profile.',
            'busy': 'Another Real-Debrid action is running. Try again shortly.',
            'config': 'Configure an Aperture Real-Debrid application client ID first.',
            'invalid': 'Real-Debrid returned an unsupported response or link.',
            'missing': 'This item is no longer on this downloads page. Reopen the library.',
            'service': 'Real-Debrid is unavailable. Please try again later.',
        }.get(kind, 'Real-Debrid request failed.'))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(method, url, fields=None, token=None):
    """Bounded TLS requests. Credentials cannot follow redirects to other hosts."""
    if not url.startswith((API, OAUTH)):
        raise DebridError('invalid')
    data = urlencode(fields).encode('utf-8') if fields is not None else None
    headers = {'Accept': 'application/json', 'User-Agent': 'Aperture-Movies/0.3'}
    if data is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        with build_opener(NoRedirect()).open(Request(url, data=data, headers=headers, method=method), timeout=15) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise DebridError('invalid')
        result = json.loads(raw)
        if not isinstance(result, (dict, list)):
            raise DebridError('invalid')
        return result
    except HTTPError as error:
        code = error.code
        error.close()
        raise DebridError({401: 'auth', 403: 'denied', 429: 'rate'}.get(code, 'service')) from None
    except (URLError, OSError, ValueError):
        raise DebridError('service') from None


def secret(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9._~+/-]{1,4096}', value):
        raise DebridError('invalid')
    return value


def number(value, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= maximum:
        raise DebridError('invalid')
    return value


def web_url(value):
    if not isinstance(value, str) or len(value) > 8192 or any(ord(c) < 33 or c in '|\\' for c in value):
        raise DebridError('invalid')
    try:
        url = urlsplit(value)
        host = (url.hostname or '').rstrip('.').lower()
        if url.scheme != 'https' or url.username or url.password or url.port not in (None, 443) or '.' not in host or host.endswith(('.local', '.localhost')) or host == 'localhost' or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}', host):
            raise ValueError()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError()
    except ValueError:
        raise DebridError('invalid') from None
    return value


class Store:
    """POSIX owner-only storage, not encryption; fail closed elsewhere.

    Dedicated directory + O_NOFOLLOW prevent reads/writes through secret symlinks.
    A nonblocking process lock prevents refresh/connect/disconnect races.
    """
    def __init__(self, profile):
        self.directory = os.path.join(profile, 'real-debrid-private')

    def prepare(self):
        if os.name != 'posix' or not hasattr(os, 'O_NOFOLLOW'):
            raise DebridError('storage')
        os.makedirs(self.directory, mode=0o700, exist_ok=True)
        info = os.lstat(self.directory)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise DebridError('storage')

    def open_private(self, name, flags):
        fd = os.open(os.path.join(self.directory, name), flags | os.O_NOFOLLOW, 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
            os.close(fd)
            raise DebridError('storage')
        return fd

    @contextmanager
    def locked(self):
        self.prepare()
        import fcntl
        fd = self.open_private('lock', os.O_CREAT | os.O_RDWR)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise DebridError('busy') from None
            yield self
        finally:
            os.close(fd)

    def load(self):
        self.prepare()
        try:
            fd = self.open_private('credentials.json', os.O_RDONLY)
        except FileNotFoundError:
            return None
        try:
            with os.fdopen(fd) as stream:
                raw = stream.read(20000)
            value = json.loads(raw)
            for key in ('client_id', 'client_secret', 'access_token', 'refresh_token'):
                secret(value[key])
            number(value['expires_at'], 1e12)
            return value
        except (ValueError, KeyError, TypeError):
            raise DebridError('storage') from None

    def save(self, credentials):
        self.prepare()
        fd, path = tempfile.mkstemp(prefix='.credentials-', dir=self.directory)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(credentials, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(path, os.path.join(self.directory, 'credentials.json'))
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def clear(self):
        self.prepare()
        try:
            os.unlink(os.path.join(self.directory, 'credentials.json'))
        except FileNotFoundError:
            pass


class Client:
    def __init__(self, store, transport=request, clock=time.time):
        self.store, self.transport, self.clock = store, transport, clock

    def begin(self, client_id):
        if not client_id:
            raise DebridError('config')
        secret(client_id)
        result = self.transport('GET', OAUTH + 'device/code?' + urlencode({'client_id': client_id, 'new_credentials': 'yes'}))
        try:
            session = {'client_id': client_id, 'device_code': secret(result['device_code']),
                       'user_code': secret(result['user_code']),
                       'interval': max(5, number(result['interval'], 60)),
                       'expires_at': self.clock() + number(result['expires_in'], 3600)}
            if result['verification_url'] != 'https://real-debrid.com/device':
                raise DebridError('invalid')
            return session
        except (KeyError, TypeError):
            raise DebridError('invalid') from None

    def connect(self, session, wait, cancelled):
        """Caller holds store lock. wait returns true on shutdown/cancellation."""
        while self.clock() < session['expires_at']:
            if cancelled() or wait(min(session['interval'], session['expires_at'] - self.clock())) or cancelled():
                raise DebridError('cancelled')
            if self.clock() >= session['expires_at']:
                break
            try:
                pair = self.transport('GET', OAUTH + 'device/credentials?' + urlencode({'client_id': session['client_id'], 'code': session['device_code']}))
            except DebridError as error:
                # RD documents an error until authorization; 403 is pending only
                # at this endpoint. Rate/network failures stop rather than hammer.
                if error.kind == 'denied':
                    continue
                raise
            if isinstance(pair, dict) and 'error' in pair:
                raise DebridError('denied')
            try:
                pair = {k: secret(pair[k]) for k in ('client_id', 'client_secret')}
            except (KeyError, TypeError):
                raise DebridError('invalid') from None
            if cancelled():
                raise DebridError('cancelled')
            if self.clock() >= session['expires_at']:
                raise DebridError('expired')
            credentials = self.exchange(pair, session['device_code'])
            if cancelled() or self.clock() >= session['expires_at']:
                raise DebridError('cancelled')
            self.store.save(credentials)
            return
        raise DebridError('expired')

    def exchange(self, pair, code):
        result = self.transport('POST', OAUTH + 'token', dict(pair, code=code, grant_type=GRANT))
        try:
            if result['token_type'].lower() != 'bearer':
                raise DebridError('invalid')
            return dict(pair, access_token=secret(result['access_token']), refresh_token=secret(result['refresh_token']),
                        expires_at=self.clock() + number(result['expires_in'], 365 * 86400))
        except (KeyError, TypeError, AttributeError):
            raise DebridError('invalid') from None

    def token(self):
        credentials = self.store.load()
        if not credentials:
            raise DebridError('auth')
        if credentials['expires_at'] <= self.clock() + 60:
            pair = {k: credentials[k] for k in ('client_id', 'client_secret')}
            credentials = self.exchange(pair, credentials['refresh_token'])
            self.store.save(credentials)
        return credentials['access_token']

    def downloads(self, page=1):
        if type(page) is not int or not 1 <= page <= 10000:
            raise DebridError('invalid')
        result = self.transport('GET', API + 'downloads?' + urlencode({'page': page, 'limit': PAGE_SIZE}), token=self.token())
        if not isinstance(result, list):
            raise DebridError('invalid')
        return result

    def playback(self, item_id, page):
        # Re-read current account; plugin URLs contain IDs only, never signed URLs.
        for entry in self.downloads(page):
            if isinstance(entry, dict) and entry.get('id') == item_id:
                return web_url(entry.get('download'))
        raise DebridError('missing')

    def resolve_link(self, link):
        result = self.transport('POST', API + 'unrestrict/link', {'link': web_url(link), 'remote': '0'}, token=self.token())
        if not isinstance(result, dict):
            raise DebridError('invalid')
        return web_url(result.get('download'))

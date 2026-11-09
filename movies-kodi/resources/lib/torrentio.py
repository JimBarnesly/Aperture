"""Opt-in Torrentio RD adapter. Never log configuration, URLs or raw errors."""
import re
import os
import stat
import secrets
import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
import threading
import queue
from contextlib import contextmanager
from urllib.parse import unquote, urlsplit

ORIGIN = 'https://torrentio.strem.fun'


class ProviderError(Exception):
    """Only fixed, credential-free messages may cross the UI boundary."""
    def __init__(self, kind='invalid'):
        messages = {
            'invalid': 'Unsupported Torrentio configuration or response. Use HTTPS Torrentio with Real-Debrid only and exclude download links.',
            'network': 'Torrentio could not be reached safely. Retry later; redirects during lookup are not allowed.',
            'storage': 'Private local configuration is unavailable. Use a local, owner-only regular file; symbolic links are not accepted.',
            'missing': 'Set up online playback in Sources first. No Torrentio connection is saved.',
            'changed': 'That source is no longer available. Find streams again and choose a source.',
            'resolve': 'Torrentio did not return a supported HTTPS Real-Debrid download. No playback started. Retry later or choose another source.',
        }
        super().__init__(messages.get(kind, messages['invalid']))


class Config:
    def __init__(self, manifest):
        if not isinstance(manifest, str) or len(manifest) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in manifest):
            raise ProviderError()
        parsed = urlsplit(manifest)
        if parsed.scheme != 'https' or parsed.netloc != 'torrentio.strem.fun' or parsed.query or parsed.fragment:
            raise ProviderError()
        parts = parsed.path.split('/')
        if len(parts) != 3 or parts[2] != 'manifest.json':
            raise ProviderError()
        decoded = unquote(parts[1])
        options = {}
        allowed = {'realdebrid', 'debridoptions', 'providers', 'sort', 'qualityfilter', 'sizefilter', 'limit', 'language'}
        for pair in decoded.split('|'):
            values = pair.split('=')
            if len(values) != 2 or values[0] in options or values[0] not in allowed or not re.fullmatch(r'[A-Za-z0-9_,.-]+', values[1]):
                raise ProviderError()
            options[values[0]] = values[1]
        if not re.fullmatch(r'[A-Za-z0-9_-]{10,256}', options.get('realdebrid', '')):
            raise ProviderError()
        if set(options.get('debridoptions', '').split(',')) not in ({'nodownloadlinks'}, {'nodownloadlinks', 'nocatalog'}):
            raise ProviderError()
        self._manifest = manifest
        self._token = options['realdebrid']

    def lookup(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r'tt[0-9]{7,10}', identifier):
            raise ProviderError()
        return self._manifest[:-len('/manifest.json')] + '/stream/movie/' + identifier + '.json'


@contextmanager
def local_directory(path, create=False):
    """Walk from / with directory FDs: reject symlinks, including ancestors."""
    if not isinstance(path, str) or not path.startswith('/') or '\x00' in path or '..' in path.split('/'):
        raise ProviderError('storage')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in filter(None, path.split('/')):
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def read_private(fd, name):
    handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(handle, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1 or info.st_size > 4096:
            raise ProviderError('storage')
        data = stream.read(4097)
        if len(data) > 4096:
            raise ProviderError('storage')
        return data.decode('utf-8').rstrip('\r\n')


class Source:
    """Raw provider text/URLs never enter labels, reprs or navigation."""
    def __init__(self, url, label):
        self._url = url
        self.id = hashlib.sha256(url.encode('utf-8')).hexdigest()
        self.label = label


def strict_url(url):
    if not isinstance(url, str) or len(url) > 8192 or re.search(r'[\x00-\x20\x7f-\uffff|\\]', url):
        raise ProviderError()
    decoded = unquote(url)
    if re.search(r'[\x00-\x1f\x7f|\\%]', decoded) or any(p in ('.', '..') for p in urlsplit(decoded).path.split('/')):
        raise ProviderError()
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.fragment or parsed.port is not None:
        raise ProviderError()
    return parsed


def parse_streams(payload, config):
    if not isinstance(payload, dict) or not isinstance(payload.get('streams'), list) or len(payload['streams']) > 200:
        raise ProviderError()
    found = {}
    for entry in payload['streams']:
        if not isinstance(entry, dict) or any(key in entry for key in ('infoHash', 'sources', 'externalUrl', 'headers')):
            continue
        hints = entry.get('behaviorHints', {})
        if not isinstance(hints, dict) or set(hints) - {'bingeGroup', 'filename', 'videoSize', 'videoHash'}:
            continue
        name = entry.get('name', '')
        if not isinstance(name, str) or not name.startswith('[RD+]'):
            continue
        try:
            parsed = strict_url(entry.get('url'))
            if parsed.netloc != 'torrentio.strem.fun' or parsed.query:
                continue
            parts = parsed.path.split('/')
            if len(parts) not in (7, 8) or parts[1:3] != ['resolve', 'realdebrid'] or parts[3] != config._token:
                continue
            if not re.fullmatch('[a-fA-F0-9]{40}', parts[4]) or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', parts[5]) or not re.fullmatch(r'(?:null|[0-9]{1,6})', parts[6]):
                continue
            quality = re.search(r'(?i)\b(2160p|1080p|720p|480p|4k)\b', name)
            label = 'Real-Debrid · ' + (quality[0] if quality else 'quality unspecified')
            source = Source(entry['url'], label)
            found.setdefault(source.id, source)
        except (ProviderError, ValueError):
            continue
    return list(found.values())[:60]


class NetworkResponse:
    def __init__(self, connection, response, timer):
        self.connection, self.response, self.timer = connection, response, timer
        self.status, self.headers = response.status, response.headers

    def __enter__(self):
        return self

    def read(self, size):
        return self.response.read(size)

    def __exit__(self, *args):
        self.timer.cancel()
        self.response.close()
        self.connection.close()


def public_addresses(host):
    # Bound libc DNS without blocking Kodi indefinitely. The worker carries no token.
    result = queue.Queue(maxsize=1)
    def resolve():
        try:
            result.put(socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM))
        except OSError:
            result.put([])
    threading.Thread(target=resolve, daemon=True).start()
    try:
        addresses = result.get(timeout=5)
    except queue.Empty:
        raise ProviderError('network') from None
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ProviderError('network')
    return addresses


def request(url):
    """One HTTPS request, no proxies, no redirect engine, pinned public DNS."""
    connection = None
    timer = None
    try:
        # Config grammar permits pipe separators; encode only for HTTP transport.
        from urllib.parse import quote
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc != 'torrentio.strem.fun' or parsed.query or parsed.fragment:
            raise ProviderError()
        address = public_addresses(parsed.hostname)[0][4][0]
        connection = http.client.HTTPSConnection(parsed.hostname, timeout=10, context=ssl.create_default_context())
        connection._create_connection = lambda target, timeout, source_address=None: socket.create_connection((address, 443), timeout)
        connection.connect()
        sock = connection.sock
        def expire():
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        timer = threading.Timer(15, expire)
        timer.daemon = True
        timer.start()
        connection.request('GET', quote(parsed.path, safe='/%=,'), headers={'Accept': 'application/json', 'Accept-Encoding': 'identity', 'User-Agent': 'Aperture-Movies/1'})
        response = connection.getresponse()
        return NetworkResponse(connection, response, timer)
    except (OSError, ValueError, http.client.HTTPException, ProviderError):
        if timer:
            timer.cancel()
        if connection:
            connection.close()
        raise ProviderError('network') from None


class Client:
    def __init__(self, config, request=request):
        self.config, self._request = config, request

    def _json(self, url):
        try:
            with self._request(url) as response:
                if response.status != 200 or response.headers.get('Content-Encoding', 'identity') != 'identity':
                    raise ProviderError('network')
                if response.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise ProviderError()
                raw = response.read(512 * 1024 + 1)
                if len(raw) > 512 * 1024:
                    raise ProviderError()
                return json.loads(raw)
        except (OSError, ValueError, RecursionError, http.client.HTTPException):
            raise ProviderError('network') from None

    def check(self):
        manifest = self._json(self.config._manifest)
        if not isinstance(manifest, dict) or manifest.get('id') != 'com.stremio.torrentio.addon' or not isinstance(manifest.get('types'), list) or 'movie' not in manifest['types']:
            raise ProviderError()
        resources = manifest.get('resources', [])
        if not isinstance(resources, list) or not any(resource == 'stream' or isinstance(resource, dict) and resource.get('name') == 'stream' for resource in resources):
            raise ProviderError()

    def streams(self, identifier):
        return parse_streams(self._json(self.config.lookup(identifier)), self.config)

    def playback(self, identifier, source_id, cancelled=lambda: False):
        if cancelled():
            raise ProviderError('changed')
        if not isinstance(source_id, str) or not re.fullmatch('[a-f0-9]{64}', source_id):
            raise ProviderError('changed')
        selected = next((source for source in self.streams(identifier) if source.id == source_id), None)
        if selected is None or cancelled():
            raise ProviderError('changed')
        try:
            # Provider GET can mutate RD history/queue. Only after explicit Play.
            with self._request(selected._url) as response:
                if response.status != 302:
                    raise ProviderError('resolve')
                url = response.headers.get('Location')
                parsed = strict_url(url)
                if not re.fullmatch(r'[a-z0-9-]+\.download\.real-debrid\.com', parsed.netloc):
                    raise ProviderError('resolve')
                if not parsed.path.lower().endswith(('.mkv', '.mp4', '.avi', '.mov', '.m4v', '.webm', '.ts')):
                    raise ProviderError('resolve')
                public_addresses(parsed.hostname)
                # Kodi resolves this allowlisted hostname itself; DNS is rechecked
                # here but cannot be pinned across the player handoff.
                # Kodi CurlFile supports this option; no further redirects in player.
                return url + '|redirect-limit=0'
        except (OSError, ValueError, http.client.HTTPException):
            raise ProviderError('resolve') from None


class Store:
    def __init__(self, profile):
        self._directory = os.path.join(profile, 'torrentio-private')

    @contextmanager
    def _open(self, create=False):
        with local_directory(self._directory, create) as fd:
            info = os.fstat(fd)
            if info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ProviderError('storage')
            yield fd

    def load(self):
        try:
            with self._open() as fd:
                return Config(read_private(fd, 'connection'))
        except FileNotFoundError:
            return None
        except (OSError, UnicodeError, ValueError):
            raise ProviderError('storage') from None

    def import_file(self, path):
        try:
            with local_directory(os.path.dirname(path)) as fd:
                config = Config(read_private(fd, os.path.basename(path)))
            with self._open(create=True) as fd:
                try:
                    read_private(fd, 'connection')
                except FileNotFoundError:
                    pass
                name = '.new-' + secrets.token_hex(16)
                try:
                    output = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                    with os.fdopen(output, 'wb') as stream:
                        stream.write(config._manifest.encode('utf-8'))
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(name, 'connection', src_dir_fd=fd, dst_dir_fd=fd)
                    os.fsync(fd)
                finally:
                    try:
                        os.unlink(name, dir_fd=fd)
                    except FileNotFoundError:
                        pass
        except (OSError, UnicodeError, ValueError):
            raise ProviderError('storage') from None

    def clear(self):
        try:
            with self._open() as fd:
                read_private(fd, 'connection')
                os.unlink('connection', dir_fd=fd)
                os.fsync(fd)
        except FileNotFoundError:
            pass
        except (OSError, UnicodeError, ValueError):
            raise ProviderError('storage') from None

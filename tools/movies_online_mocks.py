"""Disposable native QA only. No provider traffic, credentials or usable media."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

OUT = Path(os.environ['APERTURE_MOVIES_OUT'])
RUNTIME = Path(os.environ['APERTURE_MOVIES_RUNTIME'])
assert RUNTIME.name.startswith('aperture-movies-qa.')

def record(event):
    with (OUT / 'mock-events.jsonl').open('a') as stream:
        stream.write(json.dumps({'event': event}) + '\n')

def catalogue(path):
    record('catalogue')
    movie = {'id': 'tt1234567', 'type': 'movie', 'name': 'Synthetic Online Horizon',
             'description': 'Original synthetic catalogue metadata. No playable stream.',
             'releaseInfo': '2026', 'genres': ['Adventure'], 'imdbRating': '7.5'}
    return {'meta': movie} if path.startswith('/meta/') else {'metas': [movie]}

def debrid(method, url, fields=None, token=None):
    # Only fake device-code and pending replies are supported. Even a mistaken
    # approval cannot exchange a token, access downloads or resolve a real URL.
    from resources.lib.debrid import DebridError
    path = urlsplit(url).path
    if method == 'GET' and path == '/oauth/v2/device/code':
        record('fake-device-code')
        return {'device_code': 'FAKE-DEVICE-NOT-VALID', 'user_code': 'QA-ONLY',
                'interval': 5, 'expires_in': 120,
                'verification_url': 'https://real-debrid.com/device'}
    if method == 'GET' and path == '/oauth/v2/device/credentials':
        record('fake-pending')
        raise DebridError('denied')
    record('unexpected-provider-operation')
    raise AssertionError('Unexpected operation blocked by disposable QA transport')

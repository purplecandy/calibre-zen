#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
One HTTPS POST to Sentry.

The official SDK is pure Python but wants `urllib3` and `certifi`, and the
bundle has neither. Sentry's ingest protocol is an envelope -- three lines of
JSON -- posted to one URL with one header, which is eighty lines against
calibre's own `HTTPSConnection` and the CA directory it already ships. The
same request talks to GlitchTip or a self-hosted Sentry, so the DSN is the
only thing that would change.

A send runs on its own thread with a short timeout and is dropped if it fails.
A crash reporter that queues and retries is a second bug surface, and a report
that arrives late is worth less than the UI staying responsive now.

The DSN is public by design. Sentry rate-limits per key and the key can be
rotated; it grants no read access to anything.

    CALIBRE_ZEN_REPORT_DRY=<path>   write envelopes there instead of sending
"""

import json
import os
import ssl
import sys
import threading
from urllib.parse import urlsplit

DSN = 'https://d9bd222e394c9233451e3f8fb8d29a26@o4512109070057472.ingest.de.sentry.io/4512109080281168'
TIMEOUT = 8
DRY_ENV = 'CALIBRE_ZEN_REPORT_DRY'


def parse_dsn(dsn: str = DSN) -> dict:
    p = urlsplit(dsn)
    project = p.path.rstrip('/').rsplit('/', 1)[-1]
    prefix = p.path.rstrip('/')[: -len(project) - 1]
    return {
        'key': p.username or '',
        'host': p.hostname or '',
        'port': p.port or 443,
        'project': project,
        'path': f'{prefix}/api/{project}/envelope/',
    }


def envelope(event: dict, dsn: str = DSN) -> bytes:
    "Header, item header, item: newline-separated JSON, one item per envelope."
    body = json.dumps(event, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    header = json.dumps({'event_id': event['event_id'], 'sent_at': event['timestamp'], 'dsn': dsn}).encode('utf-8')
    item = json.dumps({'type': 'event', 'content_type': 'application/json', 'length': len(body)}).encode('utf-8')
    return b'\n'.join((header, item, body, b''))


def user_agent() -> str:
    from calibre.constants import zen_version

    return f'calibre-zen/{zen_version}'


def auth_header(key: str) -> str:
    return f'Sentry sentry_version=7, sentry_client={user_agent()}, sentry_key={key}'


def connection(host: str, port: int, timeout: float = TIMEOUT):
    """
    calibre's HTTPSConnection, verified against the CA directory in the
    bundle's resources, through the user's proxy when there is one -- the same
    route calibre's own update check takes. Shared with update.py, which
    fetches the release feed from GitHub over it.
    """
    from calibre import get_proxies
    from calibre.utils.https import HTTPSConnection

    capath = ssl.get_default_verify_paths().capath
    kw = {'timeout': timeout}
    if capath and os.path.isdir(capath):
        kw['cadir'] = capath
    else:
        kw['context'] = ssl.create_default_context()
    proxies = get_proxies(debug=False)
    for scheme in ('https', 'http'):
        raw = proxies.get(scheme)
        if not raw:
            continue
        try:
            h, po = raw.rpartition(':')[::2]
            po = int(po)
        except ValueError:
            continue
        if h:
            conn = HTTPSConnection(h, po, **kw)
            conn.set_tunnel(host, port)
            return conn
    return HTTPSConnection(host, port, **kw)


def post(data: bytes, dsn: str = DSN) -> int:
    "Blocking. Returns the HTTP status, or 0 when nothing was sent."
    dry = os.environ.get(DRY_ENV)
    if dry:
        with open(dry, 'ab') as f:
            f.write(data)
        return 0
    d = parse_dsn(dsn)
    conn = connection(d['host'], d['port'])
    try:
        conn.request(
            'POST',
            d['path'],
            body=data,
            headers={
                'Content-Type': 'application/x-sentry-envelope',
                'Content-Length': str(len(data)),
                'X-Sentry-Auth': auth_header(d['key']),
                'User-Agent': user_agent(),
            },
        )
        resp = conn.getresponse()
        resp.read()
        return resp.status
    finally:
        conn.close()


def send(event: dict, *, block: bool = False) -> threading.Thread | int:
    """
    Send on a daemon thread and return it, or block and return the status.
    Failure of any kind is printed in debug builds and otherwise dropped.
    """
    data = envelope(event)

    def run():
        try:
            status = post(data)
            if status and status >= 400:
                _debug(f'calibre-zen: report rejected with HTTP {status}')
        except Exception as e:
            _debug(f'calibre-zen: report not sent: {e.__class__.__name__}: {e}')

    if block:
        return post(data)
    t = threading.Thread(target=run, name='zen-report', daemon=True)
    t.start()
    return t


def _debug(msg: str) -> None:
    from calibre.constants import DEBUG

    if DEBUG:
        print(msg, file=sys.stderr)

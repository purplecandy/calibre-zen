#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The host's secret: proof that a request comes from someone who can read
this person's calibre settings.

The same-machine rules in endpoints.py cannot tell the tray from a reverse
proxy on this computer that rewrites Host to 127.0.0.1 and adds no
forwarding header. Through such a proxy anyone could stop the host and read
its full status, paths included. So the host makes a random token when it
starts and writes it to a file in calibre's config folder that only this
user can read. The tray and launch.py read it and send it in a header; a
proxy's visitors cannot.

    POST /zen/stop     needs the token, as well as the same-machine rules
    GET /zen/status    the full answer needs the token or a login; anyone
                       else gets only that the host is up

The file holds one line and is replaced at every start. The host removes it
when it stops, but only if it still holds that host's token: a host that
crashed leaves its file behind, and the next one simply writes a new one.
"""

import hmac
import os
import secrets

HEADER = 'X-Zen-Token'
FILE_NAME = 'zen-host.token'


def path(config_dir: str | None = None) -> str:
    if config_dir is None:
        from calibre.constants import config_dir

    return os.path.join(config_dir, FILE_NAME)


def create(config_dir: str | None = None) -> str:
    "A new token, written where only this user can read it. Returns it."
    token = secrets.token_urlsafe(32)
    dest = path(config_dir)
    tmp = f'{dest}.{os.getpid()}.tmp'
    # Made with 0600 from the start, so the token is never readable by others,
    # not even between open() and a chmod().
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(token + '\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, dest)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return token


def read(config_dir: str | None = None) -> str:
    "The current host's token, or '' when there is none or it cannot be read."
    try:
        with open(path(config_dir)) as f:
            return f.read().strip()
    except OSError:
        return ''


def remove(token: str, config_dir: str | None = None) -> None:
    "Remove the file, if it still holds `token`."
    if token and matches(token, read(config_dir)):
        try:
            os.remove(path(config_dir))
        except OSError:
            pass


def matches(expected: str, given: str | None) -> bool:
    "Constant time, so the answer's timing says nothing about how much matched."
    if not expected or not given:
        return False
    return hmac.compare_digest(expected.encode('utf-8'), given.encode('utf-8'))

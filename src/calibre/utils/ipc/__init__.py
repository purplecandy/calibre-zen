#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid@kovidgoyal.net>

import errno
import os
from functools import lru_cache

from calibre.constants import __appname__, filesystem_encoding, get_windows_username, islinux, iswindows

VADDRESS = None


def eintr_retry_call(func, *args, **kwargs):
    while True:
        try:
            return func(*args, **kwargs)
        except OSError as e:
            if getattr(e, 'errno', None) == errno.EINTR:
                continue
            raise


@lru_cache
def socket_address(which):
    from calibre import force_unicode
    from calibre.utils.filenames import ascii_filename

    # calibre-zen: derived from __appname__ rather than spelled out, so this
    # fork does not land on the same endpoint as a calibre running beside it.
    # Upstream hardcodes 'calibre' here while deriving the single-instance lock
    # from __appname__, so the two disagreed: the lock let both apps start, and
    # then Listener.start_listening answered AddressInUseError by calling
    # removeServer() -- whichever started second silently took over the other's
    # socket, and "open in calibre" from the file manager went to the wrong one.
    if iswindows:
        ans = r'\\.\pipe' + '\\' + __appname__.title().replace('-', '') + which
        try:
            user = get_windows_username()
        except Exception:
            user = None
        if user:
            user = ascii_filename(user).replace(' ', '_')
            if user:
                ans += '-' + user[:100] + 'x'
    else:
        user = force_unicode(os.environ.get('USER') or os.path.basename(os.path.expanduser('~')), filesystem_encoding)
        if islinux:
            sock_name = '{}-{}-{}.socket'.format(ascii_filename(user).replace(' ', '_'), __appname__, which)
            ans = '\0' + sock_name
        else:
            ans = f'/tmp/{__appname__}-{os.getuid()}-{which}.sock'
    return ans


def gui_socket_address():
    return socket_address('GUI' if iswindows else 'gui')


def viewer_socket_address():
    return socket_address('Viewer' if iswindows else 'viewer')


def cyoa_socket_address():
    return socket_address('CYOA' if iswindows else 'cyoa')

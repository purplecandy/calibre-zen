#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Whether one of calibre's single-instance locks is held, asked without taking
it.

calibre.utils.lock.SingleInstance answers by taking the lock, which is wrong
here twice over. While the tray held it, even for a moment, a full app
starting at that instant would think another copy was running and quit. And
on macOS finding the lock file calls calibre.ptempfile.base_dir(), which
starts calibre's safe_atexit helper process: about 15 MB beside a tray that
otherwise sits near 40 MB. So this finds the same lock under the same name
and only looks at it:

    macOS     a lockf() lock on a file. F_GETLK says whether another process
              holds it. No file means nobody does: calibre deletes it on
              release
    Linux     an abstract unix socket. /proc/net/unix lists the bound ones
    Windows   a named mutex. OpenMutexW finds it without creating it, though
              it does hold a handle for the moment it takes to close it

`held()` answers False when it cannot tell. The host takes the `db` lock
itself and exits with status 3 when it is held, so a wrong False costs a
start that fails, never a library opened twice.
"""

import os
import sys

GUI = 'GUI'  # calibre.gui2.main.singleinstance_name: held while the full app runs
DB = 'db'  # held by whatever has the library open: the full app, a host, calibre-server


def full_name(name: str) -> str:
    "calibre.utils.lock.create_single_instance_mutex's name for `name`, per user."
    from calibre.constants import __appname__

    if sys.platform == 'win32':
        from calibre.constants import get_windows_username

        user = get_windows_username()
    else:
        user = os.geteuid()
    return f'{__appname__}-singleinstance-{user}-{name}'


def lock_file(name: str) -> str | None:
    """
    calibre.utils.lock.singleinstance_path, without its base_dir() call.
    That call only settles where the last fallback, the system's temporary
    folder, is. get_default_tempdir() finds the same folder without it. Not
    tempfile.gettempdir(): calibre points that at base_dir().
    """
    fname = full_name(name) + '.lock'
    home = os.path.expanduser('~')

    def system_temp():
        from calibre.ptempfile import get_default_tempdir

        return get_default_tempdir()

    locs = [lambda: '/var/lock', lambda: home, system_temp]
    if sys.platform == 'darwin':
        locs.insert(0, lambda: '/Library/Caches')
    for loc in locs:
        loc = loc()
        if os.access(loc, os.W_OK | os.R_OK | os.X_OK):
            return os.path.join(loc, ('.' if loc == home else '') + fname)
    return None


def held(name: str) -> bool:
    try:
        if sys.platform == 'win32':
            return _held_windows(full_name(name))
        if sys.platform.startswith('linux'):
            return _held_linux(full_name(name).replace(' ', '_'))
        path = lock_file(name)
        return path is not None and _held_file(path)
    except Exception:
        import traceback

        traceback.print_exc()
        return False


def _held_file(path: str) -> bool:
    import fcntl
    import struct

    try:
        fd = os.open(path, os.O_RDWR)  # never O_CREAT: no file is a free lock
    except OSError:
        return False
    try:
        if sys.platform == 'darwin':
            # struct flock on macOS: off_t l_start, off_t l_len, pid_t l_pid, short l_type, short l_whence
            fmt = 'qqihh'
            query = struct.pack(fmt, 0, 0, 0, fcntl.F_WRLCK, os.SEEK_SET)
            l_type = struct.unpack(fmt, fcntl.fcntl(fd, fcntl.F_GETLK, query))[3]
            return l_type != fcntl.F_UNLCK
        # Another BSD: the layout differs, so take the lock and give it straight back.
        try:
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        fcntl.lockf(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def _held_linux(name: str) -> bool:
    want = '@' + name
    try:
        with open('/proc/net/unix', 'rb') as f:
            lines = f.read().decode('utf-8', 'replace').splitlines()[1:]
    except OSError:
        return _held_linux_by_binding(name)
    return any(line.split()[-1:] == [want] for line in lines)


def _held_linux_by_binding(name: str) -> bool:
    "No /proc: bind the name and let it go at once, as calibre itself would find it."
    import errno
    import socket

    with socket.socket(family=socket.AF_UNIX) as s:
        try:
            s.bind('\0' + name)
        except OSError as e:
            return e.errno == errno.EADDRINUSE
    return False


def _held_windows(name: str) -> bool:
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    open_mutex = k32.OpenMutexW
    open_mutex.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
    open_mutex.restype = wintypes.HANDLE
    SYNCHRONIZE, ERROR_ACCESS_DENIED = 0x00100000, 5
    h = open_mutex(SYNCHRONIZE, False, name)
    if h:
        k32.CloseHandle(h)
        return True
    return ctypes.get_last_error() == ERROR_ACCESS_DENIED  # there, and someone else's

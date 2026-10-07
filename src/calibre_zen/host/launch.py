#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Starting, asking and stopping a host from another zen process.

`start` runs the host the way calibre_zen/reader/spare.py runs a spare reader
and calibre runs every worker: calibre's own worker executable
(calibre-parallel) with CALIBRE_SIMPLE_WORKER naming the entry point. It is
the headless one, so on macOS it comes from the bundle's console app, which
has no Dock icon, and the host's QApplication is the headless platform. From a
source tree CALIBRE_DEVELOP_FROM is inherited with the rest of the
environment, so the child runs this tree's Python; in a package the launcher
has already set it. The environment is Worker.env's without the parent's
temporary folder; `worker_env` says why.

`local_url`, `status` and `stop` use only the standard library and the light
option parser, so a tray can import this module without importing the server.
"""

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

ENTRY = 'calibre_zen.host.main:worker_main'
ARGS_ENV = 'CALIBRE_ZEN_HOST_ARGS'  # main.ARGS_ENV, without importing main


def worker_env(args: list[str]) -> dict[str, str]:
    """
    The environment calibre.utils.ipc.launch.Worker.env gives a worker, less
    one thing. Worker.env hands the child this process's temporary folder,
    which means calling calibre.ptempfile.base_dir() here: that makes the
    folder and starts calibre's safe_atexit helper process to delete it, about
    15 MB in a tray that wants to stay small. The host is better off without
    it anyway. It outlives whoever started it, so it makes its own temporary
    folder and cleans that up itself.
    """
    env = os.environ.copy()
    env.pop('CALIBRE_WORKER_TEMP_DIR', None)  # in case the caller is itself a worker
    env['CALIBRE_WORKER'] = '1'
    env['CALIBRE_SIMPLE_WORKER'] = ENTRY
    env[ARGS_ENV] = json.dumps(list(args))
    return env


def start(args: list[str], log_path: str | None = None) -> subprocess.Popen:
    """
    Start a host with these command-line arguments. Its output goes to
    `log_path` (appended), or to this process's own stdout and stderr.
    The caller owns the Popen: poll() it, and a return code of 3 means
    another calibre-zen program has the library open.
    """
    from calibre.constants import iswindows
    from calibre.utils.ipc.launch import headless_exe_path
    from calibre.utils.serialize import msgpack_dumps
    from polyglot.binary import as_hex_unicode

    exe = headless_exe_path('calibre-parallel')
    cmd = [exe] if isinstance(exe, (str, bytes)) else list(exe)
    env = worker_env(args)
    try:
        origwd = os.path.abspath(os.getcwd())
    except OSError:
        origwd = os.path.expanduser('~')
    env['ORIGWD'] = as_hex_unicode(msgpack_dumps(origwd))
    kwargs = {'env': env, 'stdin': subprocess.DEVNULL, 'close_fds': True}
    log = None
    if log_path is not None:
        log = open(log_path, 'ab')
        kwargs['stdout'] = log
        kwargs['stderr'] = subprocess.STDOUT
    if iswindows:
        from calibre.utils.ipc.launch import windows_creationflags_for_worker_process, windows_null_file

        # A server is not background work: normal priority, whatever
        # prefs['worker_process_priority'] says for conversions.
        kwargs['creationflags'] = windows_creationflags_for_worker_process('normal')
        if log is None:
            kwargs['stdout'] = windows_null_file
            kwargs['stderr'] = subprocess.STDOUT
    try:
        return subprocess.Popen(cmd, **kwargs)
    finally:
        if log is not None:
            log.close()  # the child has its own copy


def local_url(args: list[str] | None = None) -> str:
    """
    http://127.0.0.1:<port><url_prefix> for the host these arguments would
    start, with the Sharing settings as defaults. A host told to listen on one
    address is reached at that address instead.
    """
    from calibre_zen.host import options

    opts, _libraries = options.parse(args or [], options.light_parser())
    scheme = 'https' if opts.ssl_certfile and opts.ssl_keyfile else 'http'
    prefix = (opts.url_prefix or '').rstrip('/')
    if prefix and not prefix.startswith('/'):
        prefix = '/' + prefix
    return f'{scheme}://{options.local_address(opts)}:{int(opts.port)}{prefix}'


def _opener():
    # No proxies: a system proxy must never see a request for this computer.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def status(base_url: str, timeout: float = 2) -> dict | None:
    "GET /zen/status, or None if nothing answers there."
    try:
        with _opener().open(base_url.rstrip('/') + '/zen/status', timeout=timeout) as r:
            ans = json.loads(r.read())
    except OSError, ValueError, urllib.error.URLError:
        return None
    return ans if isinstance(ans, dict) else None


def port_is_open(base_url: str, timeout: float = 0.5) -> bool:
    parts = urlsplit(base_url)
    port = parts.port or (443 if parts.scheme == 'https' else 80)
    try:
        with socket.create_connection((parts.hostname or '127.0.0.1', port), timeout=timeout):
            return True
    except OSError:
        return False


def stop(base_url: str, timeout: float = 10) -> bool:
    """
    POST /zen/stop, then wait for the port to close. True once nothing is
    listening there any more, which includes when nothing was.
    """
    deadline = time.monotonic() + timeout
    req = urllib.request.Request(base_url.rstrip('/') + '/zen/stop', data=b'', method='POST')
    try:
        with _opener().open(req, timeout=min(timeout, 5)) as r:
            r.read()
    except urllib.error.HTTPError:
        return False  # it answered, and said no
    except OSError, urllib.error.URLError:
        pass  # nothing there, or it went away mid-answer
    while time.monotonic() < deadline:
        if not port_is_open(base_url):
            return True
        time.sleep(0.1)
    return not port_is_open(base_url)

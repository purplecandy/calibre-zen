#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The tray's entry point.

    calibre-debug -e src/calibre_zen/tray/__main__.py -- [--library PATH] [host options]

`--library PATH` is the tray's own. Everything else goes to the host as it
is, so calibre-server's flags (`--port`, `--enable-auth` and the rest) work
here too, and win over the Sharing settings as they do there.

One tray per config directory: a second one says so and leaves. The lock is
the tray's own, never calibre's `db` or `GUI` locks, which belong to whoever
holds the library.
"""

import os
import signal
import sys

from calibre_zen.reader import activation

LOCK_NAME = 'zen-tray'
LOG_NAME = 'zen-host.log'

USAGE = '''\
Usage: calibre-zen --headless [--library PATH] [calibre-server options]

Runs the host in the background, with an icon in the menubar or tray.
--library PATH   the library to share. Without it, the full app's libraries.
Any other option is calibre-server's, and is passed to the host.'''


def split_args(argv: list[str]) -> tuple[str | None, list[str]]:
    "(library, host arguments). Raises ValueError for a --library with no path."
    library, rest = None, []
    it = iter(argv)
    for a in it:
        if a == '--library':
            library = next(it, None)
            if not library:
                raise ValueError('--library needs a path')
        elif a.startswith('--library='):
            library = a.partition('=')[2]
            if not library:
                raise ValueError('--library needs a path')
        else:
            rest.append(a)
    if library:
        library = os.path.abspath(os.path.expanduser(library))
    return library, rest


def host_args(library: str | None, options: list[str]) -> list[str]:
    return list(options) + ([library] if library else [])


def log_path() -> str:
    from calibre.constants import cache_dir

    return os.path.join(cache_dir(), LOG_NAME)


def load_launch():
    "calibre_zen.host.launch, looked up when the tray starts so a test can pass its own."
    from calibre_zen.host import launch

    return launch


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if '-h' in argv or '--help' in argv:
        print(USAGE)
        return 0
    try:
        library, options = split_args(argv)
    except ValueError as e:
        print(f'calibre-zen: {e}', file=sys.stderr)
        return 2
    if activation.ismacos:
        # Read once, when the QApplication is made: without it Qt makes the
        # process a foreground app first, and a Dock icon flashes up.
        os.environ[activation.NO_FOREGROUND_ENV] = '1'

    lock = take_lock()
    if lock is None:
        print('calibre-zen: the menubar app is already running.', file=sys.stderr)
        return 0
    try:
        return run(library, options)
    finally:
        lock.unlock()


def lock_path() -> str:
    from calibre.constants import config_dir

    return os.path.join(config_dir, LOCK_NAME + '.lock')


def take_lock(path: str | None = None):
    """
    The tray's own lock, a QLockFile in the config directory: one tray per
    set of settings. Not calibre.utils.lock, which on macOS and Linux starts
    calibre's safe_atexit worker, a second process of about 15 MB, for a
    temporary directory the tray never uses. QLockFile also clears a lock
    left by a tray that crashed. Returns the held lock, or None.
    """
    from qt.core import QLockFile

    lock = QLockFile(path or lock_path())
    lock.setStaleLockTime(0)  # stale only when its process is gone, never by age
    return lock if lock.tryLock(0) else None


def run(library: str | None, options: list[str]) -> int:
    from qt.core import QApplication, QSystemTrayIcon, QTimer

    from calibre.constants import __appname__
    from calibre_zen.tray.keeper import Keeper
    from calibre_zen.tray.menu import Tray

    app = QApplication.instance() or QApplication([__appname__])
    app.setQuitOnLastWindowClosed(False)  # closing the folder dialog is not quitting
    activation.accessory()

    keeper = Keeper(load_launch(), host_args(library, options), log_path(), library)
    tray = Tray(keeper)
    if not QSystemTrayIcon.isSystemTrayAvailable() and os.environ.get('QT_QPA_PLATFORM') != 'offscreen':
        print('calibre-zen: this desktop has no tray. The library is still shared.', file=sys.stderr)
    tray.show()
    app.aboutToQuit.connect(keeper.shutdown)

    # Python runs a signal handler only between bytecodes, and Qt's event
    # loop is C++. The keeper's poll timer wakes Python every few seconds,
    # which is soon enough for a SIGTERM; the handler itself only queues.
    def on_signal(*_a):
        QTimer.singleShot(0, tray.quit)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, on_signal)
        except ValueError, OSError:
            pass

    keeper.start()
    return app.exec()

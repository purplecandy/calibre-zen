#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The preview build's entry point, run inside the application bundle.

A **preview** build is a copy of an installed calibre.app with the overlay
added to it -- see BUILDING.md. It is not the real build, and the difference
lives here: in a real build the fork's own `src/calibre` is compiled into the
bundle, so the identity in `calibre/constants.py` and `calibre/utils/ipc` is
simply true. A preview wraps a *stock* frozen calibre, where those modules are
upstream's, so the same identity has to be re-established at runtime.

Everything below therefore mirrors a specific place in the fork's source, and
`build-preview.sh` checks the two agree rather than trusting this comment:

    APPNAME              src/calibre/constants.py   __appname__
    socket_address()     src/calibre/utils/ipc/__init__.py
    the overlay hook     src/calibre/gui2/__init__.py  Application.__init__

The config directory is the exception: `calibre.constants` computes it at
import time, before anything here can run, so the launcher sets
CALIBRE_CONFIG_DIRECTORY instead.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The overlay ships beside this file rather than inside the frozen library:
# a built calibre has no Python source in it at all (freeze_python compiles
# every module into calibre-launcher.dylib), so this is how calibre_zen becomes
# importable at all.
sys.path.insert(0, HERE)

from calibre import constants  # noqa: E402

APPNAME = 'calibre-zen'
constants.__appname__ = APPNAME


def socket_address(which):
    "Mirrors src/calibre/utils/ipc/__init__.py."
    return f'/tmp/{APPNAME}-{os.getuid()}-{which}.sock'


def install_identity():
    """
    Keep this instance off a running calibre's IPC endpoint.

    Upstream derives the single-instance lock from __appname__ but hardcodes
    the socket, so the two disagree: the lock lets both applications start, and
    then Listener.start_listening answers AddressInUseError by calling
    removeServer() -- whichever started second takes the other's socket. These
    are replaced before calibre.gui2.listener imports them by name.
    """
    from calibre.utils import ipc

    ipc.socket_address = socket_address
    ipc.gui_socket_address = lambda: socket_address('gui')
    ipc.viewer_socket_address = lambda: socket_address('viewer')
    ipc.cyoa_socket_address = lambda: socket_address('cyoa')


def install_overlay():
    """
    Put the overlay where the fork's own source calls it from.

    `Application.__init__` calls it immediately after PaletteManager is
    constructed and before the palette is applied; wrapping the constructor
    puts it at exactly that point without needing the upstream line, which a
    frozen bundle does not have.
    """
    from calibre.gui2.palette import PaletteManager

    orig = PaletteManager.__init__

    def __init__(self, force_calibre_style, headless):
        orig(self, force_calibre_style, headless)
        if not headless:
            from calibre_zen.hooks import install

            install()

    PaletteManager.__init__ = __init__


def main():
    install_identity()
    install_overlay()
    if '--zen-selftest' in sys.argv:
        from calibre.utils.ipc import gui_socket_address
        from calibre.utils.lock import singleinstance_path

        print('appname   :', constants.__appname__)
        print('config dir:', constants.config_dir)
        print('cache dir :', constants.cache_dir())
        print('lock file :', singleinstance_path('GUI'))
        print('gui socket:', gui_socket_address())
        import calibre_zen

        print('overlay   :', os.path.dirname(calibre_zen.__file__))
        return 0
    from calibre.gui2.main import main as gui_main

    # Finder can append a process-serial-number argument on older systems;
    # calibre's option parser would reject it.
    args = [a for a in sys.argv[1:] if not a.startswith('-psn_')]
    return gui_main([APPNAME] + args)


raise SystemExit(main())

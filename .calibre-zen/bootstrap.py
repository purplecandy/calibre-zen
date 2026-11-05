# The development launcher's entry point.
#
# This instance's application identity -- "calibre-zen", and with it the
# single-instance lock, the cache directory, the IPC socket and the default
# config directory -- now comes from calibre.constants.__appname__ in the tree
# itself, because this is a fork rather than a skin over calibre. See
# src/calibre_zen/README.md, "A fork, not a skin".
#
# What is left here is only what belongs to *running from source*: debug mode,
# and a way to print the identity without starting a window.
import sys

from calibre import constants

constants.DEBUG = True

if '--zen-selftest' in sys.argv:
    from calibre.utils.ipc import gui_socket_address

    print('appname   :', constants.__appname__)
    print('config dir:', constants.config_dir)
    if constants.iswindows:  # a named mutex, not a file: there is no path to print
        print('lock      :', f'{constants.__appname__}-singleinstance-<user>-GUI')
    else:
        from calibre.utils.lock import singleinstance_path

        print('lock file :', singleinstance_path('GUI'))
    print('gui socket:', gui_socket_address())
    raise SystemExit(0)

from calibre.gui2.main import main  # noqa: E402

raise SystemExit(main([constants.__appname__] + sys.argv[1:]))

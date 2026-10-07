#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The three settings the tray's menu can change, read and written where the
full app keeps them, so both always agree.

    Share on this network            server-config.txt, listen_on: unset (every
                                     address) or 127.0.0.1 (this computer only)
    Allow changes from this computer server-config.txt, local_write
    Add books from a folder          gui.json, auto_add_path

server-config.txt is what Preferences, Sharing over the net writes, through
calibre.srv.opts. gui.json is calibre.gui2's gprefs, opened here as a plain
JSONConfig because importing calibre.gui2 costs more than the whole tray.
Each read goes back to the file: the full app may have changed it since.
"""

import os

# listen_on values that mean "this computer only".
LOCAL_ONLY = frozenset(('127.0.0.1', 'localhost', '::1'))
LOCAL_ADDRESS = '127.0.0.1'


def _server_config():
    from calibre.srv.opts import server_config

    return server_config(refresh=True)


def _change(**kw) -> None:
    from calibre.srv.opts import change_settings

    _server_config()  # change_settings starts from the cached copy; make it the file's
    change_settings(**kw)


def _gprefs():
    from calibre.utils.config import JSONConfig

    return JSONConfig('gui')


def share_on_network() -> bool:
    return (_server_config().listen_on or '') not in LOCAL_ONLY


def set_share_on_network(on: bool) -> None:
    # None is calibre's default: every IPv4 and IPv6 address.
    _change(listen_on=None if on else LOCAL_ADDRESS)


def allow_local_write() -> bool:
    return bool(_server_config().local_write)


def set_allow_local_write(on: bool) -> None:
    _change(local_write=bool(on))


def auto_add_folder() -> str | None:
    return _gprefs().get('auto_add_path') or None


def set_auto_add_folder(path: str | None) -> None:
    _gprefs().set('auto_add_path', os.path.abspath(path) if path else None)


def folder_problem(path: str, libraries=()) -> str | None:
    "Why calibre would refuse `path` as the auto-add folder, in words for a person, or None."
    from calibre.utils.localization import _

    name = os.path.basename(os.path.abspath(path))
    if not os.path.isdir(path) or not os.access(path, os.R_OK | os.W_OK):
        return _('That folder cannot be used. Pick one you can change.')
    if name[:1] in ('.', '_'):
        return _('Pick a folder whose name does not start with a dot or an underscore.')
    if any(inside(path, lib) or inside(lib, path) for lib in libraries if lib):
        return _('Pick a folder outside your library.')
    return None


def inside(path: str, directory: str) -> bool:
    "Whether `path` is `directory` or below it. calibre refuses an auto-add folder inside a library."
    try:
        path, directory = os.path.realpath(path), os.path.realpath(directory)
        return os.path.commonpath((path, directory)) == directory
    except ValueError:
        return False

#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
From the window to the menubar: "Close and keep sharing" in the Connect/share
menu, and "Restart in headless mode" in the Preferences menu, quit the full
app and start the tray, which serves the same library in the background.

The hook into quitting is calibre's own restart, the way upgrade.py installs
an update. Main.quit(restart=True) closes the library and leaves the event
loop, and calibre.gui2.main.main() calls restart_after_quit() once both
single-instance locks, `GUI` and `db`, are released. For this one quit that
name is rebound to start the tray instead. The tray then finds the library
free and starts its host at once, with none of the wait it keeps for a full
app that may be restarting. If the tray cannot start, calibre's restart runs
as it would have, so the worst case is the window back.

A tray that is already running, because the window was opened from it, is
not a problem: the new one says so and leaves, and the old one takes the
library back once the window has gone.
"""

import json
import os
import subprocess
import sys
import traceback

from calibre_zen.tray.keeper import GUI_CMD_ENV
from calibre_zen.tray.main import HELLO_ENV  # the tray says once that the library is still shared

LOG_NAME = 'zen-tray.log'

_installed = False


def enabled() -> bool:
    return os.environ.get('CALIBRE_ZEN_KEEP_SHARING', '1').lower() not in ('0', 'false', 'no', 'off')


def tray_command(library: str | None) -> list[str]:
    """
    The command that starts the tray, as the source launcher's --headless
    does: calibre-debug running tray/__main__.py. In a package the launcher
    has already set CALIBRE_DEVELOP_FROM, and the child inherits it.
    """
    from calibre.utils.ipc.launch import exe_path

    exe = exe_path('calibre-debug')
    cmd = [exe] if isinstance(exe, str) else list(exe)
    entry = os.path.join(os.path.dirname(os.path.abspath(__file__)), '__main__.py')
    return cmd + ['-e', entry, '--'] + (['--library', library] if library else [])


def own_command() -> list[str] | None:
    """
    How this window was started, when it ran from source through
    `calibre-debug -e bootstrap.py`. The tray reopens the window with it, so
    the window comes back from this tree in debug mode. None in a package,
    where the tray already runs calibre's own `calibre`.
    """
    exe, script = sys.executable or '', sys.argv[0] if sys.argv else ''
    if os.path.splitext(os.path.basename(exe))[0] == 'calibre-debug' and script.endswith('.py'):
        return [exe, '-e', os.path.abspath(script), '--']
    return None


def tray_env() -> dict:
    env = dict(os.environ)
    env[HELLO_ENV] = '1'
    if not env.get(GUI_CMD_ENV):
        cmd = own_command()
        if cmd:
            env[GUI_CMD_ENV] = json.dumps(cmd)
    return env


def log_path() -> str:
    from calibre.constants import cache_dir

    return os.path.join(cache_dir(), LOG_NAME)


def start_tray(library: str | None) -> subprocess.Popen:
    "Start the tray, detached, so it outlives this process."
    kw = {'env': tray_env(), 'stdin': subprocess.DEVNULL, 'close_fds': True}
    if os.name == 'nt':
        # calibre-debug.exe is a console program: without this a console window opens.
        kw['creationflags'] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kw['start_new_session'] = True
    with open(log_path(), 'wb') as log:
        return subprocess.Popen(tray_command(library), stdout=log, stderr=subprocess.STDOUT, **kw)


def arm(library: str | None, module=None):
    """
    Make the next restart_after_quit() start the tray instead of calibre
    again. Returns a function that undoes it, for a quit that did not happen.
    """
    gm = module or sys.modules.get('calibre.gui2.main')
    if gm is None or not callable(getattr(gm, 'restart_after_quit', None)):
        raise RuntimeError('calibre was not started through calibre.gui2.main')
    orig = gm.restart_after_quit

    def restart_after_quit():
        gm.restart_after_quit = orig
        try:
            start_tray(library)
        except Exception:
            traceback.print_exc()
            orig()

    gm.restart_after_quit = restart_after_quit
    return lambda: setattr(gm, 'restart_after_quit', orig)


def current_library(gui) -> str | None:
    "The library open in the window: the one the tray should share."
    path = getattr(getattr(gui, 'current_db', None), 'library_path', None)
    return path or None


def keep_sharing(gui, module=None) -> bool:
    """
    Quit through calibre's own quit, with the tray armed. False when the quit
    did not happen: the user kept the window open over running jobs.
    """
    try:
        disarm = arm(current_library(gui), module)
    except RuntimeError:
        traceback.print_exc()
        return False
    gui.quit(restart=True)
    if getattr(gui, 'shutting_down', False):
        return True
    disarm()
    return False


def tip_text() -> str:
    from calibre.utils.localization import _

    if sys.platform == 'darwin':
        return _('Close the window. Your library stays shared from the menubar.')
    return _('Close the window. Your library stays shared from the tray.')


def menu_text() -> tuple[str, str]:
    "The Connect/share item, and its tip."
    from calibre.utils.localization import _

    return _('Close and keep sharing'), tip_text()


GLYPH = 'moon'  # the window goes quiet, the library stays up


def icon():
    "The pack's moon, or calibre's server icon with no pack."
    from qt.core import QIcon

    from calibre_zen.icons import registry

    return registry.glyph_icon(GLYPH) or QIcon.ic('network-server.png')


def add_to_menu(action) -> None:
    "Put the item in the Connect/share menu, under the content server's own items."
    from qt.core import QAction

    menu = action.share_conn_menu
    text, tip = menu_text()
    ac = QAction(icon(), text, menu)
    ac.setStatusTip(tip)
    ac.setToolTip(tip)
    ac.triggered.connect(lambda: keep_sharing(action.gui))
    menu.insertAction(menu.control_smartdevice_action, ac)
    menu.keep_sharing_action = ac


def add_to_preferences(action) -> None:
    """
    Put the same thing in the Preferences menu, after calibre's own restarts,
    as a restart. create_menu_action registers it with the keyboard
    shortcuts, so it can be given one in Preferences -> Shortcuts.
    """
    from calibre.utils.localization import _

    menu = action.qaction.menu()
    ac = action.create_menu_action(
        menu,
        'zen_restart_headless',
        _('Restart in headless mode'),
        description=tip_text(),
        triggered=lambda: keep_sharing(action.gui),
    )
    ac.setIcon(icon())
    ac.setStatusTip(tip_text())
    menu.restart_headless_action = ac


def wrap_genesis(cls, add) -> None:
    orig = cls.genesis

    def genesis(self):
        orig(self)
        try:
            add(self)
        except Exception:
            # An extra item. It must never be the reason the menu fails to build.
            traceback.print_exc()

    cls.genesis = genesis


def install() -> bool:
    "Wrap the Connect/share and Preferences actions' genesis. Safe to call twice."
    global _installed
    if _installed or not enabled():
        return _installed
    from calibre.gui2.actions.device import ConnectShareAction
    from calibre.gui2.actions.preferences import PreferencesAction

    wrap_genesis(ConnectShareAction, add_to_menu)
    wrap_genesis(PreferencesAction, add_to_preferences)
    _installed = True
    return True

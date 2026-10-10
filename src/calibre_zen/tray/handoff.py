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

A tray that is already running, because the window was opened from it,
takes over instead: the window tells it (tray/channel.py) and it answers, so
no second tray is started. The other way round works too: a window opened
from the Dock while the tray is sharing asks for the library back before
calibre takes its lock, and waits behind a splash screen while the host
finishes. The window tells a running tray when it opens,
quits and restarts too, from any of calibre's ways of quitting, so the
tray's menu says what is happening at once instead of a few seconds later.
"""

import json
import os
import subprocess
import sys
import time
import traceback

from calibre_zen.tray import channel
from calibre_zen.tray.keeper import GUI_CMD_ENV
from calibre_zen.tray.main import HELLO_ENV  # the tray says once that the library is still shared

LOG_NAME = 'zen-tray.log'

_installed = False
_armed = False  # a Restart in headless mode is quitting the window
_tray_answered = False  # and a tray already running said it will take over


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
    global _armed, _tray_answered
    orig = gm.restart_after_quit

    def restart_after_quit():
        global _armed, _tray_answered
        gm.restart_after_quit = orig
        answered, _armed, _tray_answered = _tray_answered, False, False
        if answered:
            return  # a tray is running already, and takes over
        try:
            start_tray(library)
        except Exception:
            traceback.print_exc()
            orig()

    def disarm():
        global _armed, _tray_answered
        gm.restart_after_quit = orig
        _armed = _tray_answered = False

    gm.restart_after_quit = restart_after_quit
    _armed, _tray_answered = True, False
    return disarm


def tell_tray(gui) -> bool:
    """
    The window is shutting down: tell a running tray why. Called once the
    quit is certain, from Main.shutdown, which every way of quitting goes
    through. True when a tray answered.
    """
    global _tray_answered
    if _armed:
        message = channel.HANDOVER
    elif getattr(gui, 'restart_after_quit', False):
        message = channel.RESTARTING
    else:
        message = channel.CLOSING
    try:
        answered = channel.send(message)
    except Exception:
        traceback.print_exc()
        answered = False
    if _armed:
        _tray_answered = answered
    return answered


RELEASE_WAIT = 40  # seconds: the tray's stop timeout and exit timeout, and a little more
SPLASH_AFTER = 0.5  # seconds before the wait shows a splash screen


def take_library_back(wait: float = RELEASE_WAIT, held=None, send=None, splash=None) -> bool:
    """
    Before the window takes the library: if a tray's host has it, ask for it
    back and wait until it is free. A window opened from the Dock, a file or
    the command line while the tray is sharing gets the library instead of
    calibre's "Another calibre program ... is already running".

    Waits only when a tray says the library is its own, so a library held by
    something else, a calibre-server started by hand, shows calibre's
    message at once as before. Returns whether the library was given back.
    """
    from calibre_zen.tray import locks

    held = held or locks.held
    send = send or channel.send
    if not held(locks.DB):
        return False
    try:
        if not send(channel.RELEASE):
            return False
    except Exception:
        traceback.print_exc()
        return False
    start = time.monotonic()
    shown = None
    try:
        while held(locks.DB) and time.monotonic() - start < wait:
            # Usually free within a second. A host finishing an auto-add can
            # take longer, and then the splash says why nothing has opened.
            if shown is None and splash is not False and time.monotonic() - start > SPLASH_AFTER:
                shown = (splash or show_splash)()
            pump(0.1)
    finally:
        if shown:
            shown.close()
    return not held(locks.DB)


def show_splash():
    "The host is still finishing: say why nothing has opened yet."
    from calibre.gui2.splash_screen import SplashScreen
    from calibre.utils.localization import _

    sp = SplashScreen()
    sp.show()
    sp.show_message(_('Opening your library…'))
    return sp


def pump(seconds: float) -> None:
    from qt.core import QApplication, QEventLoop

    app = QApplication.instance()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if app is not None:
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
        time.sleep(0.02)


def wrap_run_gui(module) -> None:
    """
    calibre.gui2.main.run_gui takes the library's lock first thing, and
    main() looks the name up as a global, as it does restart_after_quit.
    """
    orig = module.run_gui

    def run_gui(*a, **kw):
        try:
            take_library_back()
        except Exception:
            traceback.print_exc()
        return orig(*a, **kw)

    module.run_gui = run_gui


def tell_tray_opened() -> None:
    try:
        channel.send(channel.OPENED)
    except Exception:
        traceback.print_exc()


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


def wrap_main(main) -> None:
    "Tell a running tray when the window is up, and when it shuts down."
    orig_initialize, orig_shutdown = main.initialize, main.shutdown

    def initialize(self, *a, **kw):
        ans = orig_initialize(self, *a, **kw)
        tell_tray_opened()
        return ans

    def shutdown(self, *a, **kw):
        try:
            return orig_shutdown(self, *a, **kw)
        finally:
            if not getattr(self, 'zen_told_tray', False):
                self.zen_told_tray = True
                tell_tray(self)

    main.initialize, main.shutdown = initialize, shutdown


def install() -> bool:
    "Wrap the Connect/share and Preferences actions' genesis, and Main. Safe to call twice."
    global _installed
    if _installed or not enabled():
        return _installed
    import calibre.gui2.main as gui_main
    from calibre.gui2.actions.device import ConnectShareAction
    from calibre.gui2.actions.preferences import PreferencesAction
    from calibre.gui2.ui import Main

    wrap_genesis(ConnectShareAction, add_to_menu)
    wrap_genesis(PreferencesAction, add_to_preferences)
    wrap_main(Main)
    wrap_run_gui(gui_main)
    _installed = True
    return True

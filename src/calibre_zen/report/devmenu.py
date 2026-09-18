#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Break things on purpose, from the running window.

A crash reporter is only testable by crashing, and the paths it covers -- the
main thread, a worker thread, a module that fails to install -- cannot be
reached from a headless script without faking the dialogs away. So with
CALIBRE_ZEN_DEVTOOLS=1 the appearance menu on the toolbar grows a Developer
submenu with one action per path, plus the negative case: an error raised in
calibre's own code, which must show calibre's dialog and no Send button.

Off by default; nothing here is imported unless the variable is set.
"""

import os
import threading

ENV = 'CALIBRE_ZEN_DEVTOOLS'
TEST_MODULE = 'devtest'


def enabled() -> bool:
    return os.environ.get(ENV, '') in ('1', 'true', 'yes', 'on')


class ZenTestError(RuntimeError):
    pass


def _raise_in_zen(where: str) -> None:
    "This frame is under calibre_zen/, which is what makes the report ours."
    raise ZenTestError(f'test error raised on purpose from Zen code ({where})')


def crash_main_thread() -> None:
    "Deferred one tick so it is unhandled -- through sys.excepthook, not the menu's slot."
    from qt.core import QTimer

    QTimer.singleShot(0, lambda: _raise_in_zen('main thread'))


def crash_worker_thread() -> None:
    t = threading.Thread(target=_raise_in_zen, args=('worker thread',), name='zen-devtest', daemon=True)
    t.start()


def crash_upstream() -> None:
    """
    The negative case. `functools.partial` has no Python frame, and
    `authors_to_string(5)` raises inside calibre, so the traceback carries no
    frame of ours and the dialog must be calibre's alone.
    """
    from functools import partial

    from qt.core import QTimer

    from calibre.ebooks.metadata import authors_to_string

    QTimer.singleShot(0, partial(authors_to_string, 5))


def fail_install() -> None:
    "Run a failing install through the guard, then offer it as the window would after startup."
    from calibre.gui2.ui import get_gui
    from calibre_zen import report
    from calibre_zen.report import guard

    def bad():
        raise AttributeError("type object 'BooksView' has no attribute 'frobnicate' (simulated)")

    guard.run_install(TEST_MODULE, bad)
    report.offer_install_failures(get_gui())
    # So the action can be used again in the same session.
    guard._states.pop(TEST_MODULE, None)


ACTIONS = (
    ('Crash in Zen code, main thread', crash_main_thread, 'Should show calibre\'s error dialog with a "Send report to Calibre Zen" button.'),
    ('Crash in Zen code, worker thread', crash_worker_thread, 'Should ask, in a question dialog, whether to send a background error.'),
    ('Crash in calibre code', crash_upstream, "Should show calibre's error dialog with no Send button: not ours."),
    ('Simulate a module install failure', fail_install, 'Should ask whether to send an install-failure report, with an "ask again" checkbox.'),
)


def attach(menu) -> None:
    "Add the Developer submenu to a QMenu. Idempotent per menu."
    if getattr(menu, '_zen_devmenu', None) is not None:
        return
    sub = menu.addMenu('Developer')
    for label, fn, tip in ACTIONS:
        action = sub.addAction(label)
        action.setToolTip(tip)
        action.setStatusTip(tip)
        action.triggered.connect(lambda _checked=False, f=fn: f())
    sub.setToolTipsVisible(True)
    menu._zen_devmenu = sub

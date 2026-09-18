#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Crash reports for the overlay's own code, and nothing else's.

calibre already funnels every unhandled GUI exception through one method,
`MainWindow.unhandled_exception`, which prints it and shows an error dialog
with a Copy button. Zen wraps it from outside and asks one question first:
is one of our frames on the stack? If not, the dialog is calibre's, untouched,
and nothing is built. If so, the same dialog appears with one more button,
Send report to Calibre Zen, and only that click sends anything.

Three wraps, no upstream file edited:

`MainWindow.unhandled_exception`
    Classifies the exception (`classify.py`) and, when it is ours, builds the
    event (`event.py`) and leaves it where the next wrap can see it, then lets
    calibre's handler run exactly as before.

`calibre.gui2.main_window.error_dialog`
    The name calibre's handler calls, rebound in that module. When an event is
    waiting it builds the same MessageBox calibre would and adds the button
    (`consent.py`). Otherwise it is the original.

`threading.excepthook`
    A crash on a worker thread has no dialog to add a button to. Ours is
    carried to the main thread over a Qt signal and asked about there.

`Main.initialize`
    Wrapped so that, once there is a window to ask from, the modules that
    failed to install (`guard.py`) are offered for sending.

The transport (`transport.py`) is one POST over calibre's own HTTPS client;
the SDK is not vendored. CALIBRE_ZEN_REPORT=0 turns all of it off.
"""

import os
import sys
import threading
import traceback

from calibre_zen.report import classify, consent, event, guard

_installed = False
_pending_event: dict | None = None
_bridge = None
OFFER_DELAY_MS = 2500


def enabled() -> bool:
    return os.environ.get('CALIBRE_ZEN_REPORT', '1') not in ('0', 'false', 'no', 'off')


def install() -> bool:
    "Wrap the four above. Safe to call twice. Needs a QApplication for the bridge."
    global _installed, _bridge
    if _installed or not enabled():
        return _installed
    from qt.core import QObject, QTimer, pyqtSignal

    from calibre.gui2 import main_window as mw_mod
    from calibre.gui2.ui import Main

    class Bridge(QObject):
        report_ready = pyqtSignal(object)

    _bridge = Bridge()
    _bridge.report_ready.connect(_on_background_event)

    orig_unhandled = mw_mod.MainWindow.unhandled_exception
    orig_error_dialog = mw_mod.error_dialog
    orig_thread_hook = threading.excepthook
    orig_initialize = Main.initialize

    def unhandled_exception(self, exc_type, value, tb):
        global _pending_event
        _pending_event = None
        if value is not None and classify.origin(value, tb) == classify.ZEN:
            try:
                _pending_event = event.build(value, tb)
            except Exception:
                traceback.print_exc()
        try:
            return orig_unhandled(self, exc_type, value, tb)
        finally:
            _pending_event = None

    def error_dialog(parent, title, msg, det_msg='', show=False, show_copy_button=True):
        ev = _pending_event
        if ev is None:
            return orig_error_dialog(parent, title, msg, det_msg=det_msg, show=show, show_copy_button=show_copy_button)
        from calibre.gui2.dialogs.message_box import MessageBox
        from calibre.utils.localization import _

        d = MessageBox(MessageBox.ERROR, _('ERROR:') + ' ' + title, msg, det_msg, parent=parent, show_copy_button=show_copy_button)
        consent.add_send_button(d, ev)
        if show:
            return d.exec()
        return d

    def excepthook(args):
        try:
            if args.exc_value is not None and classify.origin(args.exc_value, args.exc_traceback) == classify.ZEN:
                ev = event.build(args.exc_value, args.exc_traceback, mechanism_type='threading.excepthook')
                ev.setdefault('tags', {})['thread'] = getattr(args.thread, 'name', '') or 'worker'
                _bridge.report_ready.emit(ev)
        except Exception:
            traceback.print_exc()
        return orig_thread_hook(args)

    def initialize(self, *a, **kw):
        ans = orig_initialize(self, *a, **kw)
        try:
            QTimer.singleShot(OFFER_DELAY_MS, lambda: offer_install_failures(self))
        except Exception:
            traceback.print_exc()
        return ans

    mw_mod.MainWindow.unhandled_exception = unhandled_exception
    mw_mod.error_dialog = error_dialog
    threading.excepthook = excepthook
    Main.initialize = initialize
    _installed = True
    return True


def _on_background_event(ev: dict) -> None:
    "Main thread. A worker-thread crash in our code: ask, then send."
    try:
        from calibre.gui2.ui import get_gui

        parent = get_gui()
        if consent.ask_background(parent, ev):
            consent.send_now(ev)
    except Exception:
        traceback.print_exc()


def offer_install_failures(parent) -> int:
    """
    Offer the modules that did not install, once. Returns how many were sent.
    With the question's "ask again" unticked they go without asking.
    """
    events = guard.take_pending()
    if not events:
        return 0
    try:
        if consent.auto_send_install_failures() or consent.ask_install_failure(parent, events):
            for ev in events:
                consent.send_now(ev)
            return len(events)
    except Exception:
        traceback.print_exc()
    return 0


def debug_state() -> str:
    "For the log and the test: what is wrapped and what is waiting."
    return (
        f'report installed={_installed} enabled={enabled()} '
        f'modules={guard.states()} pending={len(guard.pending())} '
        f'thread_hook={threading.excepthook.__module__ if hasattr(threading.excepthook, "__module__") else "?"} '
        f'stderr={sys.stderr is not None}'
    )

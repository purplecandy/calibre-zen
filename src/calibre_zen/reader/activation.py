#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Who is allowed in the Dock, and who may take focus.

A spare reader is a GUI process nobody should see. On macOS that means no
Dock icon and no menu bar until it is handed a book, and on every platform it
means that, once it is handed one, the window it shows comes to the front even
though the click happened in another process.

Neither Qt nor calibre_extensions.cocoa has a call for an application's
activation policy, so the macOS half speaks to AppKit through the Objective-C
runtime with ctypes. Every function here is best effort: it returns whether it
did anything, and a failure costs focus or a Dock icon, never the reader.
"""

import ctypes
import sys

ismacos = sys.platform == 'darwin'
iswindows = sys.platform == 'win32'

# NSApplicationActivationPolicy
REGULAR, ACCESSORY, PROHIBITED = 0, 1, 2

# Qt makes every GUI process a foreground application while it starts --
# a Dock icon, a menu bar -- unless this is set. Read once, when the
# QApplication is constructed; spare.py sets it for the spare only.
NO_FOREGROUND_ENV = 'QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM'

_objc = None


def _runtime():
    global _objc
    if _objc is None:
        lib = ctypes.cdll.LoadLibrary('/usr/lib/libobjc.A.dylib')
        lib.objc_getClass.restype = ctypes.c_void_p
        lib.objc_getClass.argtypes = [ctypes.c_char_p]
        lib.sel_registerName.restype = ctypes.c_void_p
        lib.sel_registerName.argtypes = [ctypes.c_char_p]
        _objc = lib
    return _objc


def _send(receiver, selector: str, restype=ctypes.c_void_p, argtypes=(), *args):
    # objc_msgSend has to be called through the exact prototype of the method
    # it lands in -- on arm64 a variadic call puts the arguments in the wrong
    # registers -- so it is cast afresh for each signature.
    lib = _runtime()
    fn = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p, *argtypes)(ctypes.cast(lib.objc_msgSend, ctypes.c_void_p).value)
    return fn(receiver, lib.sel_registerName(selector.encode()), *args)


def _ns_app():
    cls = _runtime().objc_getClass(b'NSApplication')
    return _send(cls, 'sharedApplication') if cls else None


def _responds(receiver, selector: str) -> bool:
    sel = _runtime().sel_registerName(selector.encode())
    return bool(_send(receiver, 'respondsToSelector:', ctypes.c_bool, (ctypes.c_void_p,), sel))


def hide_from_dock() -> bool:
    "macOS: no Dock icon, no menu bar, no place in the app switcher. Call once the QApplication exists."
    if not ismacos:
        return False
    try:
        app = _ns_app()
        return bool(app) and bool(_send(app, 'setActivationPolicy:', ctypes.c_bool, (ctypes.c_long,), PROHIBITED))
    except Exception:
        return False


def come_forward() -> bool:
    "macOS: become an ordinary application again, and take the focus the main window yielded."
    if not ismacos:
        return False
    try:
        app = _ns_app()
        if not app:
            return False
        _send(app, 'setActivationPolicy:', ctypes.c_bool, (ctypes.c_long,), REGULAR)
        # Deprecated in macOS 14 in favour of -activate, which only succeeds
        # after the active application yields; both are fine to call, and the
        # yield is let_activate()'s half of the bargain.
        if _responds(app, 'activate'):
            _send(app, 'activate', None)
        _send(app, 'activateIgnoringOtherApps:', None, (ctypes.c_bool,), True)
        return True
    except Exception:
        return False


def let_activate(pid: int) -> bool:
    """
    Called by the process that has focus, for the one about to show a window.

    macOS 14 and later only lets an application activate itself when the
    active one has yielded to it; Windows only lets a process bring its window
    to the front when the foreground process has said it may. A freshly
    launched reader gets that for free from being launched; a spare that was
    started earlier does not.
    """
    try:
        if ismacos:
            app = _ns_app()
            running = _runtime().objc_getClass(b'NSRunningApplication')
            if not app or not running or not _responds(app, 'yieldActivationToApplication:'):
                return False
            target = _send(running, 'runningApplicationWithProcessIdentifier:', ctypes.c_void_p, (ctypes.c_int,), pid)
            if not target:
                return False
            _send(app, 'yieldActivationToApplication:', None, (ctypes.c_void_p,), target)
            return True
        if iswindows:
            return bool(ctypes.windll.user32.AllowSetForegroundWindow(ctypes.c_ulong(pid)))
    except Exception:
        pass
    return False

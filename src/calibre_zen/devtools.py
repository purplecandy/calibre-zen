#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Let calibre photograph itself, so reviewing the look costs the machine's owner
nothing.

Screenshotting from outside means raising the window and grabbing a rectangle
of the screen. That fails in three ways at once: it steals focus from whoever
is working, synthetic clicks and keystrokes land wherever the pointer happens
to be, and a region grab is not occlusion-proof -- whatever is on top of calibre
ends up in the file, which is somebody's mail or their folder names.

Qt can render a widget offscreen instead. `QWidget.grab()` needs no focus, is
unaffected by what is in front, cannot capture another application, and works on
a menu while it is open. This watches for a file and does exactly that.

Off unless CALIBRE_ZEN_SHOT_DIR is set, and it costs one timer tick even then.

    mkdir -p /tmp/zen && CALIBRE_ZEN_SHOT_DIR=/tmp/zen ./calibre-zen
    touch /tmp/zen/request          # -> /tmp/zen/00-Main.png, and a popup as 01-
"""

import os

POLL_MS = 400
REQUEST = 'request'
DONE = 'done'

_installed = False


def install() -> bool:
    """
    Called once the QApplication exists -- which is later than hooks.install(),
    since that runs while Application.__init__ is still assembling it and there
    is nothing yet to parent a timer to.
    """
    global _installed
    d = os.environ.get('CALIBRE_ZEN_SHOT_DIR', '')
    if _installed or not d:
        return _installed
    from qt.core import QTimer

    from calibre.gui2 import qapplication_or_fail

    app = qapplication_or_fail()
    _installed = True
    timer = QTimer(app)
    timer.setInterval(POLL_MS)
    timer.timeout.connect(lambda: _tick(d))
    timer.start()
    # Kept on the application so the timer is not garbage collected.
    app.zen_shot_timer = timer
    return True


def _tick(d: str) -> None:
    request = os.path.join(d, REQUEST)
    if not os.path.exists(request):
        return
    try:
        with open(request) as f:
            name = f.read().strip() or 'shot'
    except OSError:
        name = 'shot'
    try:
        os.remove(request)
    except OSError:
        return
    written = []
    try:
        written = grab(d, name)
    finally:
        with open(os.path.join(d, DONE), 'w') as f:
            f.write('\n'.join(written))


def grab(d: str, name: str) -> list:
    """
    Every visible top-level widget, largest first.

    Largest first puts the main window at 00 and anything floating above it --
    a dialog, or an open menu, which is a top-level widget in its own right --
    after it. Grabbing a menu is the whole reason this exists: a menu cannot be
    opened by a script without taking the pointer, but it can be photographed
    once a person has opened it.
    """
    from calibre.gui2 import qapplication_or_fail

    app = qapplication_or_fail()
    windows = [w for w in app.topLevelWidgets() if w.isVisible() and w.width() > 40 and w.height() > 20]
    windows.sort(key=lambda w: w.width() * w.height(), reverse=True)
    written = []
    for i, w in enumerate(windows):
        path = os.path.join(d, f'{name}-{i:02d}-{type(w).__name__}.png')
        try:
            if w.grab().save(path, 'PNG'):
                written.append(path)
        except Exception:
            continue
    return written

#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
A reader that is already running when a book is opened.

calibre starts a new process for every book it opens: Python, the viewer's
modules, an Application, a web engine, the window. Measured on a packaged
install that is about 1.5 s before the book itself is touched, and the book
takes 0.1 s on top -- under 0.6 s even the first time, when the whole book is
unpacked and prepared. Nearly all of the wait is the process.

So one is started ahead of time and kept out of sight, and View hands it the
book. Opening a book becomes one line written to a pipe and the book loading
in a reader that is already up. The spare is then an ordinary reader, and the
next one is started a few seconds later.

    spare.py       the main window's side: when to start one, when it is
                   stale, the hand-off, and the fallback to calibre's own launch
    warm.py        the spare's side: calibre's viewer, waiting with its window
                   unshown, and leaving without saving if it is never used
    activation.py  no Dock icon while waiting, and focus when shown

Two wraps, from outside, no upstream file edited:

`ViewAction.initialization_complete`
    Called once the main window has finished starting, which is when the
    first spare is scheduled.

`ViewAction._launch_viewer`
    The single place every "open this book in the reader" path ends up,
    with the path, the position and the book's library data already worked
    out. An internal reader with a book goes to the spare when there is one
    fit to take it; anything else -- no book, an external program, the LRF
    viewer, a stale or missing spare -- is calibre's own launch, unchanged.

Not used when the viewer's "single window" option is on: there every book
already goes to the reader that is open.

Costs one idle reader in memory for as long as the main window is open.
Off with `CALIBRE_ZEN_READER=0`, or Ready reader in the overlay's menu.
"""

import os

from calibre_zen import features
from calibre_zen.reader.warm import SPARE_ENV

_installed = False
_spare = None


def enabled() -> bool:
    return features.enabled('reader')


def current():
    "The main window's Spare, once it has one. (Not `spare()`: importing reader.spare would replace it.)"
    return _spare


def install() -> bool:
    global _installed
    if _installed:
        return True
    if os.environ.get(SPARE_ENV) or not enabled():
        return False
    from calibre.gui2.actions.view import ViewAction

    orig_complete = ViewAction.initialization_complete
    orig_launch = ViewAction._launch_viewer

    def initialization_complete(self):
        orig_complete(self)
        global _spare
        if _spare is None:
            from calibre_zen.reader.spare import FIRST_DELAY_MS, Spare

            _spare = Spare(self.gui)
            _spare.schedule(FIRST_DELAY_MS)

    def _launch_viewer(self, name=None, viewer='ebook-viewer', internal=True, calibre_book_data=None, open_at=None):
        if internal and name and viewer == 'ebook-viewer' and _spare is not None:
            try:
                handed = _spare.hand_off(name, open_at=open_at, book_data=calibre_book_data)
            except Exception:
                import traceback

                traceback.print_exc()
                handed = False
            if handed:
                return None
        return orig_launch(self, name=name, viewer=viewer, internal=internal, calibre_book_data=calibre_book_data, open_at=open_at)

    ViewAction.initialization_complete = initialization_complete
    ViewAction._launch_viewer = _launch_viewer
    _installed = True
    return True

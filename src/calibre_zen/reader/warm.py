#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The spare reader's side: calibre's own viewer, started early and kept out of sight.

This module is the entry point of the spare process. spare.py starts it the way
calibre starts any reader -- the viewer bundle's worker executable -- with
CALIBRE_SIMPLE_WORKER naming `main` below, so everything after that is
calibre's `gui_launch.ebook_viewer` running unchanged: the same Application,
the same web engine, the same preloaded render worker, the same window.

The differences, all in the one subclass `make_viewer` returns:

    show()       does nothing until there is a book. calibre's run_gui shows
                 the window as soon as it is built; the spare builds it and
                 waits.
    stdin        one line of JSON, the book and what calibre knows about it,
                 read on a thread and handed to the GUI thread. End of input
                 before that line means the main window has gone or has
                 retired this spare, and it leaves at once (see `abandon`).
    load_ebook() reveals the window the first time, by whatever route the book
                 arrived: the main window's line, or a file the system asked
                 this process to open.

After the reveal the process is an ordinary reader and lives as long as its
window, exactly as one calibre launched would.
"""

import json
import os
import sys
from threading import Thread

from calibre_zen.reader import activation

SPARE_ENV = 'CALIBRE_ZEN_READER_SPARE'


def debug(*args) -> None:
    from calibre.constants import DEBUG

    if DEBUG:
        print('calibre-zen reader:', *args, file=sys.stderr, flush=True)


def read_handoff(signals) -> None:
    "Runs on a thread. One message, then out; end of input before it means abandon."
    stream = sys.stdin.buffer
    try:
        line = stream.readline()
    except Exception:
        line = b''
    if not line.strip():
        signals.gone.emit()
        return
    try:
        msg = json.loads(line)
    except ValueError:
        debug('unreadable hand-off', line[:200])
        signals.gone.emit()
        return
    signals.book.emit(msg)


def make_viewer(base):
    from qt.core import QObject, Qt, pyqtSignal

    class Signals(QObject):
        book = pyqtSignal(object)
        gone = pyqtSignal()

    class SpareViewer(base):
        def __init__(self, *args, **kwargs):
            # Before anything can be shown: no Dock icon while waiting, and the
            # variable that kept Qt from adding one is not passed on to the
            # processes this one starts -- it is a reader once it is seen.
            activation.hide_from_dock()
            os.environ.pop(activation.NO_FOREGROUND_ENV, None)
            os.environ.pop(SPARE_ENV, None)
            self.zen_waiting = True
            super().__init__(*args, **kwargs)
            self.zen_signals = s = Signals(self)
            s.book.connect(self.zen_take, type=Qt.ConnectionType.QueuedConnection)
            s.gone.connect(self.zen_abandon, type=Qt.ConnectionType.QueuedConnection)
            Thread(target=read_handoff, args=(s,), name='ZenReaderHandoff', daemon=True).start()
            debug('waiting')

        def show(self):
            if self.zen_waiting:
                return
            super().show()

        def zen_reveal(self) -> None:
            if not self.zen_waiting:
                return
            self.zen_waiting = False
            activation.come_forward()
            super().show()
            debug('shown')

        def load_ebook(self, pathtoebook, open_at=None, reload_book=False):
            self.zen_reveal()
            return super().load_ebook(pathtoebook, open_at=open_at, reload_book=reload_book)

        def zen_take(self, msg) -> None:
            path = msg.get('path')
            if not path:
                return self.zen_abandon()
            if self.zen_waiting:
                # What calibre would have written to --internal-book-data: the
                # book's id, library and annotations, read once by load_finished.
                self.calibre_book_data_for_first_book = msg.get('book_data')
            debug('book', path)
            self.load_ebook(path, open_at=msg.get('open_at'))
            self.raise_and_focus()
            self.activateWindow()

        def zen_abandon(self) -> None:
            if not self.zen_waiting:
                return  # a reader now; its window decides when it ends
            debug('abandoned')
            abandon()

        def load_finished(self, ok, data):
            ans = super().load_finished(ok, data)
            debug('loaded' if ok else 'failed', data.get('pathtoebook', ''))
            return ans

    return SpareViewer


def abandon() -> None:
    """
    Leave without a word to disk.

    An unseen reader has nothing of its own to save, and a normal close would
    save anyway: the viewer writes its whole settings file from what it read at
    startup, which for a spare may be older than what another reader window has
    written since. Leaving through os._exit skips that. The render worker it
    preloaded is stopped first; the web engine's helpers follow their parent.
    """
    try:
        from calibre.gui2.viewer.convert_book import clean_running_workers

        clean_running_workers()
    except Exception:
        pass
    try:
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(0)


def main() -> None:
    "CALIBRE_SIMPLE_WORKER entry point, in the viewer bundle's worker executable."
    from calibre.gui2.viewer import main as viewer_main
    from calibre.gui_launch import ebook_viewer

    viewer_main.EbookViewer = make_viewer(viewer_main.EbookViewer)
    # --new-instance: a spare never takes the single-instance lock, so a
    # reader someone opens from the file manager is never sent to a window
    # nobody can see. spare.py does not use a spare when that option is on.
    ebook_viewer(['ebook-viewer', '--new-instance'])

#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The main window's side: one spare reader, started ahead of time and replaced when used.

`Spare` owns at most one waiting process. It is started a few seconds after
the main window is up, so it never competes with the library loading, and
again half a minute after each hand-off, so it never competes with the book
being read. A hand-off is one line on the spare's stdin; after that the
process is an ordinary reader and nothing here keeps track of it.

A spare read its settings when it started. Two things can make that stale, and
either retires it and starts another once things are quiet:

    the viewer's settings file    another reader saved a font, a margin, its
                                  window size -- every reader writes the file
                                  when it closes
    the palette                   light, dark, dim or a scheme chosen in the
                                  main window; the spare is themed from gprefs
                                  at startup and has no reason to look again

On a new profile the very first reader migrates the old viewer's settings
on startup, which is a write to that file; if that reader is a spare, it
retires itself and the next one starts clean. Once per profile, and the cost
is one start nobody sees.

A spare that is stale, still starting, or gone is never used: `hand_off`
returns False and calibre launches a reader the way it always has. The worst
case is the stock speed, never the wrong settings.
"""

import json
import os
import subprocess

from qt.core import QFileSystemWatcher, QObject, QTimer

from calibre_zen.reader import activation
from calibre_zen.reader.warm import SPARE_ENV

FIRST_DELAY_MS = 4000  # after the main window has finished starting
REFILL_DELAY_MS = 3000  # after the spare went stale: a reader just closed or the palette changed
# After a hand-off: someone has just started reading, and a new reader's
# start -- a web engine, and in develop mode a JavaScript compile -- would
# take its CPU from the one they are reading in. Only one book in a few
# seconds goes without a spare, and it opens the way calibre always did.
HANDOFF_REFILL_DELAY_MS = 30000
MAX_FAILURES = 3  # spares that died unused before we stop starting them


def settings_path() -> str:
    from calibre.gui2.viewer.config import vprefs

    return vprefs.file_path


def settings_mtime() -> float | None:
    try:
        return os.stat(settings_path()).st_mtime
    except OSError:
        return None


def single_instance() -> bool:
    "The viewer's 'one window' option: every book goes to the reader already open, so a spare has nothing to add."
    from calibre.gui2.viewer.config import get_session_pref, vprefs

    vprefs.refresh()
    return bool(get_session_pref('singleinstance', False))


class Spare(QObject):
    def __init__(self, parent=None, extra_env=None, output=None):
        super().__init__(parent)
        self.process: subprocess.Popen | None = None
        self.started_with: float | None = None  # settings_mtime() when the spare was started
        self.failures = 0
        self.extra_env = dict(extra_env or {})
        self.output = output  # where the spare's stdout and stderr go; inherited when None
        self.timer = t = QTimer(self)
        t.setSingleShot(True)
        t.timeout.connect(self.start)
        self.watcher = w = QFileSystemWatcher(self)
        w.fileChanged.connect(self.settings_changed)
        w.directoryChanged.connect(self.settings_changed)
        self.watch()
        from calibre.gui2 import qapplication_or_fail

        app = qapplication_or_fail()
        if hasattr(app, 'palette_changed'):
            app.palette_changed.connect(self.retire_and_refill)
        app.aboutToQuit.connect(self.shutdown)

    # Lifecycle {{{

    def schedule(self, delay_ms: int) -> None:
        self.timer.start(delay_ms)

    def is_ready(self) -> bool:
        p = self.process
        return p is not None and p.poll() is None and self.started_with == settings_mtime()

    def start(self) -> bool:
        if self.process is not None:
            if self.process.poll() is None:
                return False
            self.failures += 1  # it died without being used
            self.process = None
        if self.failures >= MAX_FAILURES or single_instance():
            return False
        try:
            self.process = launch(self.extra_env, self.output)
        except Exception:
            import traceback

            traceback.print_exc()
            self.failures += 1
            return False
        self.started_with = settings_mtime()
        self.watch()
        return True

    def retire(self) -> None:
        "Close the unused spare's input: it leaves at once, without saving anything (warm.abandon)."
        p, self.process = self.process, None
        if p is None:
            return
        try:
            if p.stdin is not None:
                p.stdin.close()
        except OSError:
            pass

    def retire_and_refill(self, *_args) -> None:
        self.retire()
        self.schedule(REFILL_DELAY_MS)

    def shutdown(self) -> None:
        self.timer.stop()
        self.retire()

    # }}}

    # Staleness {{{

    def watch(self) -> None:
        # The file is rewritten in place, which a watcher sees; but it may not
        # exist yet on a fresh profile, and an editor or a sync tool may
        # replace it, which drops the watch. The directory catches both.
        path = settings_path()
        wanted = [os.path.dirname(path)]
        if os.path.exists(path):
            wanted.append(path)
        have = set(self.watcher.files()) | set(self.watcher.directories())
        missing = [p for p in wanted if p not in have]
        if missing:
            self.watcher.addPaths(missing)

    def settings_changed(self, *_args) -> None:
        self.watch()
        if self.process is not None and self.started_with != settings_mtime():
            self.retire_and_refill()

    # }}}

    def hand_off(self, path: str, open_at=None, book_data=None) -> bool:
        """
        Give a book to the waiting spare. False when there is none fit to take
        it, and the caller launches a reader as calibre always has.
        """
        if not self.is_ready() or single_instance():
            if self.process is not None and self.process.poll() is None:
                self.retire()  # stale: replace it, and let this book take the normal road
            self.schedule(REFILL_DELAY_MS)
            return False
        p = self.process
        line = json.dumps({'path': path, 'open_at': open_at, 'book_data': book_data}) + '\n'
        activation.let_activate(p.pid)
        try:
            p.stdin.write(line.encode('utf-8'))
            p.stdin.flush()
            # The line is in the pipe before the end of it is, so closing now
            # costs the reader nothing, and it is no longer ours to retire.
            p.stdin.close()
        except OSError, ValueError:
            self.process = None
            self.failures += 1
            self.schedule(REFILL_DELAY_MS)
            return False
        self.process = None
        self.schedule(HANDOFF_REFILL_DELAY_MS)
        return True


def launch(extra_env=None, output=None) -> subprocess.Popen:
    """
    Start a spare the way calibre starts a reader -- calibre.utils.ipc.launch's
    Worker, with the viewer's executable and environment -- but with a pipe on
    stdin and warm.main as the entry point instead of a job.
    """
    from calibre.constants import ismacos, iswindows
    from calibre.utils.config import prefs
    from calibre.utils.ipc.launch import Worker, windows_creationflags_for_worker_process
    from calibre.utils.serialize import msgpack_dumps
    from polyglot.binary import as_hex_unicode

    env = {
        SPARE_ENV: '1',
        'CALIBRE_SIMPLE_WORKER': 'calibre_zen.reader.warm:main',
    }
    if ismacos:
        env[activation.NO_FOREGROUND_ENV] = '1'
    env.update(extra_env or {})
    w = Worker(env, gui=True, job_name='ebook-viewer')
    exe = w.gui_executable
    cmd = [exe] if isinstance(exe, (str, bytes)) else list(exe)
    env = w.env
    try:
        origwd = os.path.abspath(os.getcwd())
    except OSError:
        origwd = os.path.expanduser('~')
    env['ORIGWD'] = as_hex_unicode(msgpack_dumps(origwd))
    priority = prefs['worker_process_priority']
    kwargs = {'env': env, 'stdin': subprocess.PIPE, 'close_fds': True}
    if iswindows:
        from calibre.utils.ipc.launch import windows_null_file

        kwargs['creationflags'] = windows_creationflags_for_worker_process(priority)
        kwargs['stdout'] = windows_null_file
        kwargs['stderr'] = subprocess.STDOUT
    else:
        env['CALIBRE_WORKER_NICENESS'] = str({'normal': 0, 'low': 10, 'high': 20}[priority])
    if output is not None:
        kwargs['stdout'] = output
        kwargs['stderr'] = subprocess.STDOUT
    return subprocess.Popen(cmd, **kwargs)

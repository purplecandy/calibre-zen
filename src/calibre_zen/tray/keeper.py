#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The host's keeper: starts it, asks how it is, notices when it stops, and
starts it again.

The host is a child process (calibre_zen.host.launch.start). The keeper
never blocks the event loop on it: /zen/status is asked on a short-lived
thread, and stopping (POST /zen/stop, which waits for the port to close) runs
on one too. Only Popen.poll() and a look at the full app's lock run on the
GUI thread, and both take well under a millisecond.

A stop waits for the process as well as the port. Closing the port is the
first thing a host does on the way out; it then finishes its worker pools,
auto-add and the libraries. It is killed only after EXIT_TIMEOUT.

    starting   the process is up and has not answered yet
    sharing    /zen/status answered; `status` is its JSON
    paused     the full app holds the library. The full app's own `GUI` lock
               is held, the host exited with status 3, or the keeper started
               the full app itself and is waiting for it to quit. A quit is
               only believed once the lock has stayed free for GUI_GRACE
               seconds: calibre's restart quits the app and starts a new one
               about three seconds later, and a host started in between would
               take the library first. Status 3 is tried again every 10
               seconds, the lock looked at every 2
    stopped    the host exited for another reason; `reason` is the last line
               of its log. Tried again after 5, 10, 30, 60, 120, then every
               300 seconds
    opening    stopping the host to hand the library to the full app

`launch` is anything with calibre_zen.host.launch's four functions, and
`locks` anything with calibre_zen.tray.locks.held, so the tests can hand in
fakes.

A host outlives a tray that is force-quit or crashes, and keeps the library.
So the keeper writes down the pid and address of each host it starts, and a
new tray that finds a host still answering there with that pid stops it
before starting its own. Stopping it is simpler than adopting it: the keeper
then only ever looks after a process it started, and the new host reads the
current settings.
"""

import json
import os
import subprocess
import sys
import threading
import time

from qt.core import QObject, QTimer, pyqtSignal

from calibre_zen.reader import activation
from calibre_zen.tray import locks as default_locks

STARTING, SHARING, PAUSED, STOPPED, OPENING = 'starting', 'sharing', 'paused', 'stopped', 'opening'

# The host's exit status when another process -- the full app -- holds the library.
LIBRARY_BUSY = 3

GUI_CMD_ENV = 'CALIBRE_ZEN_GUI_CMD'
# Environment the tray sets for itself that the full app must not inherit.
NOT_FOR_THE_GUI = (activation.NO_FOREGROUND_ENV, 'CALIBRE_ZEN_HOST_ARGS', 'CALIBRE_SIMPLE_WORKER')


def gui_command(library: str | None = None) -> list[str]:
    """
    The command that opens the full app.

    The development launcher sets CALIBRE_ZEN_GUI_CMD to a JSON list. A
    package does not: every package's launcher only sets CALIBRE_DEVELOP_FROM
    and CALIBRE_ZEN_PACKAGED before running calibre's own `calibre`, and the
    tray already runs with both, so it runs that same executable beside its
    own and the child inherits them.
    """
    import json

    raw = os.environ.get(GUI_CMD_ENV)
    cmd = None
    if raw:
        try:
            cmd = [str(x) for x in json.loads(raw)]
        except ValueError, TypeError:
            cmd = None
    if not cmd:
        from calibre.utils.ipc.launch import exe_path

        exe = exe_path('calibre')
        cmd = [exe] if isinstance(exe, str) else list(exe)
    if library and '--with-library' not in cmd:
        cmd += ['--with-library', library]
    return cmd


def gui_env() -> dict:
    env = dict(os.environ)
    for k in NOT_FOR_THE_GUI:
        env.pop(k, None)
    return env


def last_line(path: str | None, offset: int = 0, limit: int = 80) -> str:
    "The last non-blank line written to `path` after `offset`, shortened to `limit`."
    if not path:
        return ''
    try:
        with open(path, 'rb') as f:
            size = f.seek(0, os.SEEK_END)
            start = offset if offset <= size else 0  # truncated since: it is all new
            f.seek(max(start, size - 8192))
            raw = f.read().decode('utf-8', 'replace')
    except OSError:
        return ''
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return ''
    line = lines[-1]
    return line if len(line) <= limit else line[: limit - 1] + '…'


class Keeper(QObject):
    changed = pyqtSignal()
    _status_ready = pyqtSignal(int, object)
    _stopped = pyqtSignal(int)

    POLL_MS = 3000
    STARTING_POLL_MS = 500
    PAUSED_RETRY_MS = 10_000
    BACKOFF_MS = (5_000, 10_000, 30_000, 60_000, 120_000, 300_000)
    GUI_GRACE = 8  # seconds the full app's lock stays free before the host starts
    GUI_POLL_MS = 2000  # how often the lock is looked at while the full app is open
    STOP_TIMEOUT = 10  # seconds launch.stop waits for the port to close
    # Closing the port is the first thing a host does on the way out. Then it
    # waits for its worker pools, auto-add and the libraries, which can take a
    # while mid-add. Only after this long is it killed.
    EXIT_TIMEOUT = 25

    def __init__(
        self,
        launch,
        args: list[str],
        log_path: str | None = None,
        library: str | None = None,
        popen=None,
        locks=None,
        record_path: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.launch = launch
        self.locks = locks or default_locks
        self.record_path = record_path
        self.args = list(args)
        self.log_path = log_path
        self.library = library
        self.popen = popen or subprocess.Popen
        self.state = STARTING
        self.status: dict | None = None  # the last answer, kept while paused or stopped for the library line
        self.reason = ''
        self.url = ''
        self.proc = None
        self.gui_proc = None
        self.failures = 0
        self.log_offset = 0
        self.generation = 0  # bumped whenever the process changes, so a late answer about the old one is dropped
        self.asking = False
        self.busy = False  # a stop is running on a thread
        self.on_stopped = None
        self.stopper: threading.Thread | None = None
        self.quitting = False
        self.settling = False  # the full app was open: wait for its lock to stay free
        self.free_since: float | None = None
        self.leftover = self._recall()  # a host a crashed tray left running

        self.poll_timer = t = QTimer(self)
        t.timeout.connect(self.tick)
        self.retry_timer = r = QTimer(self)
        r.setSingleShot(True)
        r.timeout.connect(self.start)
        self._status_ready.connect(self._got_status)
        self._stopped.connect(self._finished_stopping)

    # State {{{

    def _set(self, state: str, reason: str = '') -> None:
        self.state, self.reason = state, reason
        self._pace()
        self.changed.emit()

    def _pace(self) -> None:
        ms = self.STARTING_POLL_MS if self.state == STARTING else self.POLL_MS
        if not self.poll_timer.isActive() or self.poll_timer.interval() != ms:
            self.poll_timer.start(ms)

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def address(self) -> str:
        "The address a phone on the network would use, else this computer's."
        urls = (self.status or {}).get('urls') or []
        return urls[0] if urls else self.url

    # }}}

    # Starting and noticing {{{

    def start(self) -> bool:
        if self.quitting or self.busy or self.running():
            return False
        if self.gui_proc is not None and self.gui_proc.poll() is None:
            return False
        if self.leftover is not None:
            rec, self.leftover = self.leftover, None
            self._background(lambda: self._retire(rec), self.start, STARTING)
            return False
        if not self._app_gone():
            if self.state != PAUSED:
                self._set(PAUSED)
            self.retry_timer.start(self.GUI_POLL_MS)
            return False
        self.retry_timer.stop()
        self.generation += 1
        try:
            self.url = self.launch.local_url(self.args)
            try:
                self.log_offset = os.path.getsize(self.log_path) if self.log_path else 0
            except OSError:
                self.log_offset = 0
            self.proc = self.launch.start(self.args, self.log_path)
            self._remember(self.proc.pid, self.url)
        except Exception as e:
            import traceback

            traceback.print_exc()
            self.proc = None
            self._failed(str(e) or e.__class__.__name__)
            return False
        # Still paused while trying again: flicking to "Starting" every ten
        # seconds while the full app is open says nothing useful.
        if self.state != PAUSED:
            self._set(STARTING)
        else:
            self._pace()
        return True

    def _app_gone(self) -> bool:
        """
        True when the full app is not running and has not been for GUI_GRACE
        seconds, by its own `GUI` lock. Looked at before every start, so a
        full app opened from anywhere pauses the tray without a host that
        fails first.
        """
        if self.locks.held(default_locks.GUI):
            self.settling, self.free_since = True, None
            return False
        if not self.settling:
            return True
        now = time.monotonic()
        if self.free_since is None:
            self.free_since = now
        if now - self.free_since < self.GUI_GRACE:
            return False
        self.settling, self.free_since = False, None
        return True

    def tick(self) -> None:
        if self.busy or self.quitting:
            return
        if self.gui_proc is not None:
            if self.gui_proc.poll() is None:
                return
            # The full app quit. It may be restarting, and the new one takes
            # its lock a few seconds from now: start() waits that out.
            self.gui_proc = None
            self.settling, self.free_since = True, time.monotonic()
            self.start()
            return
        if self.proc is None:
            return
        rc = self.proc.poll()
        if rc is None:
            self._ask()
        else:
            self._exited(rc)

    def _ask(self) -> None:
        if self.asking:
            return
        self.asking = True
        gen, url, launch, ready = self.generation, self.url, self.launch, self._status_ready

        def ask():
            try:
                ans = launch.status(url)
            except Exception:
                ans = None
            ready.emit(gen, ans)

        threading.Thread(target=ask, name='zen-tray-status', daemon=True).start()

    def _got_status(self, gen: int, ans) -> None:
        self.asking = False
        if gen != self.generation or not self.running() or self.busy:
            return
        if isinstance(ans, dict):
            self.status = ans
            self.failures = 0
            self._set(SHARING)
        # No answer from a live process: still starting, or a slow moment. The
        # next tick asks again, and an exit is noticed by poll().

    def _exited(self, rc: int) -> None:
        self.proc = None
        self.generation += 1
        self._forget()
        if rc == LIBRARY_BUSY:
            self._set(PAUSED)
            self.retry_timer.start(self.PAUSED_RETRY_MS)
            return
        from calibre.utils.localization import _

        self._failed(last_line(self.log_path, self.log_offset) or _('It closed with code {}').format(rc))

    def _failed(self, reason: str) -> None:
        self.failures += 1
        self._set(STOPPED, reason)
        self.retry_timer.start(self.BACKOFF_MS[min(self.failures, len(self.BACKOFF_MS)) - 1])

    def try_again(self) -> None:
        "From the menu: do not wait for the backoff."
        self.failures = 0
        self.start()

    # }}}

    # Stopping {{{

    def _stop_proc(self, proc, url: str) -> None:
        """
        Blocking: ask nicely, give it EXIT_TIMEOUT to finish, then insist.
        A host that would not hear the request gets SIGTERM, which it treats
        as the same request, and the same time.
        """
        try:
            asked = bool(self.launch.stop(url, self.STOP_TIMEOUT))
        except Exception:
            asked = False
        if proc is None or proc.poll() is not None:
            return
        try:
            if not asked:
                proc.terminate()
            proc.wait(self.EXIT_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        except OSError:
            pass

    def _background(self, work, then, state: str) -> None:
        "Run `work` on a thread, then call `then` on this one. Nothing starts meanwhile."
        self.retry_timer.stop()
        self.generation += 1
        self.busy = True
        self.on_stopped = then
        self._set(state)
        gen, done = self.generation, self._stopped

        def run():
            try:
                work()
            except Exception:
                import traceback

                traceback.print_exc()
            finally:
                done.emit(gen)

        self.stopper = t = threading.Thread(target=run, name='zen-tray-stop', daemon=True)
        t.start()

    def stop_then(self, then=None, state: str = STARTING) -> None:
        """
        Stop the host on a thread, then call `then` on this one. Used for a
        restart (then=start) and for handing over to the full app.
        """
        proc, url = self.proc, self.url
        self.proc = None
        self._background(lambda: proc is not None and self._stop_proc(proc, url), then, state)

    def _finished_stopping(self, gen: int) -> None:
        self.busy = False
        self._forget()
        then, self.on_stopped = self.on_stopped, None
        if then is not None and not self.quitting:
            then()

    def restart(self) -> None:
        "After a setting changed: the host reads them once, at start."
        if self.gui_proc is not None and self.gui_proc.poll() is None:
            return  # it starts with the new settings when the full app quits
        self.failures = 0
        if self.state == PAUSED and not self.running():
            return  # the next retry reads them
        self.stop_then(self.start)

    def shutdown(self) -> None:
        "Quit: stop the host and wait for it. Blocks, which is fine on the way out."
        self.quitting = True
        self.poll_timer.stop()
        self.retry_timer.stop()
        proc, self.proc = self.proc, None
        if proc is not None and proc.poll() is None:
            self._stop_proc(proc, self.url)
        if self.busy and self.stopper is not None:
            # A restart or a hand-over was stopping it already. Let that finish,
            # or the host outlives the tray: the thread is a daemon.
            self.stopper.join(self.STOP_TIMEOUT + self.EXIT_TIMEOUT + 1)
        if not (self.stopper is not None and self.stopper.is_alive()):
            self._forget()

    # }}}

    # A host left behind {{{

    def _remember(self, pid: int, url: str) -> None:
        if not self.record_path:
            return
        try:
            with open(self.record_path, 'w') as f:
                json.dump({'pid': pid, 'url': url}, f)
        except OSError:
            pass

    def _forget(self) -> None:
        if not self.record_path:
            return
        try:
            os.remove(self.record_path)
        except OSError:
            pass

    def _recall(self) -> dict | None:
        if not self.record_path:
            return None
        try:
            with open(self.record_path) as f:
                rec = json.load(f)
        except OSError, ValueError:
            return None
        if isinstance(rec, dict) and isinstance(rec.get('pid'), int) and isinstance(rec.get('url'), str):
            return rec
        return None

    def _retire(self, rec: dict) -> None:
        """
        Blocking: stop the host a crashed tray left behind, if it is still
        there. Only the one with the recorded pid: a host someone started by
        hand, or another tray's, is left alone.
        """
        from calibre.constants import __appname__

        url, pid = rec['url'], rec['pid']
        try:
            ans = self.launch.status(url)
        except Exception:
            ans = None
        if not isinstance(ans, dict) or ans.get('app') != __appname__ or ans.get('pid') != pid:
            return
        try:
            self.launch.stop(url, self.STOP_TIMEOUT)
        except Exception:
            pass
        # Not a child, so there is no wait(): it is done once the library is free.
        deadline = time.monotonic() + self.EXIT_TIMEOUT
        while self.locks.held(default_locks.DB) and time.monotonic() < deadline and not self.quitting:
            time.sleep(0.1)

    # }}}

    # The full app {{{

    def open_gui(self) -> None:
        "Hand the library over: stop the host, start the full app, start the host again once it quits."
        if self.running() and not self.busy:
            self.stop_then(self._launch_gui, OPENING)
        elif not self.busy:
            self._launch_gui()

    def _launch_gui(self) -> None:
        self.retry_timer.stop()
        kw = {'env': gui_env()}
        if sys.platform != 'win32':
            kw['start_new_session'] = True  # quitting the tray leaves the full app alone
        try:
            self.gui_proc = self.popen(gui_command(self.library), **kw)
        except Exception as e:
            self.gui_proc = None
            self._failed(str(e) or e.__class__.__name__)
            return
        activation.let_activate(self.gui_proc.pid)
        self._set(PAUSED)

    # }}}

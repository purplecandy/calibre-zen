#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The menubar app: the keeper's states, the menu they show, and what each item
does. The host is a fake with calibre_zen.host.launch's four functions, and
calibre's single-instance locks are a fake too, so nothing here starts a
server, a full app, or a browser, or takes a lock another run could want.
"""

import json
import os
import subprocess
import sys
import threading
import time
import types
import unittest
from unittest import mock

from calibre_zen.tests.base import ZenTestCase, wait_until

STATUS = {
    'app': 'calibre-zen',
    'port': 8099,
    'url_prefix': '',
    'urls': ['http://192.168.1.18:8099/'],
    'auth': False,
    'local_write': False,
    'libraries': [
        {'id': 'Other', 'name': 'Other', 'path': '/nowhere/Other', 'open': False, 'books': None},
        {'id': 'Calibre_Library', 'name': 'Calibre Library', 'path': '', 'open': True, 'books': 2000},
    ],
    'jobs': {'running': 0, 'waiting': 0},
    'auto_add': None,
}

LOCAL_URL = 'http://127.0.0.1:8099'


class FakeProc:
    def __init__(self, pid=4242, cmd=None, kw=None):
        self.pid, self.cmd, self.kw = pid, cmd, kw or {}
        self.rc = None
        self.terminated = self.killed = False

    def poll(self):
        return self.rc

    def terminate(self):
        self.terminated = True
        if self.rc is None:
            self.rc = -15

    def kill(self):
        self.killed = True
        if self.rc is None:
            self.rc = -9

    def wait(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        while self.rc is None:
            if deadline is not None and time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired('calibre-parallel', timeout)
            time.sleep(0.005)
        return self.rc

    def exit_in(self, seconds, rc=0):
        "Like a host finishing its shutdown after the port has closed."
        threading.Timer(seconds, lambda: setattr(self, 'rc', rc) if self.rc is None else None).start()


class FakeLaunch:
    "calibre_zen.host.launch, with a process that does what the test says."

    def __init__(self):
        self.procs: list[FakeProc] = []
        self.started: list[list[str]] = []
        self.stopped: list[str] = []
        self.answer = None  # what /zen/status says while the latest process lives
        self.log_lines: list[str] = []  # written to the log by the next start
        self.linger = 0.0  # how long a stopped host takes to exit after its port closes
        self.others: dict[str, dict] = {}  # hosts this fake did not start, by address

    def start(self, args, log_path=None):
        if log_path and self.log_lines:
            with open(log_path, 'a') as f:
                f.write('\n'.join(self.log_lines) + '\n')
        p = FakeProc(pid=5000 + len(self.procs))
        self.procs.append(p)
        self.started.append(list(args))
        return p

    def local_url(self, args=None):
        return LOCAL_URL

    def status(self, base_url, timeout=2):
        if base_url in self.others:
            return self.others[base_url]
        if self.procs and self.procs[-1].rc is None:
            return self.answer
        return None

    def stop(self, base_url, timeout=10):
        self.stopped.append(base_url)
        if self.others.pop(base_url, None) is not None:
            return True
        if self.procs and self.procs[-1].rc is None:
            if self.linger:
                self.procs[-1].exit_in(self.linger)
            else:
                self.procs[-1].rc = 0
        return True

    @property
    def proc(self) -> FakeProc:
        return self.procs[-1]


class FakeLocks:
    "calibre_zen.tray.locks, with the locks the test says are held."

    def __init__(self):
        self.names: set[str] = set()
        self.asked: list[str] = []

    def held(self, name):
        self.asked.append(name)
        return name in self.names


class FakePopen:
    def __init__(self):
        self.calls: list[FakeProc] = []

    def __call__(self, cmd, **kw):
        p = FakeProc(pid=9000 + len(self.calls), cmd=list(cmd), kw=kw)
        self.calls.append(p)
        return p


class TrayTestCase(ZenTestCase):
    def setUp(self):
        from calibre_zen.reader import activation

        # Never touch AppKit from a test process: NSApplication would give it a Dock icon.
        for name in ('let_activate', 'accessory'):
            p = mock.patch.object(activation, name, return_value=False)
            p.start()
            self.addCleanup(p.stop)
        self.reset_settings()
        self.addCleanup(self.reset_settings)
        self.log = os.path.join(self.mkdtemp(), 'zen-host.log')

    def reset_settings(self):
        from calibre.srv.opts import DEFAULT_CONFIG, server_config
        from calibre_zen.tray import settings

        try:
            os.remove(DEFAULT_CONFIG)
        except OSError:
            pass
        server_config(refresh=True)
        settings.set_auto_add_folder(None)

    def make(self, library=None, args=(), choose=None, record=None):
        from calibre_zen.tray.keeper import Keeper
        from calibre_zen.tray.menu import Tray

        self.launch = FakeLaunch()
        self.popen = FakePopen()
        self.locks = FakeLocks()
        self.opened: list[str] = []
        self.quits = 0
        self.messages: list[str] = []
        self.record = record or os.path.join(self.mkdtemp(), 'zen-tray-host.json')
        kp = Keeper(self.launch, [*args, *([library] if library else [])], self.log, library, popen=self.popen, locks=self.locks, record_path=self.record)
        kp.POLL_MS = kp.STARTING_POLL_MS = 20
        kp.PAUSED_RETRY_MS = 150
        kp.BACKOFF_MS = (150, 300)
        kp.GUI_GRACE, kp.GUI_POLL_MS = 0.3, 20
        kp.STOP_TIMEOUT = kp.EXIT_TIMEOUT = 0.1

        def quit_app():
            self.quits += 1

        tray = Tray(kp, open_url=self.opened.append, choose_folder=choose or (lambda title, start: ''), quit_app=quit_app)
        tray.icon.showMessage = lambda title, msg, *a: self.messages.append(msg)
        self.keeper, self.tray = kp, tray
        self.addCleanup(self.cleanup)
        return kp, tray

    def cleanup(self):
        self.keeper.quitting = True
        self.keeper.poll_timer.stop()
        self.keeper.retry_timer.stop()
        self.tray.icon.hide()

    def sharing(self, answer=STATUS):
        from calibre_zen.tray import keeper as k

        self.launch.answer = answer
        self.keeper.start()
        self.assertTrue(wait_until(lambda: self.keeper.state == k.SHARING), self.keeper.state)


class TestKeeper(TrayTestCase):
    def test_starting_then_sharing(self):
        from calibre_zen.tray import keeper as k

        kp, tray = self.make()
        kp.start()
        self.assertEqual(kp.state, k.STARTING)
        self.assertEqual(tray.state_action.text(), 'Starting…')
        self.assertFalse(tray.browser_action.isEnabled())
        self.assertFalse(tray.copy_action.isEnabled())
        self.launch.answer = STATUS
        self.assertTrue(wait_until(lambda: kp.state == k.SHARING))
        self.assertEqual(tray.state_action.text(), 'Sharing at 192.168.1.18:8099')
        self.assertTrue(tray.browser_action.isEnabled())
        self.assertTrue(tray.copy_action.isEnabled())
        self.assertFalse(tray.retry_action.isVisible())
        self.assertFalse(tray.reason_action.isVisible())
        self.assertEqual(self.launch.started, [[]])

    def test_paused_on_exit_3_then_retry(self):
        from calibre_zen.tray import keeper as k

        kp, tray = self.make()
        self.sharing()
        self.launch.proc.rc = k.LIBRARY_BUSY
        self.assertTrue(wait_until(lambda: kp.state == k.PAUSED))
        self.assertEqual(tray.state_action.text(), 'Paused while Calibre Zen is open')
        self.assertFalse(tray.browser_action.isEnabled())
        for ac in (tray.share_action, tray.write_action, tray.auto_add_action):
            self.assertFalse(ac.isEnabled(), ac.text())
        # Still paused while it tries again and the full app still holds the library.
        self.launch.answer = None
        self.assertTrue(wait_until(lambda: len(self.launch.started) == 2))
        self.assertEqual(kp.state, k.PAUSED)
        self.launch.proc.rc = k.LIBRARY_BUSY
        self.assertTrue(wait_until(lambda: len(self.launch.started) == 3))
        # The full app quit: this try answers.
        self.launch.answer = STATUS
        self.assertTrue(wait_until(lambda: kp.state == k.SHARING))
        self.assertTrue(tray.share_action.isEnabled())

    def test_crash_shows_the_last_log_line_and_retries(self):
        from calibre_zen.tray import keeper as k

        with open(self.log, 'w') as f:
            f.write('an older run\nOld: not this one\n')
        kp, tray = self.make()
        self.launch.log_lines = ['Traceback (most recent call last):', '  File "x.py", line 1', 'OSError: [Errno 48] Address already in use', '']
        self.sharing()
        self.launch.proc.rc = 1
        self.assertTrue(wait_until(lambda: kp.state == k.STOPPED))
        self.assertEqual(kp.reason, 'OSError: [Errno 48] Address already in use')
        self.assertEqual(tray.state_action.text(), 'Sharing stopped')
        self.assertTrue(tray.reason_action.isVisible())
        self.assertEqual(tray.reason_action.text(), kp.reason)
        self.assertTrue(tray.retry_action.isVisible())
        self.assertIn(kp.reason, tray.icon.toolTip())
        # It tries again by itself, after the first backoff step.
        self.launch.log_lines = []
        self.assertTrue(wait_until(lambda: len(self.launch.started) == 2))
        self.assertTrue(wait_until(lambda: kp.state == k.SHARING))
        self.assertEqual(kp.failures, 0)

    def test_crash_with_an_empty_log_gives_the_code(self):
        from calibre_zen.tray import keeper as k

        kp, tray = self.make()
        kp.start()
        self.launch.proc.rc = 7
        self.assertTrue(wait_until(lambda: kp.state == k.STOPPED))
        self.assertEqual(kp.reason, 'It closed with code 7')

    def test_try_again_skips_the_backoff(self):
        from calibre_zen.tray import keeper as k

        kp, tray = self.make()
        kp.BACKOFF_MS = (60_000,)
        kp.start()
        self.launch.proc.rc = 1
        self.assertTrue(wait_until(lambda: kp.state == k.STOPPED))
        tray.retry_action.trigger()
        self.assertEqual(len(self.launch.started), 2)
        self.assertEqual(kp.state, k.STARTING)

    def test_last_line_reads_only_this_run(self):
        from calibre_zen.tray.keeper import last_line

        with open(self.log, 'w') as f:
            f.write('old line\n')
        offset = os.path.getsize(self.log)
        self.assertEqual(last_line(self.log, offset), '')
        with open(self.log, 'a') as f:
            f.write('new line\n\n')
        self.assertEqual(last_line(self.log, offset), 'new line')
        with open(self.log, 'w') as f:  # truncated by the new run
            f.write('x' * 200 + '\n')
        got = last_line(self.log, offset)
        self.assertEqual(len(got), 80)
        self.assertTrue(got.endswith('…'))
        self.assertEqual(last_line(os.path.join(self.tmp, 'missing.log')), '')


class TestMenu(TrayTestCase):
    def test_library_line(self):
        kp, tray = self.make()
        self.sharing()
        # No --library: the first library the host lists.
        self.assertEqual(tray.library_action.text(), 'Other')
        lib = self.mkdtemp()
        kp, tray = self.make(library=lib)
        status = json.loads(json.dumps(STATUS))
        status['libraries'][1]['path'] = lib
        self.sharing(status)
        self.assertEqual(tray.library_action.text(), 'Calibre Library, 2,000 books')
        self.assertEqual(self.launch.started, [[lib]])
        # Not sharing: the name, without a count that may be stale.
        self.launch.proc.rc = 3
        self.assertTrue(wait_until(lambda: tray.library_action.text() == 'Calibre Library'))

    def test_library_line_before_any_answer(self):
        lib = os.path.join(self.mkdtemp(), 'My Books')
        kp, tray = self.make(library=lib)
        kp.start()
        self.assertEqual(tray.library_action.text(), 'My Books')
        kp2, tray2 = self.make()
        self.assertFalse(tray2.library_action.isVisible())

    def test_one_book(self):
        kp, tray = self.make()
        status = json.loads(json.dumps(STATUS))
        status['libraries'] = [{'name': 'Tiny', 'path': '/x', 'books': 1}]
        self.sharing(status)
        self.assertEqual(tray.library_action.text(), 'Tiny, 1 book')

    def test_open_in_browser_and_copy_address(self):
        from qt.core import QApplication

        kp, tray = self.make()
        self.sharing()
        tray.browser_action.trigger()
        self.assertEqual(self.opened, [LOCAL_URL])
        tray.copy_action.trigger()
        self.assertEqual(QApplication.clipboard().text(), 'http://192.168.1.18:8099/')

    def test_address_falls_back_to_this_computer(self):
        kp, tray = self.make()
        status = dict(STATUS, urls=[])
        self.sharing(status)
        self.assertEqual(tray.state_action.text(), 'Sharing at 127.0.0.1:8099')

    def test_icon_follows_the_state(self):
        from calibre_zen.tray import keeper as k
        from calibre_zen.tray.icon import waves_path

        self.assertTrue(os.path.exists(waves_path()))
        kp, tray = self.make()
        kp.start()
        self.assertEqual(tray.icon.icon().cacheKey(), tray.icons.get(faded=True).cacheKey())
        self.sharing()
        self.assertEqual(tray.icon.icon().cacheKey(), tray.icons.get().cacheKey())
        self.launch.proc.rc = 1
        self.assertTrue(wait_until(lambda: kp.state == k.STOPPED))
        self.assertEqual(tray.icon.icon().cacheKey(), tray.icons.get(dot=True).cacheKey())
        for faded, dot in ((False, False), (True, False), (False, True)):
            self.assertFalse(tray.icons.get(faded, dot).isNull())

    def test_mask_icon_on_macos(self):
        from calibre_zen.tray.icon import Icons

        self.assertTrue(Icons('#000000', True).get().isMask())
        self.assertFalse(Icons('#ffffff', False).get().isMask())

    def test_bare_address(self):
        from calibre_zen.tray.menu import bare_address

        self.assertEqual(bare_address('http://192.168.1.18:8080/'), '192.168.1.18:8080')
        self.assertEqual(bare_address('http://127.0.0.1:8080'), '127.0.0.1:8080')
        self.assertEqual(bare_address('http://h:8080/calibre/'), 'h:8080/calibre/')

    def test_a_flag_on_the_command_line_greys_its_toggle(self):
        kp, tray = self.make(args=['--listen-on', '0.0.0.0', '--enable-local-write'])
        self.sharing()
        self.assertFalse(tray.share_action.isEnabled())
        self.assertFalse(tray.write_action.isEnabled())
        self.assertTrue(tray.auto_add_action.isEnabled())
        kp, tray = self.make(args=['--auto-add=/x'])
        self.sharing()
        self.assertTrue(tray.share_action.isEnabled())
        self.assertFalse(tray.auto_add_action.isEnabled())


class TestToggles(TrayTestCase):
    def assertRestarted(self, times=1):
        self.assertTrue(wait_until(lambda: len(self.launch.started) == 1 + times), self.launch.started)
        self.assertEqual(len(self.launch.stopped), times)
        self.assertEqual(self.launch.procs[-2].rc, 0)

    def test_share_on_this_network(self):
        from calibre.srv.opts import DEFAULT_CONFIG, server_config

        kp, tray = self.make()
        self.sharing()
        self.assertTrue(tray.share_action.isChecked())  # calibre's default: every address
        tray.share_action.trigger()
        self.assertEqual(server_config(refresh=True).listen_on, '127.0.0.1')
        with open(DEFAULT_CONFIG) as f:
            self.assertIn('listen_on 127.0.0.1', f.read())
        self.assertFalse(tray.share_action.isChecked())
        self.assertRestarted()
        tray.share_action.trigger()
        self.assertIsNone(server_config(refresh=True).listen_on)
        self.assertTrue(tray.share_action.isChecked())
        self.assertRestarted(2)

    def test_allow_changes_from_this_computer(self):
        from calibre.srv.opts import server_config

        kp, tray = self.make()
        self.sharing()
        self.assertFalse(tray.write_action.isChecked())
        tray.write_action.trigger()
        self.assertTrue(server_config(refresh=True).local_write)
        self.assertTrue(tray.write_action.isChecked())
        self.assertRestarted()

    def test_a_setting_from_the_full_app_shows_on_open(self):
        from calibre.srv.opts import change_settings

        kp, tray = self.make()
        self.sharing()
        change_settings(local_write=True)
        tray.menu.aboutToShow.emit()
        self.assertTrue(tray.write_action.isChecked())

    def test_add_books_from_a_folder(self):
        from calibre.utils.config import JSONConfig

        folder = os.path.join(self.mkdtemp(), 'Add here')
        os.mkdir(folder)
        asked = []

        def choose(title, start):
            asked.append(title)
            return folder

        kp, tray = self.make(choose=choose)
        self.sharing()
        self.assertFalse(tray.auto_add_action.isChecked())
        tray.auto_add_action.trigger()
        self.assertEqual(asked, ['Choose a folder to add books from'])
        self.assertEqual(JSONConfig('gui').get('auto_add_path'), folder)
        self.assertTrue(tray.auto_add_action.isChecked())
        self.assertEqual(tray.auto_add_action.text(), 'Add books from Add here')
        self.assertEqual(self.messages, ['Books you put in Add here will move into your library.'])
        self.assertRestarted()
        # Unchecking clears it, without asking.
        tray.auto_add_action.trigger()
        self.assertIsNone(JSONConfig('gui').get('auto_add_path'))
        self.assertFalse(tray.auto_add_action.isChecked())
        self.assertEqual(tray.auto_add_action.text(), 'Add books from a folder…')
        self.assertEqual(len(asked), 1)
        self.assertRestarted(2)

    def test_cancelling_the_folder_changes_nothing(self):
        from calibre.utils.config import JSONConfig

        kp, tray = self.make(choose=lambda title, start: '')
        self.sharing()
        tray.auto_add_action.trigger()
        self.assertIsNone(JSONConfig('gui').get('auto_add_path'))
        self.assertFalse(tray.auto_add_action.isChecked())
        self.assertEqual(self.launch.stopped, [])

    def test_a_folder_inside_the_library_is_refused(self):
        from calibre.utils.config import JSONConfig

        lib = self.mkdtemp()
        inner = os.path.join(lib, 'incoming')
        os.mkdir(inner)
        kp, tray = self.make(library=lib, choose=lambda title, start: inner)
        self.sharing()
        tray.auto_add_action.trigger()
        self.assertIsNone(JSONConfig('gui').get('auto_add_path'))
        self.assertFalse(tray.auto_add_action.isChecked())
        self.assertEqual(self.messages, ['Pick a folder outside your library.'])
        self.assertEqual(self.launch.stopped, [])

    def test_folder_problems(self):
        from calibre_zen.tray.settings import folder_problem

        d = self.mkdtemp()
        hidden = os.path.join(d, '.hidden')
        os.mkdir(hidden)
        self.assertIsNone(folder_problem(d))
        self.assertIsNotNone(folder_problem(os.path.join(d, 'missing')))
        self.assertIsNotNone(folder_problem(hidden))
        self.assertIsNotNone(folder_problem(d, [os.path.dirname(d)]))


class TestHandOver(TrayTestCase):
    def test_open_the_full_app(self):
        from calibre_zen.reader.activation import NO_FOREGROUND_ENV
        from calibre_zen.tray import keeper as k

        lib = self.mkdtemp()
        cmd = ['/bin/zen-gui', '--debug']
        with mock.patch.dict(os.environ, {k.GUI_CMD_ENV: json.dumps(cmd), NO_FOREGROUND_ENV: '1'}):
            kp, tray = self.make(library=lib)
            self.sharing()
            tray.gui_action.trigger()
            self.assertTrue(wait_until(lambda: self.popen.calls))
        gui = self.popen.calls[0]
        self.assertEqual(self.launch.stopped, [LOCAL_URL])
        self.assertEqual(self.launch.procs[0].rc, 0)
        self.assertEqual(gui.cmd, [*cmd, '--with-library', lib])
        self.assertNotIn(NO_FOREGROUND_ENV, gui.kw['env'])
        self.assertEqual(kp.state, k.PAUSED)
        self.assertEqual(tray.state_action.text(), 'Paused while Calibre Zen is open')
        # The host stays down while the full app runs, retries or not.
        kp.retry_timer.start(1)
        wait_until(lambda: False, 200)
        self.assertEqual(len(self.launch.started), 1)
        # The full app quit: the host starts again once the app's lock has
        # stayed free for the grace period, not before.
        quit_at = time.monotonic()
        gui.rc = 0
        self.assertTrue(wait_until(lambda: len(self.launch.started) == 2))
        self.assertGreaterEqual(time.monotonic() - quit_at, kp.GUI_GRACE)
        self.assertTrue(wait_until(lambda: kp.state == k.SHARING))

    def test_open_while_paused_starts_the_app_without_a_stop(self):
        from calibre_zen.tray import keeper as k

        with mock.patch.dict(os.environ, {k.GUI_CMD_ENV: json.dumps(['/bin/zen-gui'])}):
            kp, tray = self.make()
            self.sharing()
            self.launch.proc.rc = k.LIBRARY_BUSY
            self.assertTrue(wait_until(lambda: kp.state == k.PAUSED))
            tray.gui_action.trigger()
        self.assertEqual(len(self.popen.calls), 1)
        self.assertEqual(self.launch.stopped, [])

    def test_a_setting_waits_for_the_full_app(self):
        from calibre_zen.tray import keeper as k

        with mock.patch.dict(os.environ, {k.GUI_CMD_ENV: json.dumps(['/bin/zen-gui'])}):
            kp, tray = self.make()
            self.sharing()
            tray.gui_action.trigger()
            self.assertTrue(wait_until(lambda: self.popen.calls))
        kp.restart()
        self.assertEqual(len(self.launch.started), 1)
        self.assertEqual(len(self.launch.stopped), 1)

    def test_gui_command(self):
        from calibre_zen.tray import keeper as k

        with mock.patch.dict(os.environ, {k.GUI_CMD_ENV: json.dumps(['a', 'b', '--with-library', '/lib'])}):
            self.assertEqual(k.gui_command('/other'), ['a', 'b', '--with-library', '/lib'])
        env = dict(os.environ)
        env.pop(k.GUI_CMD_ENV, None)
        with mock.patch.dict(os.environ, env, clear=True):
            cmd = k.gui_command('/lib')
        self.assertEqual(cmd[-2:], ['--with-library', '/lib'])
        self.assertIn(os.path.basename(cmd[0]), ('calibre', 'calibre.exe'))
        with mock.patch.dict(os.environ, {k.GUI_CMD_ENV: 'not json'}):
            self.assertIn(os.path.basename(k.gui_command()[0]), ('calibre', 'calibre.exe'))


class TestFullAppLock(TrayTestCase):
    "calibre's `GUI` lock: held while the full app runs, wherever it was started from."

    def test_a_restart_of_the_full_app_is_waited_out(self):
        """
        calibre's restart quits the app, then opens a new one about three
        seconds later. A host started in between would take the library and
        the new app would refuse to open.
        """
        from calibre_zen.tray import keeper as k

        with mock.patch.dict(os.environ, {k.GUI_CMD_ENV: json.dumps(['/bin/zen-gui'])}):
            kp, tray = self.make()
            self.sharing()
            tray.gui_action.trigger()
            self.assertTrue(wait_until(lambda: self.popen.calls))
        self.locks.names.add('GUI')  # the app is up
        gui = self.popen.calls[0]
        gui.rc = 0  # it quits to restart; its lock is free for a moment
        self.locks.names.discard('GUI')
        threading.Timer(kp.GUI_GRACE / 2, lambda: self.locks.names.add('GUI')).start()  # the new one is up
        wait_until(lambda: False, int(kp.GUI_GRACE * 1000 * 3))
        self.assertEqual(len(self.launch.started), 1)
        self.assertEqual(kp.state, k.PAUSED)
        self.assertEqual(tray.state_action.text(), 'Paused while Calibre Zen is open')
        # The new app quits for good: after the grace period, the host.
        freed = time.monotonic()
        self.locks.names.discard('GUI')
        self.assertTrue(wait_until(lambda: len(self.launch.started) == 2))
        self.assertGreaterEqual(time.monotonic() - freed, kp.GUI_GRACE)
        self.assertTrue(wait_until(lambda: kp.state == k.SHARING))

    def test_a_full_app_opened_elsewhere_pauses_without_a_host(self):
        from calibre_zen.tray import keeper as k

        kp, tray = self.make()
        self.locks.names.add('GUI')
        kp.start()
        self.assertEqual(kp.state, k.PAUSED)
        self.assertEqual(self.launch.started, [])
        self.assertIn('GUI', self.locks.asked)
        wait_until(lambda: False, 200)
        self.assertEqual(self.launch.started, [])
        self.locks.names.discard('GUI')
        self.launch.answer = STATUS
        self.assertTrue(wait_until(lambda: kp.state == k.SHARING))
        self.assertEqual(len(self.launch.started), 1)

    def test_no_wait_when_the_full_app_was_never_seen(self):
        kp, tray = self.make()
        kp.GUI_GRACE = 60
        kp.start()
        self.assertEqual(len(self.launch.started), 1)


class TestLocks(ZenTestCase):
    "The real probe, against calibre's own lock, under a name nothing else uses."

    HOLD = (
        'import os, sys\n'
        'from calibre.utils.lock import create_single_instance_mutex\n'
        'release = create_single_instance_mutex(os.environ["ZEN_TEST_LOCK"])\n'
        'print("held" if release else "busy", flush=True)\n'
        'sys.stdin.read()\n'
        'release and release()\n'
        'print("released", flush=True)\n'
    )

    def test_held_without_taking_it(self):
        from calibre_zen.tray import locks

        name = f'zen-test-{os.getpid()}-{time.monotonic_ns()}'
        self.assertFalse(locks.held(name))
        child = subprocess.Popen(
            [sys.executable, '-c', self.HOLD],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            env=dict(os.environ, ZEN_TEST_LOCK=name),
        )
        try:
            self.assertEqual(child.stdout.readline().strip(), 'held')
            # base_dir() would start calibre's safe_atexit helper in the tray.
            with mock.patch('calibre.ptempfile.base_dir', side_effect=AssertionError('base_dir() was called')):
                for _ in range(3):
                    self.assertTrue(locks.held(name))
            child.stdin.close()
            self.assertEqual(child.stdout.readline().strip(), 'released')
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(30)
            child.stdout.close()
        # Looking never left it taken.
        self.assertFalse(locks.held(name))

    @unittest.skipIf(sys.platform == 'win32', 'a named mutex there, not a file')
    def test_the_lock_file_without_base_dir(self):
        "calibre points tempfile's folder at base_dir(), which starts its safe_atexit helper."
        import tempfile

        from calibre.ptempfile import get_default_tempdir
        from calibre_zen.tray import locks

        home = os.path.expanduser('~')
        boom = AssertionError('base_dir() was called')
        with (
            mock.patch('calibre.ptempfile.base_dir', side_effect=boom),
            mock.patch.object(tempfile, '_gettempdir', side_effect=boom),
            mock.patch.object(os, 'access', lambda path, mode: path not in ('/Library/Caches', '/var/lock', home)),
        ):
            path = locks.lock_file('zen-test')
        self.assertEqual(os.path.dirname(path), get_default_tempdir())
        self.assertTrue(os.path.basename(path).endswith('-singleinstance-' + str(os.geteuid()) + '-zen-test.lock'))


class TestQuit(TrayTestCase):
    def test_quit_stops_the_host(self):
        kp, tray = self.make()
        self.sharing()
        tray.quit_action.trigger()
        self.assertEqual(self.launch.stopped, [LOCAL_URL])
        self.assertEqual(self.launch.proc.rc, 0)
        self.assertEqual(self.quits, 1)
        self.assertTrue(kp.quitting)
        # Nothing starts it again afterwards.
        kp.start()
        self.assertEqual(len(self.launch.started), 1)

    def test_quit_insists_when_the_host_will_not_stop(self):
        kp, tray = self.make()
        self.sharing()
        self.launch.stop = lambda url, timeout=10: False
        tray.quit_action.trigger()
        self.assertTrue(self.launch.proc.terminated)

    def test_quit_lets_the_host_finish_after_its_port_closes(self):
        "The port closes first; worker pools, auto-add and the libraries close after."
        kp, tray = self.make()
        kp.EXIT_TIMEOUT = 5
        self.sharing()
        self.launch.linger = 0.4
        t0 = time.monotonic()
        tray.quit_action.trigger()
        p = self.launch.proc
        self.assertGreaterEqual(time.monotonic() - t0, 0.35)
        self.assertEqual(p.rc, 0)
        self.assertFalse(p.terminated)
        self.assertFalse(p.killed)

    def test_quit_kills_a_host_that_never_finishes(self):
        kp, tray = self.make()
        kp.EXIT_TIMEOUT = 0.2
        self.sharing()
        self.launch.linger = 30
        tray.quit_action.trigger()
        self.assertTrue(self.launch.proc.killed)

    def test_a_restart_waits_for_the_old_host_to_exit(self):
        kp, tray = self.make()
        kp.EXIT_TIMEOUT = 5
        self.sharing()
        self.launch.linger = 0.3
        old = self.launch.proc
        seen = []
        real_start = self.launch.start
        self.launch.start = lambda *a, **kw: (seen.append(old.rc), real_start(*a, **kw))[1]
        kp.restart()
        self.assertTrue(wait_until(lambda: len(self.launch.started) == 2))
        self.assertEqual(seen, [0])
        self.assertFalse(old.killed)

    def test_restarts_during_a_stop_are_folded_into_it(self):
        kp, tray = self.make()
        kp.EXIT_TIMEOUT = 5
        self.sharing()
        self.launch.linger = 0.3
        old = self.launch.proc
        seen = []
        real_start = self.launch.start
        self.launch.start = lambda *a, **kw: (seen.append(old.rc), real_start(*a, **kw))[1]
        kp.restart()
        kp.restart()  # a second switch flicked while the first stop runs
        kp.restart()
        self.assertTrue(wait_until(lambda: len(self.launch.started) == 2))
        self.assertTrue(wait_until(lambda: not kp.busy))
        self.assertEqual(len(self.launch.started), 2)
        self.assertEqual(seen, [0])  # the new host started only after the old one exited
        with open(self.record) as f:
            self.assertEqual(json.load(f)['pid'], self.launch.proc.pid)

    def test_a_host_that_cannot_be_written_down_is_not_left_running(self):
        from calibre_zen.tray import keeper as k

        missing = os.path.join(self.mkdtemp(), 'no-such-folder', 'zen-tray-host.json')
        kp, tray = self.make(record=missing)
        kp.start()
        self.assertEqual(len(self.launch.started), 1)
        self.assertIsNotNone(self.launch.proc.rc)  # stopped again at once
        self.assertIsNone(kp.proc)
        self.assertEqual(kp.state, k.STOPPED)
        self.assertIn('Could not save', kp.reason)

    def test_quit_while_stopped(self):
        from calibre_zen.tray import keeper as k

        kp, tray = self.make()
        kp.start()
        self.launch.proc.rc = 1
        self.assertTrue(wait_until(lambda: kp.state == k.STOPPED))
        tray.quit_action.trigger()
        self.assertEqual(self.launch.stopped, [])
        self.assertFalse(kp.retry_timer.isActive())


class TestLeftover(TrayTestCase):
    "A host a crashed or force-quit tray left running, holding the library."

    OLD_URL = 'http://127.0.0.1:8100'

    def leftover(self, pid=777, answers=777):
        path = os.path.join(self.mkdtemp(), 'zen-tray-host.json')
        with open(path, 'w') as f:
            json.dump({'pid': pid, 'url': self.OLD_URL}, f)
        kp, tray = self.make(record=path)
        kp.EXIT_TIMEOUT = 5
        if answers is not None:
            self.launch.others[self.OLD_URL] = dict(STATUS, pid=answers)
        return kp, tray

    def test_the_record_follows_the_host(self):
        kp, tray = self.make()
        self.sharing()
        with open(self.record) as f:
            self.assertEqual(json.load(f), {'pid': self.launch.proc.pid, 'url': LOCAL_URL})
        tray.quit_action.trigger()
        self.assertFalse(os.path.exists(self.record))
        kp, tray = self.make()
        self.sharing()
        self.launch.proc.rc = 1
        self.assertTrue(wait_until(lambda: not os.path.exists(self.record)))

    def test_it_is_stopped_before_a_new_host_starts(self):
        from calibre_zen.tray import keeper as k

        kp, tray = self.leftover()
        # It lets go of the library a moment after its port closes.
        self.locks.names.add('db')
        real_stop = self.launch.stop

        def stop(url, timeout=10):
            threading.Timer(0.2, lambda: self.locks.names.discard('db')).start()
            return real_stop(url, timeout)

        self.launch.stop = stop
        seen = []
        real_start = self.launch.start
        self.launch.start = lambda *a, **kw: (seen.append(set(self.locks.names)), real_start(*a, **kw))[1]
        self.launch.answer = STATUS
        kp.start()
        self.assertEqual(kp.state, k.STARTING)
        self.assertTrue(wait_until(lambda: kp.state == k.SHARING))
        self.assertEqual(self.launch.stopped, [self.OLD_URL])
        self.assertEqual(seen, [set()])
        with open(self.record) as f:
            self.assertEqual(json.load(f), {'pid': self.launch.proc.pid, 'url': LOCAL_URL})

    def test_a_host_with_another_pid_is_left_alone(self):
        kp, tray = self.leftover(answers=778)
        kp.start()
        self.assertTrue(wait_until(lambda: len(self.launch.started) == 1))
        self.assertEqual(self.launch.stopped, [])

    def test_a_record_with_nothing_there_is_dropped(self):
        kp, tray = self.leftover(answers=None)
        kp.start()
        self.assertTrue(wait_until(lambda: len(self.launch.started) == 1))
        self.assertEqual(self.launch.stopped, [])

    def test_a_broken_record_is_ignored(self):
        path = os.path.join(self.mkdtemp(), 'zen-tray-host.json')
        with open(path, 'w') as f:
            f.write('{not json')
        kp, tray = self.make(record=path)
        kp.start()
        self.assertEqual(len(self.launch.started), 1)


class TestMain(ZenTestCase):
    def test_manage_users_is_refused(self):
        from calibre_zen.tray.main import main, runs_once

        for opts in (['--manage-users'], ['--manage-u', '--', 'add', 'bob'], ['--port', '1', '--manage-users=x'], ['--man']):
            self.assertTrue(runs_once(opts), opts)
        for opts in ([], ['--max-jobs', '2'], ['--port', '1', '--', '--manage-users'], ['--ma']):
            self.assertFalse(runs_once(opts), opts)
        self.assertEqual(main(['--manage-users', '--', 'add', 'bob']), 2)

    def test_split_args(self):
        from calibre_zen.tray.main import host_args, split_args

        lib, rest = split_args(['--port', '8099', '--library', '/a/b', '--enable-auth'])
        self.assertEqual(lib, os.path.abspath('/a/b'))
        self.assertEqual(rest, ['--port', '8099', '--enable-auth'])
        self.assertEqual(host_args(lib, rest), ['--zen-library', lib, '--port', '8099', '--enable-auth'])
        self.assertEqual(split_args(['--library=/x'])[0], os.path.abspath('/x'))
        self.assertEqual(split_args([]), (None, []))
        self.assertEqual(host_args(None, []), [])
        with self.assertRaises(ValueError):
            split_args(['--library'])

    def test_help_starts_nothing(self):
        from calibre_zen.tray import main

        with mock.patch.object(main, 'run') as run, mock.patch('builtins.print'):
            self.assertEqual(main.main(['--help']), 0)
            self.assertEqual(main.main(['--library']), 2)
        run.assert_not_called()

    def test_one_tray_at_a_time(self):
        from calibre_zen.tray.main import lock_path, take_lock

        self.assertEqual(os.path.realpath(os.path.dirname(lock_path())), os.path.realpath(os.environ['CALIBRE_CONFIG_DIRECTORY']))
        from calibre_zen.tray.main import record_path

        self.assertEqual(os.path.dirname(record_path()), os.path.dirname(lock_path()))
        path = os.path.join(self.tmp, 'tray.lock')
        first = take_lock(path)
        self.assertIsNotNone(first)
        self.assertIsNone(take_lock(path))
        first.unlock()
        again = take_lock(path)
        self.assertIsNotNone(again)
        again.unlock()


class TestQuitDuringRestart(TrayTestCase):
    def test_quit_waits_for_a_restart_in_flight(self):
        import threading

        kp, tray = self.make()
        self.sharing()
        gate = threading.Event()
        real_stop = self.launch.stop

        def slow_stop(url, timeout=10):
            gate.wait(2)
            return real_stop(url, timeout)

        self.launch.stop = slow_stop
        kp.restart()  # the stop runs on a thread and waits on the gate
        self.assertTrue(kp.busy)
        threading.Timer(0.2, gate.set).start()
        tray.quit_action.trigger()
        self.assertEqual(self.launch.procs[0].rc, 0)
        self.assertEqual(len(self.launch.started), 1)


class TestKeepSharing(TrayTestCase):
    "The window's Close and keep sharing: quit through calibre's restart, start the tray instead."

    def fake_main(self):
        calls = []
        return types.SimpleNamespace(restart_after_quit=lambda: calls.append('calibre restart')), calls

    def fake_gui(self, calls, quits=True):
        library = self.mkdtemp()

        class Gui:
            shutting_down = False
            current_db = types.SimpleNamespace(library_path=library)

            def quit(self, restart=False):
                calls.append(('quit', restart))
                self.shutting_down = quits

        return Gui(), library

    def test_quitting_starts_the_tray_instead_of_the_window(self):
        from calibre_zen.tray import handoff

        gm, calls = self.fake_main()
        orig = gm.restart_after_quit
        gui, library = self.fake_gui(calls)
        with mock.patch.object(handoff, 'start_tray', lambda lib: calls.append(('tray', lib))):
            self.assertTrue(handoff.keep_sharing(gui, module=gm))
            gm.restart_after_quit()  # what calibre.gui2.main.main() does once the locks are free
        self.assertEqual(calls, [('quit', True), ('tray', library)])
        self.assertIs(gm.restart_after_quit, orig, 'armed for one quit only')

    def test_a_quit_the_user_declines_starts_nothing(self):
        from calibre_zen.tray import handoff

        gm, calls = self.fake_main()
        orig = gm.restart_after_quit
        gui, _library = self.fake_gui(calls, quits=False)  # jobs are running and the user kept the window
        self.assertFalse(handoff.keep_sharing(gui, module=gm))
        self.assertIs(gm.restart_after_quit, orig)

    def test_a_tray_that_cannot_start_brings_the_window_back(self):
        from calibre_zen.tray import handoff

        gm, calls = self.fake_main()

        def broken(library):
            raise OSError('no calibre-debug')

        handoff.arm('/lib', module=gm)
        with mock.patch.object(handoff, 'start_tray', broken), mock.patch('traceback.print_exc'):
            gm.restart_after_quit()
        self.assertEqual(calls, ['calibre restart'])

    def test_the_tray_command(self):
        from calibre_zen.tray import handoff

        cmd = handoff.tray_command('/my books')
        self.assertEqual(os.path.splitext(os.path.basename(cmd[0]))[0], 'calibre-debug')
        i = cmd.index('-e')
        self.assertTrue(os.path.isfile(cmd[i + 1]), cmd[i + 1])
        self.assertEqual(os.path.basename(os.path.dirname(cmd[i + 1])), 'tray')
        self.assertEqual(cmd[i + 2 :], ['--', '--library', '/my books'])
        self.assertEqual(handoff.tray_command(None)[-1], '--')

    def test_the_tray_reopens_the_window_the_way_it_was_started(self):
        from calibre_zen.tray import handoff
        from calibre_zen.tray import keeper as k
        from calibre_zen.tray.main import HELLO_ENV

        exe = '/Applications/calibre.app/Contents/MacOS/calibre-debug'
        argv = ['/repo/.calibre-zen/bootstrap.py', '--with-library', '/lib']
        with mock.patch.dict(os.environ), mock.patch.object(sys, 'executable', exe), mock.patch.object(sys, 'argv', argv):
            os.environ.pop(k.GUI_CMD_ENV, None)
            env = handoff.tray_env()
            self.assertEqual(env[HELLO_ENV], '1')
            self.assertEqual(json.loads(env[k.GUI_CMD_ENV]), [exe, '-e', '/repo/.calibre-zen/bootstrap.py', '--'])
            # Opened from a tray already: keep the command it was given.
            os.environ[k.GUI_CMD_ENV] = '["/bin/given"]'
            self.assertEqual(handoff.tray_env()[k.GUI_CMD_ENV], '["/bin/given"]')
        # A package runs calibre's own executable: the tray finds that itself.
        exe = '/Applications/Calibre Zen.app/Contents/MacOS/calibre'
        with mock.patch.dict(os.environ), mock.patch.object(sys, 'executable', exe), mock.patch.object(sys, 'argv', ['calibre']):
            os.environ.pop(k.GUI_CMD_ENV, None)
            self.assertNotIn(k.GUI_CMD_ENV, handoff.tray_env())

    def test_the_tray_is_started_detached(self):
        from calibre_zen.tray import handoff

        log = os.path.join(self.mkdtemp(), 'zen-tray.log')
        with mock.patch.object(handoff, 'log_path', lambda: log), mock.patch('subprocess.Popen') as popen:
            handoff.start_tray('/lib')
        (cmd,), kw = popen.call_args
        self.assertEqual(cmd[-2:], ['--library', '/lib'])
        self.assertIs(kw['stdin'], subprocess.DEVNULL)
        if os.name == 'nt':
            self.assertTrue(kw['creationflags'] & subprocess.DETACHED_PROCESS)
        else:
            self.assertTrue(kw['start_new_session'])
        self.assertTrue(os.path.isfile(log))

    def test_the_tray_says_once_that_the_library_is_still_shared(self):
        kp, tray = self.make()
        tray.hello = True
        kp.start()
        self.assertEqual(self.messages, [], 'nothing to say before it is sharing')
        self.sharing()
        self.assertEqual(len(self.messages), 1)
        self.assertIn('still shared', self.messages[0])
        tray.refresh()
        self.assertEqual(len(self.messages), 1)

    def test_a_tray_started_by_hand_says_nothing(self):
        kp, tray = self.make()
        self.sharing()
        self.assertEqual(self.messages, [])

#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The menubar app: the keeper's states, the menu they show, and what each item
does. The host is a fake with calibre_zen.host.launch's four functions, so
nothing here starts a server, a full app, or a browser.
"""

import json
import os
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
        self.terminated = False

    def poll(self):
        return self.rc

    def terminate(self):
        self.terminated = True
        if self.rc is None:
            self.rc = -15

    def kill(self):
        self.terminate()

    def wait(self, timeout=None):
        return self.rc


class FakeLaunch:
    "calibre_zen.host.launch, with a process that does what the test says."

    def __init__(self):
        self.procs: list[FakeProc] = []
        self.started: list[list[str]] = []
        self.stopped: list[str] = []
        self.answer = None  # what /zen/status says while the latest process lives
        self.log_lines: list[str] = []  # written to the log by the next start

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
        if self.procs and self.procs[-1].rc is None:
            return self.answer
        return None

    def stop(self, base_url, timeout=10):
        self.stopped.append(base_url)
        if self.procs and self.procs[-1].rc is None:
            self.procs[-1].rc = 0
        return True

    @property
    def proc(self) -> FakeProc:
        return self.procs[-1]


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

    def make(self, library=None, args=(), choose=None):
        from calibre_zen.tray.keeper import Keeper
        from calibre_zen.tray.menu import Tray

        self.launch = FakeLaunch()
        self.popen = FakePopen()
        self.opened: list[str] = []
        self.quits = 0
        self.messages: list[str] = []
        kp = Keeper(self.launch, [*args, *([library] if library else [])], self.log, library, popen=self.popen)
        kp.POLL_MS = kp.STARTING_POLL_MS = 20
        kp.PAUSED_RETRY_MS = 150
        kp.BACKOFF_MS = (150, 300)
        kp.STOP_TIMEOUT = kp.KILL_TIMEOUT = 0.1

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
        from calibre_zen.tray.icon import glyph_path

        self.assertTrue(os.path.exists(glyph_path()))
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
        # The full app quit: the host starts again, at once.
        gui.rc = 0
        self.assertTrue(wait_until(lambda: len(self.launch.started) == 2))
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

    def test_quit_while_stopped(self):
        from calibre_zen.tray import keeper as k

        kp, tray = self.make()
        kp.start()
        self.launch.proc.rc = 1
        self.assertTrue(wait_until(lambda: kp.state == k.STOPPED))
        tray.quit_action.trigger()
        self.assertEqual(self.launch.stopped, [])
        self.assertFalse(kp.retry_timer.isActive())


class TestMain(ZenTestCase):
    def test_split_args(self):
        from calibre_zen.tray.main import host_args, split_args

        lib, rest = split_args(['--port', '8099', '--library', '/a/b', '--enable-auth'])
        self.assertEqual(lib, os.path.abspath('/a/b'))
        self.assertEqual(rest, ['--port', '8099', '--enable-auth'])
        self.assertEqual(host_args(lib, rest), ['--port', '8099', '--enable-auth', lib])
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

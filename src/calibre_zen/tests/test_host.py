#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The host: its options, its two routes, the lock, auto-add, and a real host
process started the way the tray starts one.

Nothing here takes the machine-wide `db` lock: other test runs may be going at
the same time. The real host runs with CALIBRE_NO_SI_DANGER_DANGER, and the
"lock is held" path is tested in this process with the lock call faked. Every
port is a free one picked at run time.
"""

import contextlib
import io
import json
import os
import shutil
import socket
import tempfile
import time
import types
import unittest
from unittest import mock

from calibre_zen.tests.base import make_library, work_dir


def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@contextlib.contextmanager
def sharing_settings(text: str):
    "server-config.txt, as Preferences -> Sharing writes it, for the duration."
    from calibre.srv.opts import DEFAULT_CONFIG

    with open(DEFAULT_CONFIG, 'w') as f:
        f.write(text)
    try:
        yield DEFAULT_CONFIG
    finally:
        os.remove(DEFAULT_CONFIG)


def long_flags(parser) -> set[str]:
    return {flag for opt in parser.option_list for flag in opt._long_opts}


class Scratch(unittest.TestCase):
    tmp = ''

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix=cls.__name__ + '-', dir=work_dir())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def mkdtemp(self) -> str:
        d = tempfile.mkdtemp(dir=self.tmp)
        self.addCleanup(shutil.rmtree, d, True)
        return d


class Options(Scratch):
    def test_light_parser_has_every_option_the_server_has(self):
        "The tray parses with the light parser; an option upstream adds must not break it."
        from calibre_zen.host import options

        self.assertEqual(long_flags(options.light_parser()), long_flags(options.full_parser()))

    def test_defaults_come_from_the_sharing_settings(self):
        from calibre_zen.host import options

        with sharing_settings('port 18123\nlocal_write True\nurl_prefix /books\n'):
            for parser in (options.full_parser, options.light_parser):
                with self.subTest(parser=parser.__name__):
                    opts, libs = options.parse([], parser())
                    self.assertEqual((opts.port, opts.local_write, opts.url_prefix, libs), (18123, True, '/books', []))
                    opts, libs = options.parse(['--port', '18124', '--disable-local-write', '/lib'], parser())
                    self.assertEqual((opts.port, opts.local_write, opts.url_prefix, libs), (18124, False, '/books', ['/lib']))

    def test_calibre_defaults_without_settings(self):
        from calibre.srv.opts import options as server_options
        from calibre_zen.host import options

        opts, _ = options.parse([], options.light_parser())
        self.assertEqual(opts.port, server_options['port'].default)
        self.assertFalse(opts.local_write)

    def test_local_url(self):
        from calibre_zen.host import launch

        with sharing_settings('port 18125\nurl_prefix /books/\n'):
            self.assertEqual(launch.local_url(), 'http://127.0.0.1:18125/books')
            self.assertEqual(launch.local_url(['--port', '18126']), 'http://127.0.0.1:18126/books')
            self.assertEqual(launch.local_url(['--listen-on', '0.0.0.0']), 'http://127.0.0.1:18125/books')
            self.assertEqual(launch.local_url(['--listen-on', '192.0.2.5']), 'http://192.0.2.5:18125/books')
            self.assertEqual(launch.local_url(['--listen-on', '::1']), 'http://[::1]:18125/books')

    def test_auto_add_folder(self):
        from calibre.utils.config import JSONConfig
        from calibre_zen.host import options

        def folder(*argv):
            return options.auto_add_folder(options.parse(argv, options.light_parser())[0])

        here = self.mkdtemp()
        self.assertEqual(folder('--auto-add', here), (here, True))
        self.assertEqual(folder('--auto-add', here, '--no-auto-add'), (None, False))
        g = JSONConfig('gui')
        old = g.get('auto_add_path')
        g['auto_add_path'] = here
        try:
            self.assertEqual(folder(), (here, False))
            self.assertEqual(folder('--no-auto-add'), (None, False))
        finally:
            g['auto_add_path'] = old


class SameMachine(unittest.TestCase):
    def test_this_computer(self):
        from calibre_zen.host.endpoints import is_this_computer, own_addresses

        for addr in ('127.0.0.1', '::1', '::ffff:127.0.0.1', '127.8.9.10'):
            self.assertTrue(is_this_computer(addr), addr)
        for addr in ('192.0.2.10', '2001:db8::1', '', None, 'nonsense'):
            self.assertFalse(is_this_computer(addr), addr)
        self.assertFalse(is_this_computer('127.0.0.1', forwarded_for='192.0.2.10'))
        lan = next((a for a in own_addresses() if not a.is_loopback and a.version == 4), None)
        if lan is not None:
            self.assertTrue(is_this_computer(str(lan)))

    def test_host_header(self):
        from calibre_zen.host.endpoints import host_is_this_computer, own_addresses

        for host in ('127.0.0.1', '127.0.0.1:8080', 'localhost', 'LocalHost:8080', '[::1]', '[::1]:8080', '::1'):
            self.assertTrue(host_is_this_computer(host), host)
        # DNS rebinding: the name is the attacker's even when it resolves here.
        for host in ('evil.example:8080', 'evil.example', '127.0.0.1.evil.example', 'localhost.evil.example', 'mymac.local'):
            self.assertFalse(host_is_this_computer(host), host)
        for host in ('', None, '127.0.0.1:x', '127.0.0.1:0', 'bob@127.0.0.1', '127.0.0.1/x', '[::1', '192.0.2.10'):
            self.assertFalse(host_is_this_computer(host), host)
        lan = next((a for a in own_addresses() if not a.is_loopback and a.version == 4), None)
        if lan is not None:  # a host on --listen-on <LAN address>, asked by the tray at that address
            self.assertTrue(host_is_this_computer(f'{lan}:8080'))

    def test_request_is_local(self):
        from calibre_zen.host.endpoints import request_is_local

        self.assertTrue(request_is_local(self.request('127.0.0.1')))
        self.assertTrue(request_is_local(self.request('::1', Host='localhost:8080')))
        self.assertFalse(request_is_local(self.request('127.0.0.1', Host='evil.example:8080')), 'DNS rebinding')
        self.assertFalse(request_is_local(self.request('127.0.0.1', Host=None)))
        self.assertFalse(request_is_local(self.request('192.0.2.10')))
        for header, value in (('X-Forwarded-For', '192.0.2.10'), ('Forwarded', 'for=192.0.2.10'), ('X-Real-Ip', '192.0.2.10')):
            self.assertFalse(request_is_local(self.request('127.0.0.1', **{header: value})), header)
        rd = self.request('127.0.0.1')
        rd.forwarded_for = '192.0.2.10'
        self.assertFalse(request_is_local(rd))

    def test_cross_site(self):
        from calibre_zen.host.endpoints import cross_site

        self.assertFalse(cross_site(None, '127.0.0.1:8080'))
        self.assertFalse(cross_site('http://127.0.0.1:8080', '127.0.0.1:8080'))
        self.assertTrue(cross_site('https://evil.example', '127.0.0.1:8080'))
        self.assertTrue(cross_site('null', '127.0.0.1:8080'))

    def request(self, remote_addr, **headers):
        "A request as calibre's handler sees it. The tray's Host unless given; None leaves it out."
        headers = {'Host': '127.0.0.1:8080', **headers}
        headers = {k: v for k, v in headers.items() if v is not None}
        return types.SimpleNamespace(remote_addr=remote_addr, forwarded_for=None, inheaders=headers)

    def test_stop_is_refused_from_elsewhere(self):
        from calibre.srv.errors import HTTPForbidden
        from calibre_zen.host.endpoints import zen_stop

        host = mock.Mock()
        ctx = types.SimpleNamespace(zen_host=host)
        rebound = self.request('127.0.0.1', Origin='http://evil.example:8080', Host='evil.example:8080')
        for rd in (self.request('192.0.2.10'), self.request('127.0.0.1', Origin='https://evil.example'), rebound):
            with self.assertRaises(HTTPForbidden):
                zen_stop(ctx, rd)
        host.stop_soon.assert_not_called()
        self.assertEqual(zen_stop(ctx, self.request('127.0.0.1', Host='127.0.0.1:8080')), {'stopping': True})
        host.stop_soon.assert_called_once_with()

    def test_status_from_elsewhere_follows_the_login_rules(self):
        from calibre_zen.host.endpoints import zen_status

        host = mock.Mock()
        host.status.return_value = {'app': 'calibre-zen'}
        ctx = types.SimpleNamespace(zen_host=host)
        self.assertEqual(zen_status(ctx, self.request('127.0.0.1')), {'app': 'calibre-zen'})
        host.auth_controller.assert_not_called()
        rd = self.request('192.0.2.10')
        zen_status(ctx, rd)
        host.auth_controller.assert_called_once_with(rd, zen_status)
        # A page on another site, its name pointed at 127.0.0.1, reads no paths without a login.
        host.auth_controller.reset_mock()
        rebound = self.request('127.0.0.1', Host='evil.example:8080')
        zen_status(ctx, rebound)
        host.auth_controller.assert_called_once_with(rebound, zen_status)
        host.auth_controller = None  # --enable-auth off: anyone may ask
        self.assertEqual(zen_status(ctx, rd), {'app': 'calibre-zen'})


class Launch(unittest.TestCase):
    def test_worker_env_does_not_start_a_temp_folder_here(self):
        "base_dir() would start calibre's safe_atexit process inside the tray."
        from calibre_zen.host import launch

        boom = AssertionError('base_dir() was called')
        with (
            mock.patch('calibre.ptempfile.base_dir', side_effect=boom),
            mock.patch('calibre.utils.ipc.launch.base_dir', side_effect=boom),
            mock.patch.dict(os.environ, {'CALIBRE_WORKER_TEMP_DIR': 'abc'}),
        ):
            env = launch.worker_env(['--port', '1'])
        self.assertNotIn('CALIBRE_WORKER_TEMP_DIR', env)
        self.assertEqual(env['CALIBRE_SIMPLE_WORKER'], 'calibre_zen.host.main:worker_main')
        self.assertEqual(json.loads(env[launch.ARGS_ENV]), ['--port', '1'])
        self.assertEqual(env['CALIBRE_WORKER'], '1')


class Lock(Scratch):
    def test_a_held_lock_is_status_3(self):
        from calibre_zen.host import main

        lib = make_library(os.path.join(self.mkdtemp(), 'lib'))
        env = {k: v for k, v in os.environ.items() if k != 'CALIBRE_NO_SI_DANGER_DANGER'}
        err = io.StringIO()
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch('calibre.utils.lock.singleinstance', return_value=False) as si,
            mock.patch.object(main, 'Host', side_effect=AssertionError('the server must not be built')),
            contextlib.redirect_stderr(err),
        ):
            rc = main.main(['--port', str(free_port()), '--no-auto-add', lib])
        self.assertEqual(rc, main.EXIT_LOCKED)
        si.assert_called_once_with('db')
        lines = err.getvalue().strip().splitlines()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn('already open', lines[0])


class ManageUsers(Scratch):
    """
    calibre-server's shape: with --manage-users the positional arguments are
    the user command. ./calibre-zen passes its library in --zen-library, which
    must never join them, or `add bob` would make the library path bob's
    password.
    """

    def users(self):
        return os.path.join(self.mkdtemp(), 'users.sqlite')

    def test_the_launchers_library_is_not_a_password(self):
        from calibre.srv.users import UserManager
        from calibre_zen.host import main

        userdb = self.users()
        lib = self.mkdtemp()
        argv = ['--zen-library', lib, '--userdb', userdb, '--manage-users', '--', 'add', 'bob']
        with mock.patch('sys.stdin', io.StringIO('secret')), mock.patch.object(main, 'take_lock', side_effect=AssertionError('no lock to manage users')):
            self.assertEqual(main.main(argv), 0)
        m = UserManager(userdb)
        self.assertEqual(m.get('bob'), 'secret')
        self.assertEqual(m.all_user_names, {'bob'})

    def test_no_command_is_the_interactive_one(self):
        from calibre_zen.host import main

        argv = ['--zen-library', self.mkdtemp(), '--userdb', self.users(), '--manage-users']
        with mock.patch('calibre.srv.manage_users_cli.manage_users_cli') as cli:
            self.assertEqual(main.main(argv), 0)
        self.assertEqual(cli.call_args.args[1], [])

    def test_the_launchers_library_is_served_after_named_ones(self):
        from calibre_zen.host import main, options

        base = self.mkdtemp()
        named = make_library(os.path.join(base, 'named'))
        launcher = make_library(os.path.join(base, 'launcher'))
        opts, paths = options.parse(['--zen-library', launcher, named], options.light_parser())
        self.assertEqual(main.resolve_libraries(paths, opts.zen_library), [named, launcher])
        self.assertEqual(main.resolve_libraries([], launcher), [launcher])
        self.assertEqual(main.resolve_libraries([launcher + os.sep], launcher), [launcher + os.sep], 'served once')
        with self.assertRaises(SystemExit):
            main.resolve_libraries([], os.path.join(base, 'nothing here'))


class AutoAdd(Scratch):
    def setUp(self):
        from calibre.db.legacy import LibraryDatabase

        base = self.mkdtemp()
        self.folder = os.path.join(base, 'add')
        os.mkdir(self.folder)
        self.legacy = LibraryDatabase(make_library(os.path.join(base, 'lib')))
        self.addCleanup(self.legacy.close)
        self.db = self.legacy.new_api
        self.logged = []

    def adder(self, **prefs):
        from calibre_zen.host.autoadd import AutoAdder

        return AutoAdder(self.folder, lambda: self.db, log=self.logged.append, prefs=prefs, poll=60)

    def drop(self, name: str, text: str = 'Some words in a book.\n') -> str:
        path = os.path.join(self.folder, name)
        with open(path, 'w') as f:
            f.write(text)
        return path

    def titles(self) -> set[str]:
        return set(self.db.all_field_for('title', self.db.all_book_ids()).values())

    def test_a_file_is_added_once_it_has_settled_and_then_deleted(self):
        a = self.adder()
        path = self.drop('Delta.txt')
        self.assertEqual(a.scan(), 0, 'first sight: not yet')
        with open(path, 'a') as f:
            f.write('More words, still being copied.\n')
        self.assertEqual(a.scan(), 0, 'it changed since the last poll')
        self.assertEqual(a.scan(), 1, self.logged)
        self.assertFalse(os.path.exists(path))
        self.assertIn('Delta', self.titles())
        snap = a.snapshot()
        self.assertEqual((snap['added'], snap['failed'], snap['folder']), (1, 0, self.folder))
        self.assertTrue(snap['last'])

    def test_an_epub_brings_its_own_metadata(self):
        from calibre.utils.resources import get_path

        src = get_path('quick_start/eng.epub')
        if not src or not os.path.exists(src):
            self.skipTest('no quick start guide in this calibre')
        shutil.copy(src, os.path.join(self.folder, 'whatever.epub'))
        a = self.adder()
        a.scan()
        self.assertEqual(a.scan(), 1, self.logged)
        (book_id,) = set(self.db.all_book_ids()) - {1, 2, 3}
        self.assertNotEqual(self.db.field_for('title', book_id), 'whatever')
        self.assertIn('EPUB', self.db.formats(book_id))

    def test_a_duplicate_is_left_in_the_folder_and_not_tried_again(self):
        a = self.adder(auto_add_check_for_duplicates=True)
        path = self.drop('Alpha.txt')
        a.scan()
        self.assertEqual(a.scan(), 0)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(a.snapshot()['duplicates'], 1)
        with mock.patch.object(a, 'add_one') as add_one:
            a.scan()
        add_one.assert_not_called()
        self.assertEqual(len(self.db.all_book_ids()), 3)

    def test_duplicates_are_added_when_not_checked(self):
        a = self.adder()
        self.drop('Alpha.txt')
        a.scan()
        self.assertEqual(a.scan(), 1, self.logged)
        self.assertEqual(len(self.db.all_book_ids()), 4)

    def test_what_is_not_a_book_stays_put(self):
        a = self.adder(blocked_auto_formats=['txt'])
        self.drop('notes.xyz')
        self.drop('blocked.txt')
        open(os.path.join(self.folder, 'downloading.epub'), 'w').close()  # Firefox's empty placeholder
        os.mkdir(os.path.join(self.folder, 'a folder.epub'))
        self.assertEqual(a.candidates(), {})
        everything = self.adder(auto_add_everything=True, blocked_auto_formats=['txt'])
        self.assertEqual(set(everything.candidates()), {'notes.xyz'})

    def test_a_failure_is_counted_and_the_file_kept(self):
        from calibre_zen.host.autoadd import AutoAdder

        def broken():
            raise OSError('the library went away')

        a = AutoAdder(self.folder, broken, log=self.logged.append, prefs={}, poll=60)
        path = self.drop('Epsilon.txt')
        a.scan()
        self.assertEqual(a.scan(), 0)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(a.snapshot()['failed'], 1)
        with mock.patch.object(a, 'add_one') as add_one:
            a.scan()
        add_one.assert_not_called()


STATUS_KEYS = {
    'app',
    'version',
    'calibre',
    'pid',
    'started',
    'uptime',
    'port',
    'url_prefix',
    'urls',
    'auth',
    'local_write',
    'libraries',
    'jobs',
    'auto_add',
    'memory_mb',
}


class HostProcess(Scratch):
    """
    One real host for the class, started with launch.start as the tray
    starts it. The port and local_write come from the Sharing settings, not
    the command line. Login is on, to show /zen/status does not need one from
    here while the library still does. The last test stops it.
    """

    proc = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from calibre.srv.opts import DEFAULT_CONFIG
        from calibre_zen.host import launch

        cls.port = free_port()
        cls.config = DEFAULT_CONFIG
        with open(cls.config, 'w') as f:
            f.write(f'port {cls.port}\nlocal_write True\n')
        cls.library = make_library(os.path.join(cls.tmp, 'library'))
        cls.folder = os.path.join(cls.tmp, 'add')
        os.mkdir(cls.folder)
        cls.log = os.path.join(cls.tmp, 'host.log')
        cls.args = ['--enable-auth', '--disable-use-bonjour', '--auto-add', cls.folder, cls.library]
        cls.url = launch.local_url(cls.args)
        env = {'CALIBRE_NO_SI_DANGER_DANGER': '1', 'CALIBRE_ZEN_AUTO_ADD_POLL': '0.5'}
        with mock.patch.dict(os.environ, env):
            cls.proc = launch.start(cls.args, cls.log)
        # The first start in a fresh checkout compiles the web app.
        deadline = time.monotonic() + 120
        while launch.status(cls.url) is None:
            if cls.proc.poll() is not None or time.monotonic() > deadline:
                cls.tearDownClass()
                raise RuntimeError(f'the host did not start ({cls.proc.returncode}):\n{cls.read_log()}')
            time.sleep(0.25)

    @classmethod
    def tearDownClass(cls):
        if cls.proc is not None and cls.proc.poll() is None:
            cls.proc.terminate()
            try:
                cls.proc.wait(15)
            except Exception:
                cls.proc.kill()
                cls.proc.wait()
        with contextlib.suppress(OSError):
            os.remove(cls.config)
        super().tearDownClass()

    @classmethod
    def read_log(cls) -> str:
        try:
            with open(cls.log, errors='replace') as f:
                return f.read()[-4000:]
        except OSError:
            return ''

    def status(self) -> dict:
        from calibre_zen.host import launch

        ans = launch.status(self.url)
        self.assertIsNotNone(ans, self.read_log())
        return ans

    def test_status_schema(self):
        from calibre.constants import __version__, zen_version

        s = self.status()
        self.assertLessEqual(STATUS_KEYS, set(s))
        self.assertEqual((s['app'], s['version'], s['calibre']), ('calibre-zen', zen_version, __version__))
        self.assertEqual(s['pid'], self.proc.pid)
        self.assertEqual(s['port'], self.port)
        self.assertEqual(s['url_prefix'], '')
        self.assertTrue(s['auth'])
        self.assertTrue(s['local_write'], 'from server-config.txt')
        self.assertIsInstance(s['uptime'], float)
        self.assertRegex(s['started'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$')
        self.assertIsInstance(s['urls'], list)
        for url in s['urls']:
            self.assertRegex(url, rf'^http://.+:{self.port}/$')
        self.assertEqual(s['jobs'], {'running': 0, 'waiting': 0})
        self.assertIsInstance(s['memory_mb'], float)
        (lib,) = s['libraries']
        self.assertEqual(set(lib), {'id', 'name', 'path', 'open', 'books'})
        self.assertEqual(os.path.realpath(lib['path']), os.path.realpath(self.library))
        self.assertEqual(lib['books'] is None, not lib['open'])
        self.assertEqual(s['auto_add']['folder'], self.folder)

    def test_the_library_still_needs_a_login(self):
        import urllib.error
        import urllib.request

        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.build_opener(urllib.request.ProxyHandler({})).open(self.url + '/ajax/library-info', timeout=5)
        self.assertEqual(cm.exception.code, 401)

    def test_auto_add_reaches_the_library(self):
        path = os.path.join(self.folder, 'Zeta.txt')
        with open(path, 'w') as f:
            f.write('A book dropped into the folder.\n')
        deadline = time.monotonic() + 60
        while True:
            s = self.status()
            if s['auto_add']['added'] >= 1 and not os.path.exists(path):
                break
            if time.monotonic() > deadline:
                self.fail(f'not added: {json.dumps(s["auto_add"])}\n{self.read_log()}')
            time.sleep(0.25)
        self.assertEqual(s['auto_add']['failed'], 0)
        self.assertTrue(s['auto_add']['last'])
        (lib,) = s['libraries']
        self.assertTrue(lib['open'])
        self.assertEqual(lib['books'], 4)

    def test_zz_stop_ends_the_process_cleanly(self):
        from calibre_zen.host import launch

        self.assertTrue(launch.stop(self.url, timeout=20), self.read_log())
        self.assertEqual(self.proc.wait(20), 0, self.read_log())
        self.assertIsNone(launch.status(self.url, timeout=0.5))

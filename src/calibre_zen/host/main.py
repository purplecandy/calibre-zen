#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The host process: calibre-server's start-up, step for step, plus the zen parts.

`main` follows calibre.srv.standalone.main -- parse, users, the single-instance
lock, libraries, Server, signals, a headless QApplication for drawing covers,
serve_forever -- with these differences:

    defaults        the GUI's Sharing settings (options.py)
    the lock        held by someone else is exit status 3 and one line, not a
                    paragraph and status 1, so the tray can tell "the main
                    window is open" from a crash
    fixes           calibre_zen.host.fixes.install() before the server is built
    routes          /zen/status and /zen/stop (endpoints.py)
    auto-add        a watched folder (autoadd.py)
    the web app     in develop mode calibre-server recompiles it at every
                    start: about 11 s and 360 MB that stay resident. The host
                    only does that when the compiled app is missing or older
                    than its sources (`web_app_is_current`)
    --auto-reload   refused: it restarts calibre-server, not the host

`worker_main` is the entry for launch.start: calibre's worker executable runs
it through CALIBRE_SIMPLE_WORKER, with the arguments as JSON in
CALIBRE_ZEN_HOST_ARGS.
"""

import json
import os
import signal
import sys
import time
from datetime import UTC, datetime
from threading import Timer

EXIT_LOCKED = 3
LOCKED_MESSAGE = 'the library is already open in another calibre-zen program, such as its main window'
ARGS_ENV = 'CALIBRE_ZEN_HOST_ARGS'
STOP_DELAY = 0.2  # seconds between answering /zen/stop and stopping, so the answer gets out


def say(msg: str) -> None:
    print(f'calibre-zen host: {msg}', file=sys.stderr, flush=True)


def take_lock() -> bool:
    "The `db` lock calibre-server, calibredb and the main window take. True if this process now holds it."
    if 'CALIBRE_NO_SI_DANGER_DANGER' in os.environ:
        return True
    from calibre.utils import lock

    return bool(lock.singleinstance('db'))


def resolve_libraries(paths: list[str], launcher_library: str | None = None) -> list[str]:
    """
    calibre-server's rules: the ones given must exist; with none, the GUI's,
    then prefs['library_path']. `launcher_library` is --zen-library, the one
    ./calibre-zen chose: served after the ones named, and once.
    """
    from calibre.db.legacy import LibraryDatabase
    from calibre.srv.library_broker import load_gui_libraries
    from calibre.utils.config import prefs

    paths = list(paths)
    if launcher_library and not any(same_path(launcher_library, p) for p in paths):
        paths.append(launcher_library)
    override = os.environ.get('CALIBRE_OVERRIDE_DATABASE_PATH')
    for lib in paths:
        if not lib or (not LibraryDatabase.exists_at(lib) and not override):
            raise SystemExit(f'There is no calibre library at: {lib}')
    libraries = paths or load_gui_libraries()
    if not libraries:
        if not prefs['library_path']:
            raise SystemExit('There is no calibre library to serve. Give a library folder.')
        libraries = [prefs['library_path']]
    if override:
        if len(libraries) > 1:
            raise SystemExit('Cannot use more than one library with CALIBRE_OVERRIDE_DATABASE_PATH')
        if not os.path.exists(override):
            raise SystemExit(f'No database found at CALIBRE_OVERRIDE_DATABASE_PATH: {override}')
    return libraries


def same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


# The web app in develop mode {{{


def web_app_inputs(base: str):
    "Every file calibre.utils.rapydscript.compile_srv reads."
    for top in (os.path.join(base, 'src', 'pyj'), os.path.join(base, 'imgsrc', 'srv')):
        for dirpath, _dirs, files in os.walk(top):
            for f in files:
                yield os.path.join(dirpath, f)
    cs = os.path.join(base, 'resources', 'content-server')
    for f in ('index.html', 'reset.css', 'base.css'):
        yield os.path.join(cs, f)
    yield os.path.join(base, 'src', 'calibre', 'srv', 'render_book.py')


def web_app_is_current() -> bool:
    "Whether the compiled web app exists and is newer than everything it is compiled from."
    from calibre.utils.rapydscript import base_dir

    base = base_dir()
    try:
        built = os.stat(os.path.join(base, 'resources', 'content-server', 'index-generated.html')).st_mtime
    except OSError:
        return False
    newest = 0.0
    for path in web_app_inputs(base):
        try:
            newest = max(newest, os.stat(path).st_mtime)
        except OSError:
            pass
    return newest <= built


# }}}


class Host:
    "One server, its routes, its watched folder, and what /zen/status reports about them."

    def __init__(self, libraries, opts, auto_add_folder=None):
        from calibre.srv import standalone
        from calibre_zen.host import endpoints

        self.opts = opts
        self.started = time.monotonic()
        self.started_at = datetime.now(UTC).isoformat(timespec='seconds')
        compile_web_app = standalone.is_running_from_develop
        if compile_web_app and web_app_is_current():
            # Server.__init__ reads the flag from its own module; this process
            # is the only one that sees the change.
            standalone.is_running_from_develop = False
        try:
            self.server = standalone.Server(libraries, opts)
        finally:
            standalone.is_running_from_develop = compile_web_app
        self.handler = self.server.handler
        self.ctx = self.handler.router.ctx
        if not self.ctx.library_broker.lmap:
            raise SystemExit('None of these is a calibre library: ' + ', '.join(libraries))
        self.ctx.zen_host = self
        endpoints.install(self.handler.router)
        self.auto_adder = None
        if auto_add_folder:
            from calibre_zen.host.autoadd import AutoAdder

            self.auto_adder = AutoAdder(auto_add_folder, self.default_db, notify=self.ctx.notify_changes, log=self.log)

    @property
    def auth_controller(self):
        return self.handler.auth_controller

    @property
    def loop(self):
        return self.server.loop

    def log(self, *args) -> None:
        self.loop.log(*args)

    def default_db(self):
        "The library auto-add adds to: the first one, as the main window adds to the one it shows."
        return self.ctx.library_broker.get(None)

    def serve(self) -> None:
        if self.auto_adder is not None:
            self.log('Watching for books to add in:', self.auto_adder.folder)
            self.auto_adder.start()
        try:
            self.server.serve_forever()
        finally:
            if self.auto_adder is not None:
                self.auto_adder.stop()
            self.handler.close()

    def stop(self) -> None:
        self.server.stop()

    def stop_soon(self) -> None:
        t = Timer(STOP_DELAY, self.stop)
        t.daemon = True
        t.start()

    def port(self) -> int:
        ba = self.loop.bound_address
        if isinstance(ba, tuple) and len(ba) > 1:
            return int(ba[1])
        return int(self.opts.port)

    def status(self) -> dict:
        from calibre.constants import __appname__, __version__, zen_version
        from calibre_zen.host import endpoints

        port = self.port()
        return {
            'app': __appname__,
            'version': zen_version,
            'calibre': __version__,
            'pid': os.getpid(),
            'started': self.started_at,
            'uptime': round(time.monotonic() - self.started, 1),
            'port': port,
            'url_prefix': (self.opts.url_prefix or '').rstrip('/'),
            'urls': endpoints.share_urls(self.opts, port),
            'auth': bool(self.opts.auth),
            'local_write': bool(self.opts.local_write),
            'libraries': endpoints.libraries(self.ctx.library_broker),
            'jobs': endpoints.jobs(self.loop.jobs_manager),
            'auto_add': None if self.auto_adder is None else self.auto_adder.snapshot(),
            'memory_mb': endpoints.memory_mb(),
        }


def main(argv: list[str] | None = None) -> int:
    from calibre_zen.host import options

    argv = sys.argv[1:] if argv is None else list(argv)
    opts, paths = options.parse(argv, options.full_parser())

    if opts.auto_reload and not opts.manage_users:
        say('--auto-reload is not supported; run calibre-server for that')
        return 2
    if opts.userdb:
        from calibre.srv.users import connect

        opts.userdb = os.path.abspath(os.path.expandvars(os.path.expanduser(opts.userdb)))
        connect(opts.userdb, exc_class=SystemExit).close()
    if opts.manage_users:
        from calibre.srv.manage_users_cli import manage_users_cli

        # As in calibre-server, the positional arguments are the user command
        # here, not libraries. --zen-library is an option so it never joins them.
        try:
            manage_users_cli(opts.userdb, paths)
        except KeyboardInterrupt, EOFError:
            raise SystemExit('Interrupted by user')
        return 0

    if not take_lock():
        say(LOCKED_MESSAGE)
        return EXIT_LOCKED

    libraries = resolve_libraries(paths, opts.zen_library)
    folder, explicit = options.auto_add_folder(opts)
    if folder:
        from calibre_zen.host.autoadd import usable_folder

        if not usable_folder(folder):
            if explicit:
                say(f'--auto-add: {folder} is not a folder this program can read and write')
                return 2
            say(f'not watching {folder}: it is not a folder this program can read and write')
            folder = None

    opts.auto_reload_port = int(os.environ.get('CALIBRE_AUTORELOAD_PORT', '0'))
    opts.allow_console_print = 'CALIBRE_ALLOW_CONSOLE_PRINT' in os.environ
    for name in ('log', 'access_log'):
        value = getattr(opts, name)
        if value and os.path.isdir(value):
            say(f'--{name.replace("_", "-")} must point to a file, not a folder')
            return 2

    from calibre.srv.loop import BadIPSpec
    from calibre_zen.host import fixes

    fixes.install()
    try:
        host = Host(libraries, opts, folder)
    except BadIPSpec as e:
        raise SystemExit(f'{e}')

    if getattr(opts, 'daemonize', False):
        from calibre.srv.standalone import daemonize

        if not opts.log:
            raise SystemExit('In order to daemonize you must specify a log file, you can use /dev/stdout to log to screen even as a daemon')
        daemonize()
    if opts.pidfile:
        with open(opts.pidfile, 'wb') as f:
            f.write(str(os.getpid()).encode('ascii'))

    signal.signal(signal.SIGTERM, lambda s, f: host.stop())
    if hasattr(signal, 'SIGHUP') and not getattr(opts, 'daemonize', False):
        signal.signal(signal.SIGHUP, lambda s, f: host.stop())

    # Covers are drawn with Qt, as calibre-server does: a headless
    # QApplication, so no window, no Dock icon and no display needed.
    from calibre.gui2 import ensure_app, load_builtin_fonts

    ensure_app(), load_builtin_fonts()
    from calibre.srv.utils import HandleInterrupt

    with HandleInterrupt(host.stop):
        host.serve()
    return 0


def worker_main() -> None:
    "The CALIBRE_SIMPLE_WORKER entry launch.start uses."
    raw = os.environ.pop(ARGS_ENV, '') or '[]'
    try:
        argv = json.loads(raw)
    except ValueError:
        say(f'{ARGS_ENV} is not JSON: {raw!r}')
        raise SystemExit(2)
    if not isinstance(argv, list) or not all(isinstance(x, str) for x in argv):
        say(f'{ARGS_ENV} must be a JSON list of strings')
        raise SystemExit(2)
    raise SystemExit(main(argv))

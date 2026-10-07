#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The two content-server bugs in host/fixes.py, each reproduced against
calibre's own code and then shown gone with the fix on.

Both are races, so neither waits for load to find them. Each forces the one
interleaving that breaks, with events, and a deadlock is a join that times
out. Every thread is a daemon, so a test that finds a deadlock can still let
the process exit. No server is started and no single-instance lock taken:
the tests drive calibre's Cache and the server's Context directly, which is
where both bugs live.

docs/plans/modes/upstream-bugs.md has the bugs; the upstream patches in
docs/plans/modes/upstream/ are the same changes as fixes.py.
"""

import ast
import os
import shutil
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace

from calibre_zen.host import fixes
from calibre_zen.tests.base import make_library, work_dir

# How long a thread gets before it is called stuck. Nothing here does real
# work, so this is generous.
STUCK = 3.0
DONE = 15.0
# apsw does not fail a second thread at once: it retries the busy connection
# for about 0.4 s first, which is why the bug shows as a few percent of
# requests and not most of them. B gets longer than that to fail.
APSW_WAIT = 2.0


class Worker(threading.Thread):
    "A daemon thread that keeps its result or its exception."

    def __init__(self, name, target):
        super().__init__(name=name, daemon=True)
        self.target_ = target
        self.result = self.error = None

    def run(self):
        try:
            self.result = self.target_()
        except BaseException as e:
            self.error = e


def wait_for(predicate, timeout=DONE, step=0.005) -> bool:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            return bool(predicate())
        time.sleep(step)
    return True


class GatedLock:
    """
    Context.lock, with a pause just after one named thread first takes it.
    Lets a test hold a thread inside the lock while it queues a writer.
    """

    def __init__(self, inner, thread_name):
        self.inner = inner
        self.thread_name = thread_name
        self.taken = threading.Event()
        self.go = threading.Event()

    def acquire(self, *args, **kwargs):
        ans = self.inner.acquire(*args, **kwargs)
        if threading.current_thread().name == self.thread_name and not self.taken.is_set():
            self.taken.set()
            self.go.wait(DONE)
        return ans

    def release(self):
        self.inner.release()

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *a):
        self.release()


class SrvFixCase(unittest.TestCase):
    "Each test sets the fixes on or off itself and leaves them as it found them."

    def setUp(self):
        self.was_installed = fixes.installed()
        self.addCleanup(self.restore)
        self.tmp = tempfile.mkdtemp(prefix='srvfix-', dir=work_dir())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def restore(self):
        if self.was_installed:
            fixes.apply()
        else:
            fixes.remove()

    def set_fixed(self, on: bool) -> None:
        if on:
            fixes.apply()
        else:
            fixes.remove()
        self.assertEqual(fixes.installed(), on)

    def library(self) -> str:
        return make_library(os.path.join(self.tmp, 'library'))


class NotesConnection(SrvFixCase):
    """
    Bug 1. Two readers inside @read_api methods at once, both running SQL on
    the one apsw connection. The first is held mid-statement by SQLite's
    progress handler; the second then runs.
    """

    def open_with_notes(self):
        from calibre.db.backend import DB
        from calibre.db.cache import Cache

        cache = Cache(DB(self.library()))
        cache.init()
        self.addCleanup(cache.close)
        aid = cache.get_item_id('authors', 'Ann Author')
        cache.set_notes_for('authors', aid, 'Writes about the alphabet.')
        book_id = next(iter(cache.search('title:Alpha')))
        return cache, book_id, {'authors': {aid: 'Ann Author'}}

    def race(self, cache, call):
        """
        Run `call` in A, stop A inside its first SQL statement, run `call` in
        B, then let A go. Returns (A, B, whether B was still waiting when A
        was let go).
        """
        conn = cache.backend.conn
        inside, go = threading.Event(), threading.Event()

        def progress():
            if threading.current_thread().name == 'zen-srvfix-A' and not inside.is_set():
                inside.set()
                go.wait(DONE)
            return 0

        conn.set_progress_handler(progress, 1)
        self.addCleanup(conn.set_progress_handler, None)
        a = Worker('zen-srvfix-A', call)
        a.start()
        self.assertTrue(inside.wait(DONE), 'A never reached SQL')
        b = Worker('zen-srvfix-B', call)
        b.start()
        b.join(APSW_WAIT)
        b_waited = b.is_alive()
        go.set()
        a.join(DONE)
        b.join(DONE)
        self.assertFalse(a.is_alive() or b.is_alive(), 'a reader never finished')
        return a, b, b_waited

    def test_unfixed_second_reader_fails(self):
        import apsw

        self.set_fixed(False)
        cache, book_id, expected = self.open_with_notes()
        a, b, _ = self.race(cache, lambda: cache.items_with_notes_in_book(book_id))
        self.assertIsNone(a.error)
        self.assertEqual(a.result, expected)
        self.assertIsInstance(b.error, apsw.ThreadingViolationError)

    def test_fixed_second_reader_waits(self):
        self.set_fixed(True)
        cache, book_id, expected = self.open_with_notes()
        a, b, b_waited = self.race(cache, lambda: cache.items_with_notes_in_book(book_id))
        self.assertIsNone(a.error)
        self.assertIsNone(b.error)
        self.assertTrue(b_waited, 'B ran beside A instead of waiting for the connection')
        self.assertEqual((a.result, b.result), (expected, expected))

    def test_unfixed_page_count_thread_fails(self):
        import apsw

        self.set_fixed(False)
        cache, book_id, expected = self.open_with_notes()
        mpc = cache.maintain_page_counts
        a, b, _ = self.race(cache, lambda: tuple(mpc.get_batch()))
        self.assertIsNone(a.error)
        self.assertIsInstance(b.error, apsw.ThreadingViolationError)

    def test_fixed_page_count_thread_waits(self):
        # The page-count thread reads SQL outside any Cache method.
        self.set_fixed(True)
        cache, book_id, expected = self.open_with_notes()
        mpc = cache.maintain_page_counts
        a, b, b_waited = self.race(cache, lambda: tuple(mpc.get_batch()))
        self.assertIsNone(a.error)
        self.assertIsNone(b.error)
        self.assertTrue(b_waited)

    def test_fixed_writer_beside_readers(self):
        # A writer and readers on one Cache, as the GUI and its server are:
        # many rounds, nothing raises and nothing waits for good.
        self.set_fixed(True)
        cache, book_id, expected = self.open_with_notes()
        aid = next(iter(expected['authors']))
        stop = threading.Event()

        def read():
            while not stop.is_set():
                cache.items_with_notes_in_book(book_id)
                cache.notes_data_for('authors', aid)
                cache.annotation_count_for_book(book_id)

        def write():
            for i in range(60):
                cache.set_notes_for('authors', aid, f'Note {i}')
                cache.set_field('rating', {book_id: 2 * (i % 5)})

        readers = [Worker(f'zen-srvfix-r{i}', read) for i in range(4)]
        writer = Worker('zen-srvfix-w', write)
        for t in readers + [writer]:
            t.start()
        writer.join(DONE * 2)
        stop.set()
        for t in readers:
            t.join(DONE)
        self.assertFalse(any(t.is_alive() for t in readers + [writer]), 'a thread is stuck')
        self.assertEqual([t.error for t in readers + [writer]], [None] * 5)


class TagBrowserDeadlock(SrvFixCase):
    """
    Bug 2. The three threads of the cycle, in the order that closes it:

    R, a page of books, holds the read lock (code.py's get_books);
    T, the tag browser, holds Context.lock and next wants the read lock;
    W, a write, queues for the write lock, so T's read lock must wait.
    R then calls Context.search and wants Context.lock.
    """

    def open_context(self):
        from calibre.srv.handler import Context
        from calibre.srv.library_broker import LibraryBroker
        from calibre.srv.opts import Options

        ctx = Context(LibraryBroker([self.library()]), Options(userdb=':memory:'))
        db = ctx.library_broker.get()
        return ctx, db

    def run_cycle(self):
        from calibre.srv.metadata import categories_as_json, categories_settings

        ctx, db = self.open_context()
        rd = SimpleNamespace(username=None, is_trusted_ip=True)
        book_id = next(iter(db.all_book_ids()))
        gate = ctx.lock = GatedLock(ctx.lock, 'zen-srvfix-T')
        r_holds, r_go = threading.Event(), threading.Event()

        def page_of_books():
            with db.safe_read_lock:
                r_holds.set()
                r_go.wait(DONE)
                return ctx.search(rd, db, 'tags:fiction')

        def tag_browser():
            opts = categories_settings({}, db, gst_container=tuple)
            return categories_as_json(ctx, rd, db, opts, '')

        def write():
            db.set_field('rating', {book_id: 8})

        r = Worker('zen-srvfix-R', page_of_books)
        r.start()
        self.assertTrue(r_holds.wait(DONE))
        t = Worker('zen-srvfix-T', tag_browser)
        t.start()
        self.assertTrue(gate.taken.wait(DONE), 'T never took Context.lock')
        w = Worker('zen-srvfix-W', write)
        w.start()
        # The write lock's own queue is the only way to know W is waiting.
        self.assertTrue(wait_for(lambda: bool(db.write_lock._shlock._exclusive_queue)), 'W never queued')
        gate.go.set()
        r_go.set()
        threads = (r, t, w)
        for x in threads:
            x.join(STUCK)
        stuck = [x.name for x in threads if x.is_alive()]
        if stuck:
            # Break the cycle so the library can close: let R have
            # Context.lock. T's own release then finds it unlocked.
            gate.inner.release()
            for x in threads:
                x.join(DONE)
        if not any(x.is_alive() for x in threads):
            ctx.library_broker.close()
        return stuck, r, t, w

    def test_unfixed_deadlocks(self):
        self.set_fixed(False)
        stuck, r, t, w = self.run_cycle()
        self.assertEqual(stuck, ['zen-srvfix-R', 'zen-srvfix-T', 'zen-srvfix-W'])

    def test_fixed_finishes(self):
        self.set_fixed(True)
        stuck, r, t, w = self.run_cycle()
        self.assertEqual(stuck, [])
        self.assertEqual([r.error, t.error, w.error], [None, None, None])
        self.assertEqual(len(r.result), 2)  # Alpha and Gamma are fiction
        self.assertIn(b'tags', t.result)


class Install(SrvFixCase):
    def test_apply_is_idempotent_and_removable(self):
        from calibre.db.cache import Cache
        from calibre.srv.handler import Context

        def current():
            return Cache.__dict__['notes_for'], Cache.__dict__['_notes_for'], Context.__dict__['search']

        fixes.remove()
        stock = current()
        self.assertIs(stock[0], stock[1])
        fixes.apply()
        once = current()
        fixes.apply()
        self.assertEqual(current(), once)
        self.assertIs(once[0], once[1])
        self.assertIsNot(once[0], stock[0])
        self.assertIsNot(once[2], stock[2])
        fixes.remove()
        self.assertEqual(current(), stock)

    def test_switch(self):
        fixes.remove()
        old = os.environ.get(fixes.ENV)
        os.environ[fixes.ENV] = '0'
        try:
            fixes.install()
            self.assertFalse(fixes.installed())
        finally:
            if old is None:
                del os.environ[fixes.ENV]
            else:
                os.environ[fixes.ENV] = old
        fixes.install()
        self.assertEqual(fixes.installed(), fixes.enabled())

    def test_window_installs(self):
        # hooks.install() runs as the Application is made, before a library
        # opens, so the server the window embeds gets the fixes.
        from calibre_zen.tests.base import app

        app()
        from calibre_zen import hooks
        from calibre_zen.report import guard

        if hooks.enabled() and fixes.enabled():
            self.assertEqual(guard.states().get('srvfix'), guard.OK)

    def test_every_patched_name_exists(self):
        from calibre.db.cache import Cache, cache_api
        from calibre.srv.handler import Context

        for name in fixes.SQL_READ_API:
            self.assertIs(cache_api.get(name), False, f'{name} is no longer a @read_api method')
            self.assertIn('_' + name, Cache.__dict__, f'{name} lost its unlocked alias')
        for name in fixes.CONTEXT_METHODS:
            self.assertIn(name, Context.__dict__)

    def test_audit_is_complete(self):
        """
        Every @read_api method that touches self.backend is either serialized
        or known not to run SQL. A calibre update that adds one fails here, so
        it gets looked at.
        """
        import calibre.db.cache as cache_mod

        with open(cache_mod.__file__, encoding='utf-8') as f:
            tree = ast.parse(f.read())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Cache')
        touching = set()
        for fn in cls.body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            if not any(isinstance(d, ast.Name) and d.id == 'read_api' for d in fn.decorator_list):
                continue
            for node in ast.walk(fn):
                if isinstance(node, ast.Attribute) and node.attr == 'backend' and isinstance(node.value, ast.Name) and node.value.id == 'self':
                    touching.add(fn.name)
                    break
        known = set(fixes.SQL_READ_API) | set(fixes.NOT_SQL_READ_API)
        self.assertEqual(touching - known, set(), 'new @read_api methods touch the backend: audit them')
        self.assertEqual(set(fixes.SQL_READ_API) - touching, set())

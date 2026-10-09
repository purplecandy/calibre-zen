#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
A watched folder, without the main window.

calibre's own auto-add (gui2/auto_add.py) returns early when there is no main
window: it adds through the book list's model and asks about duplicates in a
dialog. This is the same behaviour on a thread, adding through the server's
own library, so the server's caches see the new book the way they see one
added over HTTP (srv/cdb.py does exactly this).

What matches the main window:

    which files      a regular file, not empty, readable and writable, whose
                     name passes the Adding books filter rules, else whose
                     extension is an e-book format calibre auto-adds, minus
                     the blocked ones -- or every format, when "add
                     everything" is on
    metadata         read in a worker process with fork_job, which also runs
                     the file-type import plugins; when that fails, from the
                     file name
    rules            the tag and author mapping rules for adding
    duplicates       checked only when "check for duplicates" is on, as in
                     the main window; otherwise a duplicate is just added
    after adding     the file is deleted from the folder
    on failure       the file stays where it is

What differs, because there is nobody to ask:

    copying          the main window waits two seconds after a change and
                     hopes. Here a file is only taken when its size and
                     modification time are the same at two polls in a row
    a duplicate      the main window asks. Here the file is left in the
                     folder and not tried again until it changes. Deleting
                     a book nobody chose to drop would lose it
    a failure        the main window shows an error. Here it is logged,
                     counted in /zen/status, and the file is not tried
                     again until it changes
    auto-convert     not done: converting needs the main window's convert
                     action. The book is added in the format it came in

The gui preferences are read from gui.json once, at start, without importing
calibre.gui2: the tray restarts the host when a setting changes.
"""

import os
import stat
import sys
import traceback
from datetime import UTC, datetime
from threading import Event, Lock, Thread

POLL_ENV = 'CALIBRE_ZEN_AUTO_ADD_POLL'
DEFAULT_POLL = 3.0  # seconds; a file waits between one and two polls before it is added

# The gprefs keys auto-add reads, with calibre.gui2's defaults for them.
PREF_DEFAULTS = {
    'auto_add_check_for_duplicates': False,
    'auto_add_everything': False,
    'blocked_auto_formats': [],
    'add_filter_rules': [],
    'tag_map_on_add_rules': [],
    'author_map_on_add_rules': [],
}

# Formats the main window never auto-adds (gui2/auto_add.py, AUTO_ADDED).
NEVER_AUTO_ADDED = frozenset(('pdr', 'mbp', 'tan'))


def read_prefs() -> dict:
    from calibre.utils.config import JSONConfig

    g = JSONConfig('gui')
    return {key: g.get(key, default) for key, default in PREF_DEFAULTS.items()}


def poll_interval() -> float:
    try:
        return max(0.1, float(os.environ.get(POLL_ENV) or DEFAULT_POLL))
    except ValueError:
        return DEFAULT_POLL


class AllBut:
    "Every format except some. 'Add everything' with a block list."

    def __init__(self, blocked):
        self.blocked = frozenset(blocked)

    def __contains__(self, fmt):
        return fmt not in self.blocked


def allowed_formats(prefs):
    from calibre.ebooks import BOOK_EXTENSIONS

    blocked = frozenset(prefs['blocked_auto_formats'] or ())
    if prefs['auto_add_everything']:
        return AllBut(blocked)
    return frozenset(BOOK_EXTENSIONS) - NEVER_AUTO_ADDED - blocked


def usable_folder(path) -> bool:
    return bool(path) and os.path.isdir(path) and os.access(path, os.R_OK | os.W_OK)


def inside(path: str, directory: str) -> bool:
    "Whether `path` is `directory` or below it, after following links."
    try:
        path, directory = os.path.realpath(path), os.path.realpath(directory)
        return os.path.normcase(os.path.commonpath((path, directory))) == os.path.normcase(directory)
    except ValueError:  # different drives on Windows
        return False


def folder_problem(folder, libraries=()) -> str | None:
    """
    Why `folder` cannot be watched, to follow "it", or None. Besides being
    usable, it must not overlap a library being served: inside one, a book's
    own files would be added as new books and then deleted; holding one, the
    same, a level up. The main window and the tray refuse such a folder too.
    """
    if not usable_folder(folder):
        return 'is not a folder this program can read and write'
    for lib in libraries:
        if not lib:
            continue
        if inside(folder, lib):
            return f'is inside the library {lib}'
        if inside(lib, folder):
            return f'holds the library {lib}'
    return None


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec='seconds')


class AutoAdder(Thread):
    """
    Polls `folder` every `poll` seconds and adds what has settled to the
    library `get_db()` returns -- a Cache, opened on first need.

    `notify(library_path, change_event)` is the server context's
    notify_changes, so anything listening to the server hears about the book.
    """

    def __init__(self, folder, get_db, notify=None, log=None, prefs=None, poll=None):
        Thread.__init__(self, name='ZenAutoAdd', daemon=True)
        self.folder = folder
        self.get_db = get_db
        self.notify = notify
        self.log = log or (lambda *a: print(*a, file=sys.stderr))
        self.prefs = read_prefs() if prefs is None else {**PREF_DEFAULTS, **prefs}
        self.allowed = allowed_formats(self.prefs)
        self.rules = self.compile_rules()
        self.poll = poll_interval() if poll is None else poll
        self.stopped = Event()
        self.lock = Lock()
        self.seen: dict[str, tuple[int, int]] = {}  # name -> (size, mtime_ns) at the last poll
        self.settled: dict[str, tuple[int, int]] = {}  # left in the folder: not tried again until it changes
        self.added = self.failed = self.duplicates = 0
        self.last: str | None = None
        self.folder_was_usable = True

    def compile_rules(self):
        from calibre.db.adding import compile_rule

        try:
            return tuple(map(compile_rule, self.prefs['add_filter_rules'] or ()))
        except Exception:
            traceback.print_exc()
            return ()

    # The thread {{{

    def run(self):
        while not self.stopped.wait(self.poll):
            try:
                self.scan()
            except Exception:
                self.log('Auto-add: scanning failed:\n' + traceback.format_exc())

    def stop(self, timeout: float = 10) -> None:
        self.stopped.set()
        if self.is_alive():
            self.join(timeout)

    def snapshot(self) -> dict:
        with self.lock:
            return {
                'folder': self.folder,
                'added': self.added,
                'failed': self.failed,
                'duplicates': self.duplicates,
                'last': self.last,
            }

    # }}}

    def is_filename_allowed(self, name: str) -> bool:
        from calibre.db.adding import filter_filename

        allowed = filter_filename(self.rules, name)
        if allowed is None:
            allowed = os.path.splitext(name)[1][1:].lower() in self.allowed
        return bool(allowed)

    def candidates(self) -> dict[str, tuple[int, int]]:
        ans = {}
        for name in os.listdir(self.folder):
            path = os.path.join(self.folder, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            # Firefox writes an empty placeholder while it downloads.
            if not stat.S_ISREG(st.st_mode) or st.st_size <= 0:
                continue
            if not os.access(path, os.R_OK | os.W_OK) or not self.is_filename_allowed(name):
                continue
            ans[name] = (st.st_size, st.st_mtime_ns)
        return ans

    def scan(self) -> int:
        "One poll. Returns how many books were added."
        if not usable_folder(self.folder):
            if self.folder_was_usable:
                self.log(f'Auto-add: {self.folder} is not a folder this program can read and write; waiting for it')
            self.folder_was_usable = False
            self.seen = {}
            return 0
        self.folder_was_usable = True
        current = self.candidates()
        ready = [name for name, key in current.items() if self.seen.get(name) == key and self.settled.get(name) != key]
        self.seen = current
        self.settled = {name: key for name, key in self.settled.items() if current.get(name) == key}
        count = 0
        for name in sorted(ready, key=lambda n: current[n][1]):
            if self.stopped.is_set():
                break
            count += self.add_one(name, current[name])
        return count

    def add_one(self, name: str, key: tuple[int, int]) -> int:
        from calibre.ptempfile import TemporaryDirectory

        path = os.path.join(self.folder, name)
        try:
            # On Windows a file another program is still writing cannot be opened.
            open(path, 'rb').close()
        except OSError:
            self.seen.pop(name, None)
            return 0
        with TemporaryDirectory('_zen_auto_add') as tdir:
            mi, book_path = self.read_metadata(name, path, tdir)
            if mi is None:  # it changed while being read; it settles again first
                self.seen.pop(name, None)
                return 0
            return self.add(name, key, path, book_path, mi)

    def read_metadata(self, name, path, tdir):
        """
        (metadata, path to add) the way the main window reads them, or
        (None, None) when the file changed while it was being read.
        """
        from calibre.ebooks.metadata.meta import metadata_from_filename
        from calibre.ebooks.metadata.opf2 import OPF
        from calibre.utils.ipc.simple_worker import WorkerError, fork_job

        try:
            fork_job('calibre.ebooks.metadata.meta', 'forked_read_metadata', (path, tdir), no_output=True)
        except WorkerError as e:
            self.log(f'Auto-add: failed to read metadata from {name}:\n{e.orig_tb}')
        except Exception:
            self.log(f'Auto-add: failed to read metadata from {name}:\n{traceback.format_exc()}')

        book_path = path
        changed = os.path.join(tdir, 'file_changed_by_plugins')
        if os.path.exists(changed):
            with open(changed) as f:
                book_path = f.read()
        try:
            with open(os.path.join(tdir, 'size.txt'), 'rb') as f:
                size_when_read = int(f.read())
        except OSError, ValueError:
            size_when_read = None  # the worker never got that far; the name is all we have
        if size_when_read is not None:
            try:
                if size_when_read != os.stat(book_path).st_size:
                    return None, None
            except OSError:
                return None, None

        mi = None
        opf = os.path.join(tdir, 'metadata.opf')
        try:
            if os.stat(opf).st_size >= 30:
                with open(opf, 'rb') as f:
                    mi = OPF(f, tdir, populate_spine=False).to_book_metadata()
        except Exception:
            mi = None
        if mi is None:
            mi = metadata_from_filename(name)
        return mi, book_path

    def map_metadata(self, mi, db) -> None:
        if self.prefs['tag_map_on_add_rules']:
            from calibre.ebooks.metadata.tag_mapper import map_tags

            mi.tags = map_tags(mi.tags, self.prefs['tag_map_on_add_rules'])
        if self.prefs['author_map_on_add_rules']:
            from calibre.ebooks.metadata.author_mapper import compile_rules, map_authors

            authors = map_authors(mi.authors, compile_rules(self.prefs['author_map_on_add_rules']))
            if authors != mi.authors:
                mi.authors = authors
                mi.author_sort = db.author_sort_from_authors(authors)

    def add(self, name, key, path, book_path, mi) -> int:
        fmt = os.path.splitext(os.path.basename(book_path))[1][1:].upper()
        try:
            db = self.get_db()
            if db is None:
                raise RuntimeError('there is no library to add to')
            self.map_metadata(mi, db)
            ids, duplicates = db.add_books([(mi, {fmt: book_path})], add_duplicates=not self.prefs['auto_add_check_for_duplicates'])
        except Exception:
            self.log(f'Auto-add: failed to add {name}, leaving it in {self.folder}:\n{traceback.format_exc()}')
            with self.lock:
                self.failed += 1
            self.settled[name] = key
            return 0
        if not ids:
            self.log(f'Auto-add: {name} is already in the library, leaving it in {self.folder}')
            with self.lock:
                self.duplicates += 1
            self.settled[name] = key
            return 0
        if self.notify is not None:
            from calibre.srv.changes import books_added

            try:
                self.notify(db.backend.library_path, books_added(ids))
            except Exception:
                traceback.print_exc()
        try:
            os.remove(path)
        except OSError:
            # Added but still there: it must not be added a second time.
            self.log(f'Auto-add: added {name} but could not delete it:\n{traceback.format_exc()}')
            self.settled[name] = key
        with self.lock:
            self.added += len(ids)
            self.last = now_iso()
        self.log(f'Auto-add: added {name} as book {ids[0]}')
        return len(ids)

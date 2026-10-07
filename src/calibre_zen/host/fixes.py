#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Two content-server bugs, worked around from outside.

docs/plans/modes/upstream-bugs.md has the evidence and
docs/plans/modes/upstream/ the patches meant for calibre. Each fix here is the
same change as its patch, applied by wrapping instead of editing, so the two
can be read side by side.

1. Reads share one SQLite connection.

   A `@read_api` method of `Cache` holds the shared read lock, so many threads
   run them at once. Most read only the in-memory tables. The ones named in
   SQL_READ_API run SQL on the backend's single apsw connection, which allows
   one call at a time, and a second thread gets `ThreadingViolationError` --
   an HTTP 500 from the server.

   Fix: a mutex per connection around each of those methods. `Cache.__init__`
   wraps whatever the class holds under a public name in the read lock, so
   replacing the class attribute (and its unlocked alias `_name`, which other
   Cache methods call while already locked) puts the mutex inside the read
   lock. Nothing inside the mutex takes another lock or waits on a thread, so
   it is a leaf: it cannot close a cycle with the read lock, the write lock,
   or anything the GUI holds. Writers hold the lock exclusively and never meet
   a reader, so they need no mutex for their own SQL.

   Two readers run SQL outside any Cache method and get the same mutex:
   `MaintainPageCounts.get_batch` (the page-count thread every library runs)
   and `DB.get_next_fts_job` (the full-text indexer's dispatcher).

   Only a Cache made after install() gets the mutex on its public methods,
   because `Cache.__init__` binds them. The GUI installs this as its
   Application is made, before any library is open, and the host before it
   builds the server.

2. Two lock orders for one pair of locks.

   `Context.search`, `Context.get_categories` and `Context.get_tag_browser`
   take `Context.lock`, then call into the library, which takes its read
   lock. `get_books` and `ajax/search` hold the read lock, then call
   `Context.search`. With a writer queued, a new reader waits behind it
   (db/locking.py), and the three threads wait on each other for good. The
   tag browser runs on the server's event loop, so the whole server stops.

   Fix: those three methods take the library's read lock first. The read lock
   is reentrant for a thread that already holds it, even with a writer
   queued, and `safe_read_lock` does nothing for a thread holding the write
   lock. One order everywhere: read lock, then `Context.lock`, then the
   connection mutex. calibre's repair of a broken link table needs the write
   lock in the middle of that, so it is run outside both (`_read_locked`).

Off with CALIBRE_ZEN_SRVFIX=0. For the GUI's embedded server it is also off
with CALIBRE_ZEN_STYLE=0, which turns the whole overlay off.
"""

import os
from functools import wraps
from threading import Lock, RLock

ENV = 'CALIBRE_ZEN_SRVFIX'
OFF_VALUES = frozenset({'0', 'false', 'no', 'off'})

# Cache's @read_api methods whose body runs SQL on the backend's connection.
# Audited against calibre 9.15's db/cache.py: every @read_api method that
# touches self.backend, less those that only read an attribute, the file
# system or the in-memory prefs.
SQL_READ_API = (
    # Notes
    'notes_for',
    'notes_data_for',
    'get_all_items_that_have_notes',
    'items_with_notes_in_book',
    'get_notes_resource',
    'notes_resources_used_by',
    'export_note',
    # Annotations
    'annotations_map_for_book',
    'all_annotations_for_book',
    'annotation_count_for_book',
    'all_annotation_users',
    'all_annotation_types',
    'all_annotations',
    'all_annotation_styles',
    'search_annotations',
    # Reading positions and page counts
    'get_last_read_positions',
    'get_pages',
    'pages_needs_scan',
    'num_of_books_that_need_pages_counted',
    # Plugin data and conversion options
    'get_custom_book_data',
    'get_ids_for_custom_book_data',
    'conversion_options',
    'has_conversion_options',
    # Grouping by date, case-sensitive item lookup, the read-only clone
    'books_by_year',
    'books_by_month',
    'get_item_id',
    'get_item_ids',
    'clone_for_readonly_access',
)

# The other @read_api methods that touch self.backend, and why they are safe:
# they read an attribute, the in-memory prefs, or the file system, never the
# connection. test_srvfix.py fails when calibre adds one to neither list.
NOT_SQL_READ_API = (
    'last_modified',  # os.stat of metadata.db
    'is_fts_enabled',  # an attribute
    'field_supports_notes',  # an attribute
    'pref',  # the prefs dict, loaded at open
    'size_stats',  # os.path.getsize
    'format_hash',
    'cover_or_cache',
    'cover_last_modified',
    'cover_timestamp',
    'copy_cover_to',
    'copy_format_to',
    'format_abspath',
    'has_format',
    'formats',
    'read_backup',
    'get_top_level_move_items',
    'list_trash_entries',
    'copy_format_from_trash',
    'copy_book_from_trash',
    'are_paths_inside_book_dir',
    'list_extra_files',
    'copy_extra_file_to',
)

# Context methods that took Context.lock before the library's read lock.
CONTEXT_METHODS = ('get_categories', 'get_tag_browser', 'search')

# Where the mutex lives on a backend. Upstream would make it in DB.__init__.
LOCK_ATTR = 'zen_connection_lock'

_originals: dict[tuple[type, str], object] = {}
_state = Lock()
_lazy = Lock()


def enabled() -> bool:
    return os.environ.get(ENV, '1').lower() not in OFF_VALUES


def install() -> None:
    "Apply both fixes unless CALIBRE_ZEN_SRVFIX=0. Safe to call more than once."
    if enabled():
        apply()


def installed() -> bool:
    return bool(_originals)


def connection_lock(backend) -> RLock:
    "The one mutex for `backend`'s connection, made on first use."
    lock = backend.__dict__.get(LOCK_ATTR)
    if lock is None:
        with _lazy:
            lock = backend.__dict__.get(LOCK_ATTR)
            if lock is None:
                lock = RLock()
                setattr(backend, LOCK_ATTR, lock)
    return lock


def apply() -> None:
    "Both fixes, whatever the environment says. Idempotent."
    with _state:
        if _originals:
            return
        from calibre.db.backend import DB
        from calibre.db.cache import Cache
        from calibre.db.page_count import MaintainPageCounts
        from calibre.srv.handler import Context

        for name in SQL_READ_API:
            orig = Cache.__dict__.get(name)
            if orig is None:
                continue
            wrapped = _serialized(orig)
            _replace(Cache, name, wrapped)
            if Cache.__dict__.get('_' + name) is orig:
                _replace(Cache, '_' + name, wrapped)
        _replace(DB, 'get_next_fts_job', _serialized_backend(DB.__dict__['get_next_fts_job']))
        _replace(MaintainPageCounts, 'get_batch', _serialized_batch(MaintainPageCounts.__dict__['get_batch']))
        for name in CONTEXT_METHODS:
            _replace(Context, name, _read_locked(Context.__dict__[name]))


def remove() -> None:
    """
    Put calibre's own methods back. For tests and before/after comparisons;
    a Cache made while the fixes were on keeps them on its public methods.
    """
    with _state:
        for (cls, name), orig in _originals.items():
            setattr(cls, name, orig)
        _originals.clear()


def _replace(cls: type, name: str, new) -> None:
    _originals[(cls, name)] = cls.__dict__[name]
    setattr(cls, name, new)


def _serialized(func):
    "A Cache method, run holding its backend's connection mutex."

    @wraps(func)
    def serialized(self, *args, **kwargs):
        with connection_lock(self.backend):
            return func(self, *args, **kwargs)

    return serialized


def _serialized_backend(func):
    "A DB method, run holding its own connection mutex."

    @wraps(func)
    def serialized(self, *args, **kwargs):
        with connection_lock(self):
            return func(self, *args, **kwargs)

    return serialized


def _serialized_batch(func):
    """
    MaintainPageCounts.get_batch, a generator that runs SQL under the read
    lock. The read lock comes first here too; the original takes it again,
    which is reentrant.
    """

    @wraps(func)
    def get_batch(self, size: int = 100):
        db = self.dbref()
        if db is None:
            return
        with db.safe_read_lock, connection_lock(db.backend):
            yield from func(self, size)

    return get_batch


def _read_locked(func):
    """
    A Context method, run holding the library's read lock before it takes
    Context.lock.

    One thing in calibre needs the write lock below these methods:
    `Cache.get_categories` repairs a link table that names a missing item
    (`InvalidLinkTable`) by taking it. A thread holding the read lock cannot,
    and SHLock says so with `LockingError`. So when that is what went wrong,
    the repair runs here with no lock held -- not the read lock, not
    Context.lock -- and the method runs again. Holding nothing while it waits
    for the write lock is what keeps the repair out of the lock cycle. A
    caller that already held the read lock gets the error, as it does from
    calibre's own ajax.py.
    """
    from calibre.db.fields import InvalidLinkTable
    from calibre.db.locking import LockingError

    @wraps(func)
    def read_locked(self, request_data, db, *args, **kwargs):
        try:
            with db.safe_read_lock:
                return func(self, request_data, db, *args, **kwargs)
        except LockingError as err:
            if not isinstance(err.__context__, InvalidLinkTable):
                raise
        # Every book, so every broken item is found; it repairs one field at
        # a time until none is left.
        db.get_categories()
        with db.safe_read_lock:
            return func(self, request_data, db, *args, **kwargs)

    return read_locked

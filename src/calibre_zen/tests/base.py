#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
What a test builds on: one offscreen Application for the whole process, a
temporary library with a few books, and a way to wait for Qt.

The Application is made once and never quit. calibre's own Application is a
singleton in every sense, and the overlay installs into it at construction
(gui2/__init__.py), so every test sees the overlay exactly as a user would.
"""

import os
import shutil
import tempfile
import unittest

_app = None

# title, authors, tags, series. Three books is enough for a search to leave
# one, for two to share an author, and for a series to appear once.
BOOKS = (
    ('Alpha', ['Ann Author'], ['fiction'], 'Greek'),
    ('Beta', ['Bob Writer'], ['history'], 'Greek'),
    ('Gamma', ['Ann Author'], ['fiction', 'long'], None),
)


def app():
    "The process's one Application, made on first use."
    global _app
    if _app is None:
        from calibre.gui2 import Application

        _app = Application(['calibre-zen-test'], force_calibre_style=True)
    return _app


def process_events(ms: int = 0) -> None:
    "Let Qt run: pending events only, or for `ms` milliseconds of event loop."
    from qt.core import QCoreApplication, QEventLoop, QTimer

    if ms <= 0:
        QCoreApplication.processEvents()
        return
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def wait_until(predicate, timeout_ms: int = 5000, step_ms: int = 25) -> bool:
    """
    Run the event loop until `predicate()` is true or the timeout passes.
    Returns the predicate's final answer, so a caller asserts on it.
    """
    from calibre.utils.monotonic import monotonic

    deadline = monotonic() + timeout_ms / 1000
    while True:
        if predicate():
            return True
        if monotonic() > deadline:
            return bool(predicate())
        process_events(step_ms)


def work_dir() -> str:
    "The run's scratch directory, from ./zen-test; removed when it exits."
    return os.environ.get('CALIBRE_ZEN_TEST_DIR') or tempfile.gettempdir()


def make_library(path: str, books=BOOKS) -> str:
    """
    A new library at `path` holding `books`, metadata only. Returns the path.
    The database is closed again; the caller opens it the way the code under
    test would.
    """
    from calibre.db.legacy import LibraryDatabase
    from calibre.ebooks.metadata.book.base import Metadata

    os.makedirs(path, exist_ok=True)
    db = LibraryDatabase(path)
    try:
        # A new library comes with the Quick Start Guide; the tests want
        # exactly `books`, so it goes.
        db.new_api.remove_books(db.new_api.all_book_ids())
        for title, authors, tags, series in books:
            mi = Metadata(title, authors)
            mi.tags = list(tags)
            if series:
                mi.series = series
            db.new_api.create_book_entry(mi)
    finally:
        db.close()
    return path


class ZenTestCase(unittest.TestCase):
    """
    A test with the Application up and a per-class scratch directory.

    `self.tmp` is removed after the class; a test that needs its own uses
    `self.mkdtemp()`, which is removed after the test.
    """

    tmp = ''

    @classmethod
    def setUpClass(cls):
        app()
        cls.tmp = tempfile.mkdtemp(prefix=cls.__name__ + '-', dir=work_dir())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def mkdtemp(self) -> str:
        d = tempfile.mkdtemp(dir=self.tmp)
        self.addCleanup(shutil.rmtree, d, True)
        return d

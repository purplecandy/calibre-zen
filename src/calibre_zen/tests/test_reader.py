#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The spare reader: a real viewer process, started, handed a book, retired.

Each test starts calibre's own viewer through spare.py, offscreen, with its
output in a log the test reads -- the spare says what it is doing there when
CALIBRE_DEBUG is set. A spare takes a couple of seconds to come up, so these
are the slow tests; they are also the only ones that prove a hand-off reaches
a window rather than a mock of one.
"""

import os
import zipfile

from calibre_zen.tests.base import ZenTestCase, wait_until

START_MS = 60000  # a cold web engine on a slow CI machine
CONTAINER = '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>'''
OPF = '''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:title>Spare</dc:title><dc:identifier id="id">spare-test</dc:identifier><dc:language>en</dc:language>
</metadata>
<manifest><item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/></manifest>
<spine><itemref idref="c1"/></spine>
</package>'''
CHAPTER = '''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>One</title></head>
<body><h1>One</h1><p>A book small enough to open at once.</p></body></html>'''


def make_epub(path: str) -> str:
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml', CONTAINER)
        z.writestr('content.opf', OPF)
        z.writestr('c1.xhtml', CHAPTER)
    return path


class TestSpareReader(ZenTestCase):
    def setUp(self):
        from calibre.gui2.viewer.config import vprefs
        from calibre_zen.reader.spare import Spare

        # The first reader on a new profile migrates the old viewer's
        # settings, which is a write to the file a spare watches: it would
        # retire itself once, by design. The tests start past that.
        if not vprefs['old_prefs_migrated']:
            vprefs.set('old_prefs_migrated', True)

        d = self.mkdtemp()
        self.book = make_epub(os.path.join(d, 'spare.epub'))
        self.log_path = os.path.join(d, 'spare.log')
        self.log = open(self.log_path, 'wb')
        self.addCleanup(self.log.close)
        self.spare = Spare(extra_env={'CALIBRE_DEBUG': '1'}, output=self.log)
        self.addCleanup(self.stop)

    def stop(self):
        p = self.spare.process
        self.spare.shutdown()
        if p is not None and p.poll() is None:
            p.kill()
            p.wait(10)

    def output(self) -> str:
        with open(self.log_path, encoding='utf-8', errors='replace') as f:
            return f.read()

    def start_and_wait(self):
        self.assertTrue(self.spare.start(), 'the spare did not start')
        self.process = self.spare.process
        ok = wait_until(lambda: 'reader: waiting' in self.output() or self.process.poll() is not None, START_MS)
        self.assertTrue(ok and self.process.poll() is None, 'the spare never came up:\n' + self.output()[-3000:])

    def test_waits_unseen_and_opens_a_handed_book(self):
        self.start_and_wait()
        self.assertNotIn('reader: shown', self.output(), 'a spare showed its window before it had a book')
        self.assertTrue(self.spare.hand_off(self.book, book_data=None))
        self.assertIsNone(self.spare.process, 'a spare that took a book is no longer ours to retire')
        ok = wait_until(lambda: 'reader: loaded' in self.output(), START_MS)
        self.assertTrue(ok, 'the handed book never loaded:\n' + self.output()[-3000:])
        out = self.output()
        self.assertLess(out.index('reader: shown'), out.index('reader: loaded'))
        self.assertIn(self.book, out)
        self.process.kill()
        self.process.wait(10)

    def test_retired_spare_leaves_without_saving(self):
        from calibre_zen.reader.spare import settings_mtime

        self.start_and_wait()
        before = settings_mtime()
        self.spare.retire()
        self.assertTrue(wait_until(lambda: self.process.poll() is not None, 15000), 'a retired spare kept running')
        self.assertEqual(self.process.returncode, 0)
        self.assertEqual(settings_mtime(), before, 'a retired spare wrote the viewer settings it read at startup')
        self.assertIn('reader: abandoned', self.output())

    def test_stale_spare_is_not_used(self):
        from calibre_zen.reader.spare import settings_path

        self.start_and_wait()
        # Another reader saving its settings: the spare read the old ones.
        path = settings_path()
        st = os.stat(path) if os.path.exists(path) else None
        if st is None:
            with open(path, 'w') as f:
                f.write('{}')
        else:
            os.utime(path, (st.st_atime, st.st_mtime + 5))
        self.assertFalse(self.spare.hand_off(self.book), 'a spare with stale settings took a book')
        self.assertTrue(wait_until(lambda: self.process.poll() is not None, 15000), 'the stale spare was not retired')
        self.assertTrue(self.spare.timer.isActive(), 'no replacement was scheduled')

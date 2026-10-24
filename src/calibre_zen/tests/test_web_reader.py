#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
calibre's web reader in zen's look: the page at the server's root carries the
reader sheet and the line icons, asks for its fonts by address, and keeps
calibre's own redirect and login rule. The reading itself is in
web/e2e/read.spec.ts, in a browser.
"""

import os
import shutil
import tempfile
import unittest
from unittest import mock

from calibre_zen.tests.base import make_library, work_dir


class Page(unittest.TestCase):
    def test_style_and_icons_go_in(self):
        from calibre.utils.resources import get_path
        from calibre_zen.reader.look import STYLE_ID
        from calibre_zen.web import reader_look

        with open(get_path('content-server/index-generated.html'), 'rb') as f:
            html = f.read()
        out = reader_look.page(html)
        self.assertEqual(out.count(f'<style id="{STYLE_ID}">'.encode()), 1)
        self.assertLess(out.index(STYLE_ID.encode()), out.index(b'</head>'))
        self.assertIn(b'url("zen/fonts/', out)
        self.assertNotIn(b'data:font/ttf', out, 'the fonts are served, not inline')
        self.assertIn(b'font-display: swap', out)
        # A mapped symbol is drawn as a line, the way the desktop reader's is.
        self.assertIn(b'stroke="currentColor"', out)
        self.assertNotIn(b'stroke="currentColor"', html)

    def test_a_broken_part_leaves_the_page(self):
        from calibre_zen.web import reader_look

        html = b'<html><head></head><body>calibre</body></html>'
        with mock.patch.object(reader_look, 'stylesheet', side_effect=RuntimeError('boom')):
            self.assertEqual(reader_look.page(html), html)

    def test_font_paths(self):
        from calibre_zen.theme import generate
        from calibre_zen.theme.tokens import primitives
        from calibre_zen.web import reader_look

        font = primitives.active_font()
        good = f'{font["dir"]}/{font["faces"][0]}'
        self.assertEqual(reader_look.resolve_font(good), os.path.realpath(os.path.join(generate.FONTS_DIR, good)))
        for bad in ('', '../serve.py', f'{font["dir"]}/../../theme/generate.py', '.hidden/x.ttf', f'{font["dir"]}/OFL.txt', 'nope/none.ttf'):
            self.assertIsNone(reader_look.resolve_font(bad), bad)


class Served(unittest.TestCase):
    "A real calibre server, with /app/ and the look added the way the host adds them."

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix=cls.__name__ + '-', dir=work_dir())
        cls.library = make_library(os.path.join(cls.tmp, 'library'))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def server(self, look=True, **opts):
        from calibre.srv.tests.base import LibraryServer
        from calibre_zen.web import reader_look, serve

        p = mock.patch.object(reader_look, 'enabled', return_value=look)
        p.start()
        self.addCleanup(p.stop)
        server = LibraryServer(self.library, **opts)
        self.assertTrue(serve.install(server.handler.router))
        return server

    def get(self, server, path, headers=None):
        conn = server.connect()
        try:
            conn.request('GET', path, headers=headers or {})
            r = conn.getresponse()
            return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()
        finally:
            conn.close()

    def font_path(self, body: bytes) -> str:
        start = body.index(b'url("zen/fonts/') + len(b'url("')
        return body[start : body.index(b'"', start)].decode()

    def test_root_page_and_fonts(self):
        with self.server() as server:
            status, headers, body = self.get(server, '/')
            self.assertEqual(status, 200)
            self.assertIn('text/html', headers['content-type'])
            self.assertIn(b'<style id="zen-reader-look">', body)
            status, _, _ = self.get(server, '/', {'If-None-Match': headers['etag']})
            self.assertEqual(status, 304, 'made once, then the browser keeps it')

            status, headers, font = self.get(server, '/' + self.font_path(body))
            self.assertEqual(status, 200)
            self.assertEqual(headers['content-type'], 'font/ttf')
            self.assertIn('max-age', headers['cache-control'])
            self.assertGreater(len(font), 10_000)
            self.assertEqual(self.get(server, '/zen/fonts/../web/serve.py')[0], 404)

            # The rest of calibre is untouched.
            self.assertEqual(self.get(server, '/interface-data/update')[0], 200)

    def test_under_a_prefix(self):
        with self.server(url_prefix='/books') as server:
            status, headers, _ = self.get(server, '/books')
            self.assertIn(status, (301, 302, 307, 308), "calibre's own redirect to the directory is kept")
            self.assertTrue(headers['location'].endswith('/books/'))
            status, _, body = self.get(server, '/books/')
            self.assertEqual(status, 200)
            self.assertIn(b'zen-reader-look', body)
            self.assertEqual(self.get(server, '/books/' + self.font_path(body))[0], 200)

    def test_public_behind_a_login(self):
        "calibre's page is public; so are the look and its fonts. The books are not."
        with self.server(auth=True) as server:
            status, _, body = self.get(server, '/')
            self.assertEqual(status, 200)
            self.assertEqual(self.get(server, '/' + self.font_path(body))[0], 200)
            self.assertEqual(self.get(server, '/interface-data/update')[0], 401)

    def test_switched_off(self):
        with self.server(look=False) as server:
            status, _, body = self.get(server, '/')
            self.assertEqual(status, 200)
            self.assertNotIn(b'zen-reader-look', body)
            self.assertEqual(self.get(server, '/zen/fonts/inter/Inter-Regular.ttf')[0], 404)

    def test_follows_the_reader_look_switch(self):
        from calibre_zen import features
        from calibre_zen.web import reader_look

        with mock.patch.dict(features._at_start, clear=True), mock.patch.dict(os.environ, {'CALIBRE_ZEN_READER_LOOK': '0'}):
            self.assertFalse(reader_look.enabled())
        with mock.patch.dict(features._at_start, clear=True), mock.patch.dict(os.environ, {'CALIBRE_ZEN_READER_LOOK': '1'}):
            self.assertTrue(reader_look.enabled())

    def test_wrapped_once(self):
        from calibre.srv.tests.base import LibraryServer
        from calibre_zen.web import reader_look

        server = LibraryServer(self.library)
        try:
            router = server.handler.router
            self.assertTrue(reader_look.wrap_index(router))
            self.assertFalse(reader_look.wrap_index(router))
            self.assertTrue(router.routes[''].endpoint.f.zen_reader_look)
        finally:
            server.handler.close()

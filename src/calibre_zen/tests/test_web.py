#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The new web app at /app/: its colours are the desktop's, and calibre's server
serves its build under any prefix, with the right caching and behind nothing
but calibre's own login for the data.

The build here is a small stand-in written per test, so these run without
Node. The real one is built and checked by CI's web job.
"""

import os
import shutil
import tempfile
import unittest
from unittest import mock

from calibre_zen.tests.base import make_library, work_dir

SENTINEL = '/__zen_prefix__'


def repo_root() -> str:
    d = os.path.dirname
    return d(d(d(d(os.path.abspath(__file__)))))


def fake_build(root: str) -> str:
    "A dist/ shaped like Astro's, with the placeholder where Astro puts the base."
    files = {
        'index.html': f'<link rel="manifest" href="{SENTINEL}/app/manifest.webmanifest"><script src="{SENTINEL}/app/_astro/a.js"></script>',
        'book/index.html': f'<a href="{SENTINEL}/app/">home</a>',
        '_astro/a.js': f'const BASE="{SENTINEL}/app/";',
        'manifest.webmanifest': '{"start_url": "./"}',
        'sw.js': 'self.addEventListener("install", () => {})',
        '.hidden': 'no',
    }
    for name, text in files.items():
        path = os.path.join(root, *name.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(text)
    with open(os.path.join(root, 'icon.png'), 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + SENTINEL.encode())
    with open(os.path.join(os.path.dirname(root), 'secret.txt'), 'w') as f:
        f.write('outside')
    return root


class Scratch(unittest.TestCase):
    tmp = ''

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix=cls.__name__ + '-', dir=work_dir())
        cls.library = make_library(os.path.join(cls.tmp, 'library'))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def mkdtemp(self) -> str:
        d = tempfile.mkdtemp(dir=self.tmp)
        self.addCleanup(shutil.rmtree, d, True)
        return d


class Tokens(unittest.TestCase):
    def test_tokens_css_is_current(self):
        "web/src/styles/tokens.css is what the schemes say today."
        from calibre_zen.web import tokens

        with open(tokens.output_path(), encoding='utf-8') as f:
            on_disk = f.read()
        self.assertEqual(
            on_disk,
            tokens.css(),
            'web/src/styles/tokens.css is stale: regenerate it, see calibre_zen/web/tokens.py',
        )

    def test_every_scheme_and_mode_is_there(self):
        from calibre_zen.theme.tokens import schemes
        from calibre_zen.web import tokens

        css = tokens.css()
        for name, scheme in schemes.SCHEMES.items():
            self.assertIn(f":root[data-scheme='{name}'] {{", css)
            self.assertIn(f":root[data-scheme='{name}'].dark {{", css)
            if scheme.dim:
                self.assertIn(f":root[data-scheme='{name}'].dark.dim {{", css)

    def test_neutral_is_shadcns_neutral(self):
        "The default scheme reads as shadcn's own preset, where the two agree."
        from calibre_zen.theme.tokens import schemes
        from calibre_zen.web import tokens

        light = tokens.variables(schemes.SCHEMES['neutral'], 'light')
        self.assertEqual(light['background'], '#ffffff')
        self.assertEqual(light['primary'], '#171717')
        self.assertEqual(light['muted-foreground'], '#737373')
        self.assertEqual(light['border'], '#e5e5e5')
        dark = tokens.variables(schemes.SCHEMES['neutral'], 'dark')
        self.assertEqual(dark['background'], '#0a0a0a')
        self.assertEqual(dark['primary'], '#e5e5e5')
        self.assertEqual(dark['muted-foreground'], '#a1a1a1')

    def test_icon_is_the_apps(self):
        "web/public/icon.svg is a copy of imgsrc/calibre.svg, for the install icons."
        root = repo_root()
        with open(os.path.join(root, 'imgsrc', 'calibre.svg'), 'rb') as a, open(os.path.join(root, 'web', 'public', 'icon.svg'), 'rb') as b:
            self.assertEqual(a.read(), b.read())


class Resolve(Scratch):
    def test_paths(self):
        from calibre_zen.web import serve

        dist = fake_build(os.path.join(self.mkdtemp(), 'dist'))
        self.assertEqual(serve.resolve('', dist), os.path.realpath(os.path.join(dist, 'index.html')))
        self.assertEqual(serve.resolve('book', dist), os.path.realpath(os.path.join(dist, 'book', 'index.html')))
        self.assertEqual(serve.resolve('_astro/a.js', dist), os.path.realpath(os.path.join(dist, '_astro', 'a.js')))
        self.assertIsNone(serve.resolve('../secret.txt', dist))
        self.assertIsNone(serve.resolve('book/../../secret.txt', dist))
        self.assertIsNone(serve.resolve('.hidden', dist))
        self.assertIsNone(serve.resolve('missing.js', dist))

    def test_rewrite(self):
        from calibre_zen.web import serve

        self.assertEqual(serve.rewrite(b'"/__zen_prefix__/app/x"', ''), b'"/app/x"')
        self.assertEqual(serve.rewrite(b'"/__zen_prefix__/app/x"', '/books'), b'"/books/app/x"')

    def test_sentinel_matches_the_build(self):
        "serve.py and web/paths.mjs agree on the placeholder."
        from calibre_zen.web import serve

        with open(os.path.join(repo_root(), 'web', 'paths.mjs')) as f:
            self.assertIn(f"PREFIX_SENTINEL = '{serve.SENTINEL.decode()}'", f.read())


class Served(Scratch):
    "A real calibre server, with /app/ added the way the host adds it."

    def server(self, **opts):
        from calibre.srv.tests.base import LibraryServer
        from calibre_zen.web import serve

        dist = fake_build(os.path.join(self.mkdtemp(), 'dist'))
        p = mock.patch.object(serve, 'DIST', dist)
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

    def test_pages_assets_and_redirects(self):
        with self.server() as server:
            status, headers, body = self.get(server, '/app')
            self.assertEqual(status, 302)
            self.assertEqual(headers['location'], '/app/')

            status, headers, body = self.get(server, '/app/')
            self.assertEqual(status, 200)
            self.assertIn('text/html', headers['content-type'])
            self.assertEqual(headers['cache-control'], 'no-cache')
            self.assertNotIn(b'__zen_prefix__', body)
            self.assertIn(b'href="/app/manifest.webmanifest"', body)
            etag = headers['etag']

            status, _, _ = self.get(server, '/app/', {'If-None-Match': etag})
            self.assertEqual(status, 304)

            status, headers, _ = self.get(server, '/app/book?id=12')
            self.assertEqual(status, 302)
            self.assertEqual(headers['location'], '/app/book/?id=12')

            status, headers, body = self.get(server, '/app/book/?id=12')
            self.assertEqual(status, 200)
            self.assertEqual(body, b'<a href="/app/">home</a>')

            status, headers, body = self.get(server, '/app/_astro/a.js')
            self.assertEqual(status, 200)
            self.assertIn('text/javascript', headers['content-type'])
            self.assertIn('immutable', headers['cache-control'])
            self.assertEqual(body, b'const BASE="/app/";')

            status, headers, _ = self.get(server, '/app/manifest.webmanifest')
            self.assertIn('application/manifest+json', headers['content-type'])

            status, headers, _ = self.get(server, '/app/sw.js')
            self.assertEqual(headers['cache-control'], 'no-cache')

            status, headers, body = self.get(server, '/app/icon.png')
            self.assertEqual(headers['content-type'], 'image/png')
            self.assertIn(b'__zen_prefix__', body, 'a binary file is sent as it is')

            for path in ('/app/../secret.txt', '/app/%2E%2E/secret.txt', '/app/.hidden', '/app/nope.js'):
                self.assertEqual(self.get(server, path)[0], 404, path)

    def test_under_a_prefix(self):
        with self.server(url_prefix='/books') as server:
            status, headers, _ = self.get(server, '/books/app')
            self.assertEqual(status, 302)
            self.assertEqual(headers['location'], '/books/app/')
            status, _, body = self.get(server, '/books/app/')
            self.assertEqual(status, 200)
            self.assertIn(b'href="/books/app/manifest.webmanifest"', body)
            self.assertIn(b'src="/books/app/_astro/a.js"', body)

    def test_files_are_public_and_data_needs_the_login(self):
        "The same split as calibre's own page: the shell for anyone, the books behind the login."
        with self.server(auth=True) as server:
            self.assertEqual(self.get(server, '/app/')[0], 200)
            self.assertEqual(self.get(server, '/app/_astro/a.js')[0], 200)
            self.assertEqual(self.get(server, '/interface-data/update')[0], 401)

    def test_not_built(self):
        from calibre_zen.web import serve

        with self.server() as server, mock.patch.object(serve, 'DIST', self.mkdtemp()):
            status, _, body = self.get(server, '/app/')
            self.assertEqual(status, 503)
            self.assertIn(b'npm run build', body)


class Install(Scratch):
    def test_switched_off(self):
        from calibre.srv.tests.base import LibraryServer
        from calibre_zen.web import serve

        server = LibraryServer(self.library)
        with mock.patch.dict(os.environ, {serve.ENV_VAR: '0'}):
            self.assertFalse(serve.install(server.handler.router))
        with server:
            conn = server.connect()
            conn.request('GET', '/app/')
            self.assertEqual(conn.getresponse().status, 404)
            conn.close()

    def test_a_plugin_route_is_kept(self):
        "Something already at /app keeps it, and the server still starts."
        from calibre.srv.routes import endpoint
        from calibre.srv.tests.base import LibraryServer
        from calibre_zen.web import serve

        @endpoint('/app', auth_required=False)
        def plugin_app(ctx, rd):
            return 'plugin'

        server = LibraryServer(self.library)
        server.handler.router.add(plugin_app)
        server.handler.router.finalize()
        self.assertFalse(serve.install(server.handler.router))
        server.handler.close()

    def test_window_server_is_wrapped(self):
        "embedded.Server makes its Handler in __init__, where the wrap adds /app/."
        import inspect

        from calibre.srv import embedded
        from calibre_zen.web import serve

        upstream = getattr(embedded.Server.__init__, '__wrapped__', embedded.Server.__init__)
        self.assertIn('self.handler = Handler(', inspect.getsource(upstream))
        orig = embedded.Server.__init__
        with mock.patch.object(serve, '_wrapped', False):
            try:
                self.assertTrue(serve.install_embedded())
                self.assertIs(embedded.Server.__init__.__wrapped__, orig)
            finally:
                embedded.Server.__init__ = orig

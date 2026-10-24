#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
What the server's address opens (web/switch.py): calibre's page, still at
`/`, with the script that sends a bare visit to the new app or leaves it be,
under a prefix, behind a login, and with every other path untouched. Plus the
setting, and its box on Preferences -> Sharing over the net (web/sharing.py).

What the script does in a browser is in web/e2e/switch.spec.ts.
"""

import os
import unittest
from unittest import mock

from calibre_zen.tests.test_web import Scratch, fake_build


def calibres_page() -> bytes:
    from calibre.utils.resources import get_path as P

    with open(P('content-server/index-generated.html'), 'rb') as f:
        return f.read()


class Setting(unittest.TestCase):
    def setUp(self):
        from calibre_zen.web import switch

        self.switch = switch
        p = mock.patch.dict(os.environ)
        p.start()
        self.addCleanup(p.stop)
        os.environ.pop(switch.ENV_VAR, None)

    def test_the_default_is_the_new_app(self):
        with mock.patch.object(self.switch, 'stored', return_value=None):
            self.assertEqual(self.switch.home(), self.switch.APP)

    def test_environment_then_stored_then_default(self):
        s = self.switch
        with mock.patch.object(s, 'stored', return_value=s.CALIBRE):
            self.assertEqual(s.home(), s.CALIBRE)
            os.environ[s.ENV_VAR] = 'App'
            self.assertEqual(s.home(), s.APP)
            os.environ[s.ENV_VAR] = 'nonsense'
            with mock.patch('builtins.print'):
                self.assertEqual(s.home(), s.CALIBRE, 'a value it does not know is ignored')

    def test_stored_is_gui_json(self):
        from calibre.utils.config import JSONConfig

        s = self.switch
        prefs = JSONConfig('gui')
        prefs.set(s.PREF_KEY, s.CALIBRE)
        self.addCleanup(lambda: (prefs.pop(s.PREF_KEY, None), prefs.commit()))
        self.assertEqual(s.stored(), s.CALIBRE)
        prefs.set(s.PREF_KEY, 'other')
        self.assertIsNone(s.stored())


class Page(unittest.TestCase):
    def test_script_goes_first_in_the_head(self):
        from calibre_zen.web import switch

        page = calibres_page()
        out = switch.inject(page, switch.APP)
        head = out.index(b'<head>') + len(b'<head>')
        self.assertTrue(out[head:].lstrip().startswith(b'<script>/* calibre-zen: web/switch.py */'))
        self.assertIn(b'var home = "app"', out)
        self.assertIn(b"location.replace('app/')", out)
        self.assertEqual(out.replace(b'\n' + switch.script(switch.APP), b'', 1), page)
        self.assertIn(b'var home = "calibre"', switch.inject(page, switch.CALIBRE))

    def test_a_page_without_a_head_is_left_alone(self):
        from calibre_zen.web import switch

        self.assertEqual(switch.inject(b'<p>hi', switch.APP), b'<p>hi')


class Served(Scratch):
    "A real calibre server with /app/ and the switch added, the way the host adds them."

    def server(self, choice=None, **opts):
        from calibre.srv.tests.base import LibraryServer
        from calibre_zen.web import serve, switch

        dist = fake_build(os.path.join(self.mkdtemp(), 'dist'))
        for p in (mock.patch.object(serve, 'DIST', dist), mock.patch.object(switch, 'home', return_value=choice or switch.APP)):
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

    def assertSwitch(self, body, choice):
        self.assertIn(b'<script>/* calibre-zen: web/switch.py */', body)
        self.assertIn(f'var home = "{choice}"'.encode(), body)
        self.assertIn(b'<title>calibre</title>', body, "it is still calibre's page")

    def test_the_new_app_is_home(self):
        with self.server() as server:
            status, headers, body = self.get(server, '/')
            self.assertEqual(status, 200)
            self.assertIn('text/html', headers['content-type'])
            self.assertSwitch(body, 'app')
            status, _, _ = self.get(server, '/', {'If-None-Match': headers['etag']})
            self.assertEqual(status, 304)
            # /app/ is as it was.
            status, _, body = self.get(server, '/app/')
            self.assertEqual(status, 200)
            self.assertNotIn(b'calibre-zen: web/switch.py', body)

    def test_calibres_app_is_home(self):
        with self.server('calibre') as server:
            status, _, body = self.get(server, '/')
            self.assertEqual(status, 200)
            self.assertSwitch(body, 'calibre')

    def test_every_other_path_is_untouched(self):
        with self.server() as server:
            for path in ('/mobile', '/opds', '/ajax/library-info', '/interface-data/update', '/service_worker.js', '/manifest.json', '/robots.txt'):
                status, _, body = self.get(server, path)
                self.assertEqual(status, 200, path)
                self.assertNotIn(b'calibre-zen: web/switch.py', body, path)

    def test_under_a_prefix(self):
        with self.server(url_prefix='/books') as server:
            # calibre's own redirect to a trailing slash, which the script's
            # relative app/ needs as much as calibre's page does.
            status, headers, _ = self.get(server, '/books')
            self.assertIn(status, (301, 302))
            self.assertTrue(headers['location'].endswith('/books/'), headers['location'])
            status, _, body = self.get(server, '/books/')
            self.assertEqual(status, 200)
            self.assertSwitch(body, 'app')
            self.assertEqual(self.get(server, '/books/app/')[0], 200)

    def test_behind_a_login(self):
        "The page is public, as calibre's is, so the script runs before anything asks for the login."
        with self.server(auth=True) as server:
            status, _, body = self.get(server, '/')
            self.assertEqual(status, 200)
            self.assertSwitch(body, 'app')
            self.assertEqual(self.get(server, '/interface-data/update')[0], 401)

    def test_not_built(self):
        "With no new app to go to, the page goes out as it came."
        from calibre_zen.web import serve

        with self.server() as server, mock.patch.object(serve, 'DIST', self.mkdtemp()):
            status, _, body = self.get(server, '/')
            self.assertEqual(status, 200)
            self.assertIn(b'<title>calibre</title>', body)
            self.assertNotIn(b'calibre-zen: web/switch.py', body)

    def test_the_readers_look_is_kept(self):
        "reader_look.py wraps the same route; the script goes into its page, not instead of it."
        from calibre_zen.web import reader_look

        with self.server() as server:
            body = self.get(server, '/')[2]
            self.assertTrue(reader_look.enabled())
            self.assertSwitch(body, 'app')
            self.assertIn(reader_look.FONT_ROUTE.encode(), body)


class Install(Scratch):
    def test_wraps_once(self):
        from calibre.srv.tests.base import LibraryServer
        from calibre_zen.web import switch

        server = LibraryServer(self.library)
        router = server.handler.router
        orig = router.routes[''].endpoint.f
        self.assertIsNotNone(switch.calibres_index(orig))
        self.assertTrue(switch.install(router, switch.APP))
        wrapped = router.routes[''].endpoint.f
        self.assertIs(wrapped.__wrapped__, orig)
        self.assertIs(switch.calibres_index(wrapped), orig)
        self.assertTrue(switch.install(router, switch.CALIBRE))
        self.assertIs(router.routes[''].endpoint.f, wrapped)
        self.assertEqual(wrapped.zen_home, switch.APP)
        server.handler.close()

    def test_a_plugin_page_at_the_root_is_kept(self):
        from calibre.srv.routes import endpoint
        from calibre.srv.tests.base import LibraryServer
        from calibre_zen.web import switch

        @endpoint('', auth_required=False)
        def plugin_index(ctx, rd):
            return 'plugin'

        server = LibraryServer(self.library)
        router = server.handler.router
        del router.routes['']
        router.add(plugin_index)
        router.finalize()
        with mock.patch('builtins.print'):
            self.assertFalse(switch.install(router))
        self.assertIs(router.routes[''].endpoint.f, plugin_index.f)
        server.handler.close()

    def test_switched_off_with_the_web_app(self):
        from calibre.srv.tests.base import LibraryServer
        from calibre_zen.web import serve

        server = LibraryServer(self.library)
        with mock.patch.dict(os.environ, {serve.ENV_VAR: '0'}):
            self.assertFalse(serve.install(server.handler.router))
        self.assertFalse(hasattr(server.handler.router.routes[''].endpoint.f, 'zen_home'))
        server.handler.close()


class Sharing(unittest.TestCase):
    "The box on Preferences -> Sharing over the net."

    def setUp(self):
        from calibre.gui2 import gprefs
        from calibre_zen.tests.base import app
        from calibre_zen.web import sharing, switch

        app()
        self.switch = switch
        self.gprefs = gprefs
        before = gprefs.get(switch.PREF_KEY)
        self.addCleanup(lambda: gprefs.set(switch.PREF_KEY, before) if before else gprefs.pop(switch.PREF_KEY, None))
        gprefs.pop(switch.PREF_KEY, None)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(switch.ENV_VAR, None)
        with mock.patch.object(sharing, '_installed', False):
            from calibre.gui2.preferences import server

            cls = server.ConfigWidget
            saved = cls.genesis, cls.save_changes, cls.restore_defaults
            self.addCleanup(lambda: setattr(cls, 'genesis', saved[0]) or setattr(cls, 'save_changes', saved[1]) or setattr(cls, 'restore_defaults', saved[2]))
            self.assertTrue(sharing.install())

    def page(self):
        from calibre.gui2.preferences import server

        page = server.ConfigWidget()
        page.genesis(None)
        self.addCleanup(page.deleteLater)
        return page

    def test_box_shows_and_stores_the_choice(self):
        from calibre.gui2.preferences import server
        from calibre_zen.web import sharing

        page = self.page()
        box = page.findChild(type(page.zen_web_home), 'zenWebHome')
        self.assertIs(box, page.zen_web_home)
        self.assertTrue(box.isChecked())
        self.assertTrue(box.isEnabled())
        sharing.store(page)
        self.assertIsNone(self.gprefs.get(self.switch.PREF_KEY), 'an untouched box stores nothing')
        box.setChecked(False)
        sharing.store(page)
        self.assertEqual(self.gprefs.get(self.switch.PREF_KEY), self.switch.CALIBRE)
        page.restore_defaults()
        self.assertTrue(box.isChecked())
        self.assertIsInstance(page, server.ConfigWidget)

    def test_environment_pins_the_box(self):
        os.environ[self.switch.ENV_VAR] = 'calibre'
        page = self.page()
        box = page.zen_web_home
        self.assertFalse(box.isEnabled())
        self.assertFalse(box.isChecked())
        self.assertIn(self.switch.ENV_VAR, box.toolTip())

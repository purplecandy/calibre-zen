#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The web app's editing: /zen/api/can-edit tells it, before anything is
clicked, whether this request may change the library, and the answer matches
what calibre's own write endpoints then do.
"""

import json
import os
import shutil
import tempfile
import unittest
from base64 import b64encode

from calibre_zen.tests.base import make_library, work_dir


class CanEdit(unittest.TestCase):
    tmp = ''

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix=cls.__name__ + '-', dir=work_dir())
        cls.library = make_library(os.path.join(cls.tmp, 'library'))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def server(self, **opts):
        from calibre.srv.tests.base import LibraryServer
        from calibre_zen.web import serve

        server = LibraryServer(self.library, **opts)
        if not serve.install(server.handler.router):
            raise AssertionError('/app/ and /zen/api/ were not installed')
        return server

    def request(self, server, method, path, user=None, body=None):
        headers = {}
        if user:
            headers['Authorization'] = 'Basic ' + b64encode(f'{user}:pass-word'.encode()).decode()
        if body is not None:
            headers['Content-Type'] = 'application/json'
            body = json.dumps(body)
        conn = server.connect()
        try:
            conn.request(method, path, body=body, headers=headers)
            r = conn.getresponse()
            return r.status, r.read()
        finally:
            conn.close()

    def can_edit(self, server, user=None):
        status, body = self.request(server, 'GET', '/zen/api/can-edit?library_id=library', user)
        self.assertEqual(status, 200, body)
        d = json.loads(body)
        return d['can_edit'], d['reason']

    def set_title(self, server, user=None):
        "calibre's own answer: the status set-fields gives the same request."
        status, _ = self.request(server, 'POST', '/cdb/set-fields/1/library', user, {'changes': {'title': 'Alpha'}})
        return status

    def test_login_off_is_read_only(self):
        with self.server() as server:
            self.assertEqual(self.can_edit(server), (False, 'anonymous'))
            self.assertEqual(self.set_title(server), 403)

    def test_local_write(self):
        with self.server(local_write=True) as server:
            self.assertEqual(self.can_edit(server), (True, ''))
            self.assertEqual(self.set_title(server), 200)

    def test_users(self):
        with self.server(auth=True, auth_mode='basic') as server:
            users = server.handler.router.ctx.user_manager
            users.add_user('writer', 'pass-word')
            users.add_user('reader', 'pass-word', readonly=True)
            users.add_user('partial', 'pass-word', restriction={'library_restrictions': {'library': 'tags:fiction'}})

            self.assertEqual(self.request(server, 'GET', '/zen/api/can-edit')[0], 401, 'the answer needs the login')

            self.assertEqual(self.can_edit(server, 'writer'), (True, ''))
            self.assertEqual(self.set_title(server, 'writer'), 200)

            self.assertEqual(self.can_edit(server, 'reader'), (False, 'read-only'))
            self.assertEqual(self.set_title(server, 'reader'), 403)

            self.assertEqual(self.can_edit(server, 'partial'), (False, 'restricted'))
            self.assertEqual(self.set_title(server, 'partial'), 403)


if __name__ == '__main__':
    unittest.main()

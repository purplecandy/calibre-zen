#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
calibre's real server on a throwaway library, with /app/ added the way the
host adds it, serving the build in src/calibre_zen/web/dist. Started by
playwright.config.ts, once per project:

    calibre-debug -e web/e2e/server.py -- PORT [--prefix /books] [--user NAME:PASSWORD]

Uses calibre's own test server, so it takes no single-instance lock and runs
beside a calibre-zen that is open on this computer.
"""

import argparse
import os
import sys
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument('port', type=int)
parser.add_argument('--prefix', default='')
parser.add_argument('--user', default='')
args = parser.parse_args(sys.argv[1:])

from calibre_zen.tests.base import make_library  # noqa: E402

lib = make_library(os.path.join(tempfile.mkdtemp(prefix='zen-web-e2e-'), 'Books'))

from calibre.srv.tests.base import LibraryServer  # noqa: E402
from calibre_zen.web import serve  # noqa: E402

opts = {'port': args.port, 'listen_on': '127.0.0.1', 'url_prefix': args.prefix}
if args.user:
    opts.update(auth=True, auth_mode='basic')
server = LibraryServer(lib, **opts)
if args.user:
    name, _, password = args.user.partition(':')
    server.handler.router.ctx.user_manager.add_user(name, password)
if not serve.install(server.handler.router):
    raise SystemExit('/app/ was not installed')

with server:
    print('serving on', server.address, 'prefix', args.prefix or '(none)', flush=True)
    while True:
        time.sleep(1)

#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
calibre's real server on a throwaway library, with /app/ added the way the
host adds it, serving the build in src/calibre_zen/web/dist. Started by
playwright.config.ts, once per project:

    calibre-debug -e web/e2e/server.py -- PORT [--prefix /books] [--user NAME:PASSWORD ...] [--library DIR ...]
        [--formats] [--dist DIR] [--local-write]

With no --library, two throwaway libraries, Books and Shelf. --library serves
libraries you have instead, for `npm run dev`; give it more than once for
more than one. The server can write to them (reading positions, for one), so
give it copies.

--formats gives each throwaway book a small TXT file, for conversion and
full-text search. --dist serves a copy of the build made in DIR, so a test
can change sw.js under a running server and see the app offer the update.
--local-write lets this computer change the libraries without a login, as
calibre-server's option of that name does.

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
parser.add_argument('--user', action='append', default=[])
parser.add_argument('--library', action='append', default=[])
parser.add_argument('--formats', action='store_true')
parser.add_argument('--dist', default='')
parser.add_argument('--local-write', action='store_true')
args = parser.parse_args(sys.argv[1:])

# What each book's TXT says with --formats. Only Alpha mentions marmalade, so
# a full-text search for it finds one book.
TEXTS = {
    'Alpha': 'The keeper of the lighthouse ate marmalade on toast every morning.',
}


def add_text_formats(path: str) -> None:
    from io import BytesIO

    from calibre.db.legacy import LibraryDatabase

    db = LibraryDatabase(path)
    try:
        api = db.new_api
        for book_id in api.all_book_ids():
            title = api.field_for('title', book_id)
            text = TEXTS.get(title, f'{title} is a short book about the sea.')
            body = '\n\n'.join([f'Chapter One\n\n{text}'] * 3)
            api.add_format(book_id, 'TXT', BytesIO(body.encode('utf-8')))
    finally:
        db.close()


if args.library:
    libraries = [os.path.abspath(x) for x in args.library]
else:
    from calibre_zen.tests.base import make_library

    root = tempfile.mkdtemp(prefix='zen-web-e2e-')
    libraries = [
        make_library(os.path.join(root, 'Books')),
        make_library(os.path.join(root, 'Shelf'), books=(('Delta', ['Dee Writer'], ['poetry'], None),)),
    ]
    if args.formats:
        for library in libraries:
            add_text_formats(library)

from calibre.db.cache import Cache  # noqa: E402
from calibre.srv.tests.base import LibraryServer  # noqa: E402
from calibre_zen.web import serve  # noqa: E402

# A book is indexed for full-text search every 4 seconds, so as not to load a
# computer someone is using. A test has three books and no one to disturb.
Cache.fts_indexing_sleep_time = 0.1

if args.dist:
    import shutil

    shutil.rmtree(args.dist, ignore_errors=True)
    shutil.copytree(serve.DIST, args.dist)
    serve.DIST = args.dist

opts = {'port': args.port, 'listen_on': '127.0.0.1', 'url_prefix': args.prefix, 'local_write': args.local_write}
if args.user:
    opts.update(auth=True, auth_mode='basic')
server = LibraryServer(libraries[0], libraries=tuple(libraries), **opts)
# calibre's test server has no job runner; its reader and conversion need one.
server.handler.set_jobs_manager(server.loop.jobs_manager)
for user in args.user:
    name, _, password = user.partition(':')
    server.handler.router.ctx.user_manager.add_user(name, password)
if not serve.install(server.handler.router):
    raise SystemExit('/app/ was not installed')

with server:
    print('serving on', server.address, 'prefix', args.prefix or '(none)', flush=True)
    while True:
        time.sleep(1)

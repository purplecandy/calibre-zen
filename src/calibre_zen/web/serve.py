#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
/app/: the new web app, served by calibre's own server.

The app is a static Astro build (`web/` at the top of the repo) that lands in
`dist/` beside this file. Packaging copies all of `src/`, so it ships with
the Python and needs no Node at run time. Its data comes from calibre's own
endpoints, unchanged.

How it gets into the server: the same way /zen/status does (host/endpoints.py).
calibre's Handler loads its routes and the content-server plugins' routes and
finalizes the Router. `install` adds /app/, and /zen/api/can-edit
(access.py), with the public Router.add and finalizes again. The host calls it directly; the window's
embedded server gets it through a wrap of `embedded.Server.__init__`, which
is where that server's Handler is made.

The prefix. calibre's server can live under a path such as /books
(--url-prefix), and that is a setting, while Astro bakes its base path into
the build. So the build is made under a placeholder, SENTINEL, and every text
file is sent with the placeholder replaced by this server's prefix, which is
often nothing. Binary files carry no paths and go out as they are.

The login. Like calibre's own page, the app's files are served to anyone:
they hold no books and no names. The data they ask for needs the login, so
the browser asks for it on the first request, exactly as it does for
calibre's app. This also keeps the service worker away from 401s: it only
ever caches the public files.

Caching. Astro's `_astro/` files are named by their content, so they are
kept for a year. Everything else is revalidated on every load with its ETag,
which is what lets a new version of sw.js and the pages reach the browser.

Off with CALIBRE_ZEN_WEB=0.
"""

import mimetypes
import os

ENV_VAR = 'CALIBRE_ZEN_WEB'
APP = 'app'
SENTINEL = b'/__zen_prefix__'
DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist')

# Files whose text can carry the placeholder. Mirrors what Astro and Workbox
# write, plus the manifest.
TEXT_TYPES = {
    '.html': 'text/html; charset=UTF-8',
    '.js': 'text/javascript; charset=UTF-8',
    '.mjs': 'text/javascript; charset=UTF-8',
    '.css': 'text/css; charset=UTF-8',
    '.json': 'application/json; charset=UTF-8',
    '.webmanifest': 'application/manifest+json; charset=UTF-8',
    '.svg': 'image/svg+xml; charset=UTF-8',
    '.txt': 'text/plain; charset=UTF-8',
    '.xml': 'application/xml; charset=UTF-8',
    '.map': 'application/json; charset=UTF-8',
}
BINARY_TYPES = {
    '.png': 'image/png',
    '.ico': 'image/x-icon',
    '.woff2': 'font/woff2',
    '.woff': 'font/woff',
    '.webp': 'image/webp',
    '.jpg': 'image/jpeg',
}

IMMUTABLE = 'public, max-age=31536000, immutable'
REVALIDATE = 'no-cache'

NOT_BUILT = '''\
<!doctype html><meta charset="utf-8"><title>Not built</title>
<p>The web app has not been built. In <code>web/</code> at the top of the
repository, run <code>npm install</code> and then <code>npm run build</code>.
'''


def enabled() -> bool:
    return os.environ.get(ENV_VAR, '1') not in ('0', 'false', 'no', 'off')


def is_built(dist: str = DIST) -> bool:
    return os.path.isfile(os.path.join(dist, 'index.html'))


def server_prefix(ctx) -> str:
    "The server's --url-prefix, without a trailing slash: '' or '/books'."
    return ctx.url_for(None).rstrip('/')


def resolve(parts: str, dist: str = DIST) -> str | None:
    """
    The file in `dist` that `parts` (the path after /app/) names, or None.
    A directory means its index.html. Nothing outside `dist`, and nothing
    hidden, is ever returned.
    """
    segments = [s for s in parts.split('/') if s]
    if any(s.startswith('.') for s in segments):
        return None
    root = os.path.realpath(dist)
    path = os.path.realpath(os.path.join(root, *segments))
    if path != root and not path.startswith(root + os.sep):
        return None
    if os.path.isdir(path):
        path = os.path.join(path, 'index.html')
    return path if os.path.isfile(path) else None


def content_type(path: str) -> tuple[str, bool]:
    "(the Content-Type, whether the file is text that may carry the placeholder)"
    ext = os.path.splitext(path)[1].lower()
    if ext in TEXT_TYPES:
        return TEXT_TYPES[ext], True
    if ext in BINARY_TYPES:
        return BINARY_TYPES[ext], False
    return mimetypes.guess_type(path)[0] or 'application/octet-stream', False


def rewrite(data: bytes, prefix: str) -> bytes:
    return data.replace(SENTINEL, prefix.encode('utf-8'))


def original_path(rd) -> bytes:
    "The path as the browser sent it, before calibre dropped its trailing slash."
    uri = rd.request_original_uri or b''
    if isinstance(uri, str):
        uri = uri.encode('utf-8')
    return uri.partition(b'?')[0]


def redirect_to_directory(rd, prefix: str, parts: str):
    """
    /app and /app/book send the browser to /app/ and /app/book/. Every URL in
    the build is relative to a directory, so a page must be loaded as one.
    """
    from urllib.parse import quote

    from calibre.srv.errors import HTTPRedirect

    location = f'{prefix}/{APP}/' + ''.join(quote(s) + '/' for s in parts.split('/') if s)
    uri = rd.request_original_uri or b''
    if isinstance(uri, bytes):
        uri = uri.decode('utf-8', 'replace')
    query = uri.partition('?')[2]
    if query:
        location += '?' + query
    raise HTTPRedirect(location, http_code=302)


def respond(ctx, rd, parts: str, dist: str | None = None):
    from calibre.srv.errors import HTTPNotFound

    dist = dist or DIST
    prefix = server_prefix(ctx)
    if not is_built(dist):
        rd.outheaders.set('Cache-Control', REVALIDATE, replace_all=True)
        rd.outheaders.set('Content-Type', 'text/html; charset=UTF-8', replace_all=True)
        rd.status_code = 503
        return NOT_BUILT
    path = resolve(parts, dist)
    if path is None:
        raise HTTPNotFound(f'Not part of the web app: {parts}')
    if path.endswith(os.sep + 'index.html') and not os.path.basename(parts) == 'index.html':
        if not original_path(rd).endswith(b'/'):
            redirect_to_directory(rd, prefix, parts)

    rel = os.path.relpath(path, os.path.realpath(dist)).replace(os.sep, '/')
    rd.outheaders.set('Cache-Control', IMMUTABLE if rel.startswith('_astro/') else REVALIDATE, replace_all=True)
    ctype, is_text = content_type(path)
    if not is_text:
        rd.outheaders.set('Content-Type', ctype, replace_all=True)
        return open(path, 'rb')

    mtime = os.stat(path).st_mtime_ns

    def generate():
        with open(path, 'rb') as f:
            return rewrite(f.read(), prefix)

    # One copy per file, per build, per server: the static cache belongs to
    # the server, whose prefix never changes while it runs.
    return rd.generate_static_output(f'zen-web:{rel}:{mtime}', generate, content_type=ctype)


def make_route():
    from calibre.srv.routes import endpoint

    @endpoint('/' + APP + '/{+parts=""}', auth_required=False)
    def zen_web_app(ctx, rd, parts):
        return respond(ctx, rd, parts)

    return zen_web_app


def install(router) -> bool:
    """
    Add /app/ to a router calibre has already finalized, and finalize it
    again. False when it is switched off, or something already has /app.
    """
    if not enabled():
        return False
    from calibre_zen.web import access

    try:
        router.add(make_route())
        router.add(access.make_route())
    except Exception as e:
        # A content-server plugin got there first. Its route stays.
        print('calibre-zen: the web app is not served:', e)
        return False
    router.finalize()
    return True


_wrapped = False


def install_embedded() -> bool:
    "The window's own server, started from Connect/share, serves /app/ too."
    global _wrapped
    if _wrapped or not enabled():
        return _wrapped
    from calibre.srv import embedded

    orig = embedded.Server.__init__

    def __init__(self, *args, **kwargs):
        orig(self, *args, **kwargs)
        install(self.handler.router)

    __init__.__wrapped__ = orig
    embedded.Server.__init__ = __init__
    _wrapped = True
    return True

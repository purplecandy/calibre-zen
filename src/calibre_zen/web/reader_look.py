#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
calibre's web reader, in the desktop reader's look.

The web app's Read button opens calibre's own reader, at the server's root
(docs/plans/web/, "The reader"). That reader is the same code the desktop
viewer runs, `src/pyj/read_book/`, and reader/look/ already restyles it
there. So the page at the root gets the same two things the desktop page gets,
from outside, with nothing in src/pyj or src/calibre/srv edited:

- the icon sprite redrawn in the zen pack's line glyphs (look/icons.py), and
- the stylesheet, built from the same tokens (look/__init__.py).

How it gets in. calibre's index route ('' in the Router) sends the compiled
page as a file. `install` swaps that route's function for one that calls it,
keeps its redirect under a prefix, and sends the page with the two changes,
made once per server and per page. Same Router, same route, same login rule.

The fonts. The desktop page carries its fonts inline, because nothing serves
it. Here a server does, and inline they would add 1.6 MB to a page every
visit. So the sheet asks for them by address, under /zen/fonts/, and they are
cached. The sheet itself stays inline: calibre's service worker keeps the
page, so a book read offline keeps the look; only the font falls back.

The page at the root is calibre's whole app, not only its reader, so its
library view takes the font and the icons too. Nothing in it is hidden or
moved.

Off with CALIBRE_ZEN_READER_LOOK=0, as on the desktop, or CALIBRE_ZEN_WEB=0.
"""

import os
from urllib.parse import quote

FONT_ROUTE = 'zen/fonts'
FONT_TYPES = {'.ttf': 'font/ttf', '.otf': 'font/otf', '.woff2': 'font/woff2', '.woff': 'font/woff'}
# A font file never changes under its name while a version is installed.
FONT_CACHE = 'public, max-age=86400'


def enabled() -> bool:
    from calibre_zen import features
    from calibre_zen.web import serve

    return serve.enabled() and features.enabled('reader-look')


def font_url(directory: str, face: str) -> str:
    # Relative to the page, which calibre always serves from a directory
    # (it redirects /books to /books/), so a prefix needs nothing here.
    return f'{FONT_ROUTE}/{quote(directory)}/{quote(face)}'


def stylesheet() -> str:
    from calibre_zen.reader import look

    m = look.mapping()
    # A late font is better than no text while it arrives over the network.
    m['font_faces'] = look.font_faces(font_url).replace('font-display: block', 'font-display: swap')
    return look.stylesheet(m)


def page(html: bytes) -> bytes:
    """
    calibre's page with zen's icons and stylesheet. Cosmetic: whatever fails
    leaves that part of the page as calibre made it.
    """
    from calibre_zen.reader.look import icons, inject

    try:
        html = icons.rewrite(html)
    except Exception:
        import traceback

        traceback.print_exc()
    try:
        html = inject(html, stylesheet())
    except Exception:
        import traceback

        traceback.print_exc()
    return html


def wrap_index(router) -> bool:
    "Swap the root route's function for one that sends the page in zen's look."
    from dataclasses import replace

    route = router.routes.get('')
    if route is None or getattr(route.endpoint.f, 'zen_reader_look', False):
        return False
    orig = route.endpoint.f

    def index(ctx, rd):
        # calibre's own first: under a prefix it redirects to the directory.
        out = orig(ctx, rd)
        path = getattr(out, 'name', None)
        if not isinstance(path, str):
            return out
        out.close()

        def generate():
            with open(path, 'rb') as f:
                return page(f.read())

        key = f'zen-reader-look:{path}:{os.stat(path).st_mtime_ns}'
        return rd.generate_static_output(key, generate, content_type='text/html; charset=UTF-8')

    index.zen_reader_look = True
    index.__wrapped__ = orig
    index.__name__ = orig.__name__
    route.endpoint = replace(route.endpoint, f=index)
    return True


def resolve_font(parts: str) -> str | None:
    "The font file `parts` names under the vendored fonts, or None."
    from calibre_zen.theme import generate

    segments = [s for s in parts.split('/') if s]
    if not segments or any(s.startswith('.') for s in segments):
        return None
    if os.path.splitext(segments[-1])[1].lower() not in FONT_TYPES:
        return None
    root = os.path.realpath(generate.FONTS_DIR)
    path = os.path.realpath(os.path.join(root, *segments))
    if not path.startswith(root + os.sep) or not os.path.isfile(path):
        return None
    return path


def make_font_route():
    from calibre.srv.routes import endpoint

    @endpoint('/' + FONT_ROUTE + '/{+parts=""}', auth_required=False)
    def zen_fonts(ctx, rd, parts):
        from calibre.srv.errors import HTTPNotFound

        path = resolve_font(parts)
        if path is None:
            raise HTTPNotFound(f'No such font: {parts}')
        rd.outheaders.set('Content-Type', FONT_TYPES[os.path.splitext(path)[1].lower()], replace_all=True)
        rd.outheaders.set('Cache-Control', FONT_CACHE, replace_all=True)
        return open(path, 'rb')

    return zen_fonts


def install(router) -> bool:
    """
    The root page in zen's look, and the fonts it asks for. Leaves the router
    for the caller to finalize. False when switched off or already done.
    """
    if not enabled():
        return False
    try:
        router.add(make_font_route())
    except Exception as e:
        print('calibre-zen: the reader look is not served:', e)
        return False
    return wrap_index(router)

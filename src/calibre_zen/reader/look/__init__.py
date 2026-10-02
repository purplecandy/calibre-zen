#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The reader's web UI, in the overlay's look.

Almost everything inside the reader window -- the page, the main menu,
Preferences, Go to, the selection bar -- is one web page, `viewer.html`,
served to a QWebEngineView by `calibre.gui2.viewer.web_view`. Qt's stylesheet
does not reach it, and neither does the font Qt registered, so it gets a
stylesheet of its own, built from the same tokens as the Qt one.

One wrap, from outside, no upstream file edited:

`web_view.viewer_html`
    The module-level function the page's URL handler calls by name for every
    load. Wrapped to return upstream's page with one `<style id="zen-reader-
    look">` inserted before `</head>`, built once per process.

`web_view.create_profile`
    Where calibre adds its own `viewer.js` to the web engine's profile. The
    scripts in js/ are added beside it, in the same JavaScript world -- the
    *application* world, not the page's: calibre's code runs there, and only
    from there can a script reach `window.python_comm`, which is how the
    header and footer sheets (sheets.py, js/30-sheets.js) turn pages and open
    calibre's panels by calibre's own means.

Only the reader process does this. `install()` runs in every calibre process
and `calibre.gui2.viewer.main` is imported only by the ones that are a reader
-- the viewer's launcher and the spare in warm.py both import it before the
Application exists -- so the main window never loads the web engine for this.

The stylesheet is every file in css/, in filename order, rendered the way the
Qt sheets are (string.Template, `$name`, a bad placeholder costs one file):

    00-variables.css   the API: every `--zen-*` custom property, light and
                       dark, plus the `--calibre-color-*` overrides, plus the
                       font. Read its comments before using one.
    01-base.css        global things only: font, scrollbars, selection, focus.
    20-... and up      one file per part of the reader. A file that only uses
                       the `--zen-*` variables is plain CSS and needs nothing
                       from here; a new file is picked up with no code change.

Dark and light follow the *reading* colour scheme, not the Qt palette: the web
UI puts `color-scheme: dark|light` on `<html>` as the reader picks a scheme.
So both sets of values are written out, and the variables file switches
between them on `:root[style*="color-scheme: dark"]`.

The page adds its own `<style>` elements after ours, at runtime. A rule of
equal specificity that comes from the page therefore wins over one of ours:
write selectors that are more specific than upstream's, or use `!important`.

Off with `CALIBRE_ZEN_READER_LOOK=0`, or Reader look in the overlay's menu.
"""

import base64
import os
import re
import sys
from functools import cache
from string import Template

from qt.core import QColor, QPalette

from calibre_zen import features
from calibre_zen.theme import generate
from calibre_zen.theme.tokens import components, primitives, semantic

HERE = os.path.dirname(os.path.abspath(__file__))
CSS_DIR = os.path.join(HERE, 'css')
STYLE_ID = 'zen-reader-look'
# A reader process has imported this before it makes its Application; no other
# calibre process does. See the module docstring.
VIEWER_MODULE = 'calibre.gui2.viewer.main'
WEB_VIEW_MODULE = 'calibre.gui2.viewer.web_view'

# The family the page is told to use. Private on purpose: a reader may have a
# real "Inter" installed, in another version, and this must be the one we
# shipped.
FONT_NAME = 'Zen UI'
FONT_FALLBACK = 'system-ui, sans-serif'

# Web-only sizes: the Qt sheet has no token for a panel title or a section
# label, because Qt has no such element. The base and caption sizes are the
# sheet's own.
TITLE_SIZE = 16
LABEL_SIZE = 11
LINE_HEIGHT = 1.4
# Motion, in ms. 120-180 is where a transition reads as responsive and not as
# an animation; the menu opening is the slow one.
DURATION_FAST = 120
DURATION = 150
DURATION_SLOW = 180
EASE = 'cubic-bezier(0.16, 1, 0.3, 1)'
BLUR = 12  # px, behind the menu card

# A shadow is made of nothing but darkness, so it is the one colour here that
# is not read off a palette.
SHADOW_INK = '0 0 0'


# The variables {{{


def _rgba(color: QColor, alpha: float) -> str:
    return f'rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})'


_QT_RGBA = re.compile(r'^rgba\((\d+), (\d+), (\d+), (\d+)\)$')


def _css_alpha(value: str) -> str:
    """
    `Chrome` writes alpha the way QSS reads it, 0-255; CSS reads 0-1 and clamps
    anything above it, so `rgba(.., 33)` would be a solid fill. Convert.
    """
    m = _QT_RGBA.match(value)
    if m is None:
        return value
    r, g, b, a = m.groups()
    return f'rgba({r}, {g}, {b}, {round(int(a) / 255, 3)})'


def _mode_mapping(pal: QPalette, is_dark: bool) -> dict:
    "Every colour a mode needs, as {name: css colour}."
    chrome = semantic.Chrome(pal, is_dark)
    m = {k: _css_alpha(v) if isinstance(v, str) else v for k, v in chrome.as_mapping().items()}
    fg = pal.color(QPalette.ColorRole.WindowText)
    accent = pal.color(QPalette.ColorRole.Highlight)
    m.update(
        fg=fg.name(),
        page=pal.color(QPalette.ColorRole.Base).name(),
        link=pal.color(QPalette.ColorRole.Link).name(),
        # Selected text in the page's chrome: the accent, let through, so the
        # text on it keeps its own colour at either end of the lightness range.
        selection=_rgba(accent, 0.25 if is_dark else 0.22),
        ring=chrome.accent,
        ring_glow=_rgba(accent, 0.2),
        # The lit upper edge a floating surface gets in dark, in place of a
        # heavier shadow.
        edge=_rgba(fg, 0.07),
        # A hint of the text colour over whatever is behind: the three
        # `--calibre-color-surface-*` steps, which were the cream tint.
        tint_1=_rgba(fg, 0.04),
        tint_2=_rgba(fg, 0.025),
        tint_3=_rgba(fg, 0.015),
    )
    return m


@cache
def _face_data(directory: str, name: str) -> str:
    with open(os.path.join(generate.FONTS_DIR, directory, name), 'rb') as f:
        return base64.b64encode(f.read()).decode('ascii')


def _weight_of(face: str) -> int:
    "The weight a vendored file is, from its name: Inter-SemiBold.ttf is 600."
    stem = os.path.splitext(face)[0].lower()
    for word, weight in (('semibold', 600), ('medium', 500), ('bold', 700)):
        if stem.endswith(word):
            return weight
    return 400


def font_faces() -> str:
    """
    The @font-face rules for the UI family, with the files inline as data: URLs.

    The web engine cannot see a font Qt registered, and there is no URL to
    serve one from, so the page carries its own. Weights are read off the file
    names; a family with a semibold does not also load its bold, since the
    browser picks the heavier face at or above what is asked for and 600 is
    what the sheet means by bold.
    """
    font = primitives.active_font()
    weights = {face: _weight_of(face) for face in font['faces']}
    if 600 in weights.values():
        weights = {face: w for face, w in weights.items() if w <= 600}
    rules = []
    for face, weight in sorted(weights.items(), key=lambda kv: kv[1]):
        try:
            data = _face_data(font['dir'], face)
        except OSError:
            continue  # a face that is missing costs that weight, not the page
        rules.append(
            f'@font-face {{ font-family: "{FONT_NAME}"; font-weight: {weight}; font-style: normal; font-display: block; '
            f'src: url("data:font/ttf;base64,{data}") format("truetype"); }}'
        )
    return '\n'.join(rules)


def mapping(light_pal: QPalette | None = None, dark_pal: QPalette | None = None) -> dict:
    """
    What a template may substitute.

    `light_<name>` and `dark_<name>` for every colour, so one file can write a
    mode's block each; the radii and sizes unprefixed, as in the Qt sheets.
    The palettes are the active scheme's own (`generate.light_palette()` and
    `dark_palette()`), the dark one at the depth Dim says -- a custom palette
    from Preferences is not read, because the reader's two modes are not the
    Qt window's one.
    """
    # The radii belong to the active scheme and are plain module attributes.
    components.refresh()
    m = components.as_mapping()
    for prefix, pal, is_dark in (
        ('light', light_pal or generate.light_palette(), False),
        ('dark', dark_pal or generate.dark_palette(), True),
    ):
        for key, value in _mode_mapping(pal, is_dark).items():
            m[f'{prefix}_{key}'] = value
    m.update(
        font_name=FONT_NAME,
        font_fallback=FONT_FALLBACK,
        font_faces=font_faces(),
        font_size_base=primitives.FONT_SIZE['base'],
        font_size_caption=primitives.FONT_SIZE['sm'],
        font_size_title=TITLE_SIZE,
        font_size_label=LABEL_SIZE,
        line_height=LINE_HEIGHT,
        weight_regular=primitives.FONT_WEIGHT['regular'],
        weight_medium=primitives.FONT_WEIGHT['medium'],
        weight_semibold=primitives.FONT_WEIGHT['semibold'],
        duration_fast=DURATION_FAST,
        duration=DURATION,
        duration_slow=DURATION_SLOW,
        ease=EASE,
        blur=BLUR,
        shadow_ink=SHADOW_INK,
    )
    return m


# }}}

# The stylesheet {{{


def templates() -> tuple:
    "Every file in css/, in filename order. The numeric prefixes are that order."
    return tuple(sorted(n for n in os.listdir(CSS_DIR) if n.endswith('.css')))


def render(name: str, m: dict) -> str:
    "One file, substituted. A bad placeholder costs this file its placeholder, not the page its sheet."
    with open(os.path.join(CSS_DIR, name), encoding='utf-8') as f:
        t = Template(f.read())
    try:
        return t.substitute(m)
    except (KeyError, ValueError) as err:
        # Plain CSS may legitimately hold a `$` -- [href$=".pdf"] -- which is a
        # ValueError here and is left as it is by safe_substitute.
        from calibre.constants import DEBUG

        if DEBUG:
            print(f'calibre-zen: reader look {name}: bad placeholder: {err}', file=sys.stderr)
        return t.safe_substitute(m)


def stylesheet(m: dict | None = None) -> str:
    "The whole sheet: every file, rendered, in order."
    if m is None:
        m = mapping()
    return '\n'.join(render(name, m) for name in templates())


# }}}

# Injection {{{

_HEAD_END = re.compile(rb'</head\s*>', re.IGNORECASE)


def style_element(css: str) -> bytes:
    return f'<style id="{STYLE_ID}">\n{css}\n</style>'.encode()


JS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'js')


def scripts() -> str:
    """
    Every `js/*.js`, in filename order, as one script for the application
    world (see `web_view.create_profile` above). Behaviour the look needs and
    CSS cannot do. Each file is its own IIFE, so one that throws costs only
    itself.
    """
    try:
        names = sorted(n for n in os.listdir(JS_DIR) if n.endswith('.js'))
    except OSError:
        return ''
    parts = []
    for name in names:
        with open(os.path.join(JS_DIR, name), encoding='utf-8') as f:
            parts.append(f'/* {name} */\n' + f.read())
    return '\n'.join(parts)


def inject(html: bytes, css: str | None = None) -> bytes:
    "`html` with our style before `</head>`, or in front of everything when it has no head."
    tag = style_element(stylesheet() if css is None else css)
    match = _HEAD_END.search(html)
    if match is None:
        return tag + html
    return html[: match.start()] + tag + html[match.start() :]


def wrap(module) -> bool:
    "Replace `module.viewer_html` with one that returns the page with our style in it, once per process."
    orig = getattr(module, 'viewer_html', None)
    if orig is None or getattr(orig, 'zen_reader_look', False):
        return False
    cached = []

    def viewer_html() -> bytes:
        if not cached:
            page = orig()
            try:
                from calibre_zen.reader.look import icons

                page = icons.rewrite(page)
            except Exception:
                import traceback

                traceback.print_exc()
            try:
                page = inject(page)
            except Exception:
                # Cosmetic. The reader without its look is the reader.
                import traceback

                traceback.print_exc()
            cached.append(page)
        return cached[0]

    viewer_html.zen_reader_look = True
    viewer_html.__wrapped__ = orig
    module.viewer_html = viewer_html
    return True


def enabled() -> bool:
    return features.enabled('reader-look')


def is_reader_process() -> bool:
    return VIEWER_MODULE in sys.modules


def install() -> bool:
    if not enabled() or not is_reader_process():
        return False
    import importlib

    # Already imported by the viewer's own `main`; this only fetches it.
    web_view = importlib.import_module(WEB_VIEW_MODULE)
    wrap(web_view)
    try:
        from calibre_zen.reader.look import sheets

        sheets.install(web_view, importlib.import_module('calibre.gui2.viewer.ui'), scripts)
    except Exception:
        import traceback

        traceback.print_exc()
    try:
        from calibre_zen.reader.look import qt

        qt.install()
    except Exception:
        import traceback

        traceback.print_exc()
    return True


# }}}

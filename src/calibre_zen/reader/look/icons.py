#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The reader page's icon sprite, redrawn in the zen pack's line glyphs.

The reader's web UI draws every icon as `<svg><use href="#icon-NAME"/></svg>`
against one inline sprite, `<svg style="display:none">` holding a `<symbol
id="icon-NAME">` for each file in `imgsrc/srv/` -- ninety solid Font-Awesome
style glyphs. `rewrite(html)` swaps the body of each mapped symbol for the
Tabler outline glyph the main window uses, in place and under the same id, so
nothing that references the sprite has to know.

Why it works with no help from the page: calibre's `svgicon()` puts
`fill: currentColor` on the outer `<svg>`, and a fill is inherited down through
`<use>`. A presentation attribute on the `<symbol>` itself beats an inherited
value, so a mapped symbol carries `fill="none" stroke="currentColor"` and draws
as a line, while an unmapped one has none and goes on being filled. Both take
their colour from `currentColor`, which is the text colour of whatever holds
them.

An unmapped name is left exactly as calibre drew it, which is what the main
window's pack does too. The ones left on purpose:

    selection-handle, selection-handle-vertical
        The grips at the ends of a text selection. They are solid teardrops
        whose fill and outline are set from script (`set_handle_color`) to
        match the book's colours; a line version would lose the shape.

The page is the only input. Anything that goes wrong -- a page with no sprite,
a glyph that is not on disk, a symbol that does not parse -- leaves that symbol,
or the whole page, as it was: this runs in front of every reader window and is
cosmetic.
"""

import os
import re
from functools import cache

from calibre_zen.icons.pack import ASSETS

# calibre's name for the icon -> the Tabler glyph. Where the main window's pack
# (icons/packs/tabler.py) already drew the same idea, this is its choice.
MAP = {
    'ai': 'sparkles',
    'angle-down': 'chevron-down',
    'arrow-left': 'arrow-left',
    'arrow-right': 'arrow-right',
    'arrows-h': 'arrows-horizontal',
    'auto-scroll': 'chevrons-down',
    # The rich-text editor's colour pickers: a paint pot for the background, a
    # letter A for the text colour (the pack's 'text-color').
    'bg': 'bucket-droplet',
    'fg': 'text-color',
    'bold': 'bold',
    'book': 'book-2',
    'bookmark': 'bookmark',
    'bug': 'bug',
    # Read aloud, which is the only thing the reader uses it for.
    'bullhorn': 'volume',
    # The small solid triangles of a tree or a nav row. A chevron is what the
    # rest of the UI draws for the same thing.
    'caret-down': 'chevron-down',
    'caret-left': 'chevron-left',
    'caret-right': 'chevron-right',
    'check': 'check',
    'chevron-down': 'chevron-down',
    'chevron-left': 'chevron-left',
    'chevron-right': 'chevron-right',
    'chevron-up': 'chevron-up',
    'close': 'x',
    'cloud-download': 'cloud-download',
    'cog': 'settings',
    'cogs': 'adjustments-horizontal',
    'convert': 'transform',
    'copy': 'copy',
    'date': 'calendar',
    'edit': 'edit',
    'ellipsis-v': 'dots-vertical',
    'eraser': 'eraser',
    'external-link': 'external-link',
    # Read aloud speed: the hare and the tortoise, as a runner and a walker.
    'faster': 'run',
    'fit-to-screen': 'arrows-maximize',
    'fts': 'file-search',
    'full-screen': 'maximize',
    'global-search': 'world-search',
    'heading': 'heading',
    'heart': 'heart',
    'help': 'help-circle',
    'highlight': 'highlight',
    'home': 'home',
    'hourglass': 'hourglass',
    'hr': 'separator-horizontal',
    'image': 'photo',
    'indent': 'indent-increase',
    'insert-link': 'link-plus',
    'italic': 'italic',
    'justify-center': 'align-center',
    'justify-full': 'align-justified',
    'justify-left': 'align-left',
    'justify-right': 'align-right',
    'library': 'books',
    'link': 'link',
    'off': 'power',
    'ol': 'list-numbers',
    'outdent': 'indent-decrease',
    'pause': 'player-pause',
    'pencil': 'pencil',
    'play': 'player-play',
    'plus': 'plus',
    'print': 'printer',
    'random': 'arrows-shuffle',
    'redo': 'arrow-forward-up',
    'reference-mode': 'hand-finger',
    'refresh': 'refresh',
    'remove': 'x',
    'search': 'search',
    'select-all': 'select-all',
    'send': 'send',
    'slower': 'walk',
    'sort-amount-asc': 'sort-ascending',
    'sort-amount-desc': 'sort-descending',
    # Tabler's half star is the left half drawn as an outline, which is how a
    # run of stars ending in one reads in a line set.
    'star': 'star',
    'star-half': 'star-half',
    'strikethrough': 'strikethrough',
    'subscript': 'subscript',
    'superscript': 'superscript',
    'tags': 'tags',
    'toc': 'list-tree',
    'trash': 'trash',
    'ul': 'list',
    'underline': 'underline',
    'undo': 'arrow-back-up',
    'user': 'user',
    'warning': 'alert-triangle',
    'window-restore': 'minimize',
}

# Never rewritten, and why: see the module docstring.
UNMAPPED = ('selection-handle', 'selection-handle-vertical')

GLYPH_DIR = os.path.join(ASSETS, 'tabler')

# One symbol, id and all. The sprite is machine-written by
# imgsrc/srv/generate.py, so a symbol never nests another and never carries a
# '>' inside an attribute.
_SYMBOL = re.compile(rb'<symbol\b(?P<attrs>[^>]*)>(?P<body>.*?)</symbol\s*>', re.S)
_ID = re.compile(rb'''\bid\s*=\s*(?:"icon-([^"]+)"|'icon-([^']+)')''')
_SVG_BODY = re.compile(r'<svg\b[^>]*>(?P<body>.*)</svg\s*>', re.S)
# Tabler starts each glyph with an invisible 24x24 box so that a stroke has a
# frame in tools that crop to ink. Nothing here needs it.
_FRAME = re.compile(r'<path\b[^>]*\bstroke="none"[^>]*/>\s*')


def stroke_width() -> float:
    "The weight of the main window's icons, so a glyph is one weight everywhere."
    from calibre_zen.theme.tokens import components

    return components.ICON_STROKE


@cache
def glyph_body(name: str) -> str:
    "The drawing elements of one vendored Tabler glyph, or '' when it is not usable."
    try:
        with open(os.path.join(GLYPH_DIR, f'{name}.svg'), encoding='utf-8') as f:
            svg = f.read()
    except OSError:
        return ''
    m = _SVG_BODY.search(svg)
    if m is None:
        return ''
    return _FRAME.sub('', m.group('body')).strip()


def symbol(name: str, body: str, stroke: float) -> bytes:
    """
    One `<symbol>` in the sprite's shape: a line glyph, in the text colour.

    The weight is written twice. The attribute is the main window's own and
    stands when nothing else is loaded. The style wins over it and reads
    `--zen-icon-stroke`, which css/41-icons.css sets by the size an icon is
    drawn at: a line scaled down from the 24px box it was drawn for goes
    thin, so a small icon is given a heavier stroke to look the same weight.
    """
    return (
        f'<symbol id="icon-{name}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" '
        f'style="stroke-width: var(--zen-icon-stroke, {stroke})">{body}</symbol>'
    ).encode()


def wanted() -> bool:
    "Line icons are the active pack's choice: off, or another pack, and the sprite stays calibre's."
    try:
        from calibre_zen.icons import registry

        pack = registry.active()
        return pack is not None and pack.name == 'tabler'
    except Exception:
        # No way to ask; the default is the line icons.
        return True


def _replace(stroke: float):
    def sub(m: re.Match) -> bytes:
        try:
            idm = _ID.search(m.group('attrs'))
            if idm is None:
                return m.group()
            name = (idm.group(1) or idm.group(2)).decode('ascii')
            glyph = MAP.get(name)
            body = glyph_body(glyph) if glyph else ''
            if not body:
                return m.group()
            return symbol(name, body, stroke)
        except Exception:
            return m.group()

    return sub


def rewrite(html: bytes) -> bytes:
    "The reader page with its icon sprite redrawn. Returns `html` untouched on any trouble."
    try:
        if not isinstance(html, bytes | bytearray) or b'<symbol' not in html or not wanted():
            return html
        return _SYMBOL.sub(_replace(stroke_width()), bytes(html))
    except Exception:
        return html

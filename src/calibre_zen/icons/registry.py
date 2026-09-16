#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Which icon pack is in use, and the one place calibre is taught about it.

Every icon in calibre arrives through `QIcon.ic(name)`, which is
`IconResourceManager.__call__`. Wrapping that one method is the whole
integration: a name the active pack covers is rendered from SVG in the palette's
colour, and a name it does not falls straight through to calibre's own icon. A
pack therefore never has to be complete, and turning packs off restores stock
calibre exactly.

Icons are cached per (pack, name) -- the colour is not part of the key because
an icon resolves it when it paints -- and their rendered pixmaps are dropped
when the palette changes,
because the colour is baked into the rendered pixmaps.
"""

import os

from qt.core import QIcon, QPalette

from calibre_zen.icons import packs

_cache: dict = {}
# Distinct from None, which is a real answer here: it means the user asked for
# calibre's own icons and no pack should be consulted.
_UNRESOLVED = object()
_active = _UNRESOLVED
_installed = False


def enabled() -> bool:
    return os.environ.get('CALIBRE_ZEN_ICONS', '1') not in ('0', 'false', 'no', 'off')


def requested() -> str:
    "The pack the environment asks for. 'tabler' unless told otherwise."
    val = os.environ.get('CALIBRE_ZEN_ICONS', '')
    return val if val and enabled() and val not in ('1', 'true', 'yes', 'on') else 'tabler'


def available() -> dict:
    return packs.discover()


def active():
    global _active
    if not enabled():
        return None
    if _active is _UNRESOLVED:
        _active = available().get(requested())
    return _active


def use(name: str) -> bool:
    """
    Swap packs. `name` may be a pack name or '' for calibre's own icons.

    Clears the caches and re-themes, which is enough for everything that asks
    for its icon when it paints. Widgets that took a QIcon once at construction
    keep the old one until they are rebuilt -- a restart swaps everything.
    """
    global _active
    if name and name not in available():
        return False
    _active = available().get(name) if name else None
    clear()
    from calibre.gui2 import qapplication_or_fail

    app = qapplication_or_fail()
    QIcon.ic.set_theme()  # type: ignore
    app.palette_changed.emit()
    return True


def clear() -> None:
    _cache.clear()
    from calibre.gui2 import icon_resource_manager

    icon_resource_manager.icon_cache = {}


def color_for(role: str) -> str:
    """
    Resolve a pack's role against the live palette.

    `success` is the exception: the palette has no green, deliberately, so it
    comes from the tokens instead. A status mark is the one place where red and
    green carry the meaning and consistency must not flatten them.
    """
    from calibre.gui2 import qapplication_or_fail
    from calibre_zen.theme.tokens import schemes

    app = qapplication_or_fail()
    if role == 'success':
        return schemes.active().success[0 if app.property('is_dark_theme') else 1]
    r = {
        'text': QPalette.ColorRole.WindowText,
        'accent': QPalette.ColorRole.Highlight,
        # What sits *on* the accent: the colour a highlighted menu item's label
        # flips to, and therefore what its glyph has to flip to as well.
        'on-accent': QPalette.ColorRole.HighlightedText,
        'danger': QPalette.ColorRole.BrightText,
    }.get(role, QPalette.ColorRole.WindowText)
    return app.palette().color(r).name()


def icon(name: str):
    "The pack's icon for a calibre icon name, or None to let calibre answer."
    pack = active()
    if pack is None:
        return None
    svg, role = pack.svg(name)
    if svg is None:
        return None
    # No colour in the key: the icon resolves its own on every paint, so one
    # QIcon serves both themes and the copy a QAction took at startup is still
    # right after the reader switches.
    key = (pack.name, name)
    ans = _cache.get(key)
    if ans is None:
        from calibre_zen.icons import render
        from calibre_zen.theme.tokens import components

        ans = _cache[key] = render.live_icon(svg, role, components.ICON_STROKE)
    return ans


def glyph_icon(glyph: str, role: str = 'text'):
    """
    An icon for a glyph named directly, rather than for a calibre icon name.

    For the places where the overlay needs an icon calibre never had one for --
    the Preferences menu's category submenus, which upstream draws with five
    copies of the same gear.
    """
    pack = active()
    if pack is None:
        return None
    svg = pack.glyph_svg(glyph)
    if not svg:
        return None
    key = ('glyph', pack.name, glyph)
    ans = _cache.get(key)
    if ans is None:
        from calibre_zen.icons import render
        from calibre_zen.theme.tokens import components

        ans = _cache[key] = render.live_icon(svg, role, components.ICON_STROKE)
    return ans


def install() -> bool:
    global _installed
    if _installed or not enabled():
        return _installed
    from calibre.gui2 import IconResourceManager

    orig_call = IconResourceManager.__call__
    orig_set_theme = IconResourceManager.set_theme

    def __call__(self, name, fallback=b''):
        if isinstance(name, str) and name and not os.path.isabs(name):
            ans = icon(name)
            if ans is not None:
                return ans
        return orig_call(self, name, fallback)

    def set_theme(self):
        # The palette changed. The QIcons themselves survive it -- they ask the
        # palette for a colour when they paint -- but the pixmaps rendered in
        # the old one do not.
        from calibre_zen.icons import render

        render.clear_pixmaps()
        return orig_set_theme(self)

    IconResourceManager.__call__ = __call__
    IconResourceManager.set_theme = set_theme
    _installed = True
    return True

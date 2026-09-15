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

Icons are cached per (pack, name, colour) and dropped when the palette changes,
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
    from calibre.gui2 import qapplication_or_fail

    pal = qapplication_or_fail().palette()
    r = {
        'text': QPalette.ColorRole.WindowText,
        'accent': QPalette.ColorRole.Highlight,
        'danger': QPalette.ColorRole.BrightText,
    }.get(role, QPalette.ColorRole.WindowText)
    return pal.color(r).name()


def icon(name: str):
    "The pack's icon for a calibre icon name, or None to let calibre answer."
    pack = active()
    if pack is None:
        return None
    svg, role = pack.svg(name)
    if svg is None:
        return None
    color = color_for(role)
    key = (pack.name, name, color)
    ans = _cache.get(key)
    if ans is None:
        from calibre.gui2 import qapplication_or_fail
        from calibre_zen.icons import render
        from calibre_zen.theme.tokens import components

        ans = _cache[key] = render.icon(svg, color, components.ICON_STROKE, qapplication_or_fail().devicePixelRatio())
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
        # The palette changed, so every rendered colour is stale.
        _cache.clear()
        return orig_set_theme(self)

    IconResourceManager.__call__ = __call__
    IconResourceManager.set_theme = set_theme
    _installed = True
    return True

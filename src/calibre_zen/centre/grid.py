#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
How big a cover-grid tile is.

calibre computes one tile size from `gprefs['cover_grid_height']` and
`['cover_grid_width']` -- both default to 0, meaning "a fifth of the screen's
height, three-quarters as wide" (`alternate_views.py:77, 662-672`). On a tall
display that is a very large tile, and there is no setting between it and
typing centimetres into Preferences.

This adds three densities on top. It is a **multiplier**, not a size, which is
the same shape as `TOOLBAR_ICON_SIZE` re-scaling calibre's five icon settings:
whatever the reader has chosen in Preferences -> Cover grid still decides the
base, and the density only changes the scale underneath it. `default` is 1.0
and must stay 1.0 -- it is the promise that this can be turned off.

`CoverDelegate.set_dimensions` is wrapped rather than reimplemented: the
original runs in full and its answer is scaled afterwards. That matters because
the tile is not just the cover -- there is a title strip whose height comes
from the font, and an emblem gutter whose size and position come from four more
preferences. Scaling the cover and re-deriving the rest from the original's own
numbers keeps all of that working without this file knowing the emblem rules.

Two things deliberately do not scale. The **title strip** is text, and text that
is 44% of its proper size is not a smaller label, it is an unreadable one. An
explicitly configured **spacing** is a number the reader typed; only the
automatic spacing, which is itself derived from the tile width, follows.
"""

from qt.core import QSize

from calibre.gui2 import gprefs
from calibre_zen.theme.tokens import components

PREF_KEY = 'zen_grid_density'
ENV_VAR = 'CALIBRE_ZEN_GRID'

_installed = False


def levels() -> tuple:
    "The density names, roomiest first."
    return tuple(components.GRID_DENSITY)


def label_for(name: str) -> str:
    return {'default': _('Default'), 'compact': _('Compact'), 'tiny': _('Tiny')}.get(name, name)


def density() -> str:
    """
    The density in force: the environment if it names one, else the stored
    choice, else the shipped default.
    """
    import os

    chosen = os.environ.get(ENV_VAR) or gprefs.get(PREF_KEY) or components.GRID_DENSITY_DEFAULT
    return chosen if chosen in components.GRID_DENSITY else components.GRID_DENSITY_DEFAULT


def factor() -> float:
    return components.GRID_DENSITY.get(density(), 1.0)


def set_density(name: str, gui=None) -> None:
    "Store the choice and, if the grid exists, re-lay it out now."
    if name not in components.GRID_DENSITY:
        return
    gprefs.set(PREF_KEY, name)
    view = None if gui is None else getattr(gui, 'grid_view', None)
    if view is None:
        return
    view.delegate.set_dimensions()
    view.setSpacing(view.delegate.spacing)
    view.update_memory_cover_cache_size()
    # setSpacing already asks for a relayout, but the item size changed too and
    # a QListView caches that per item until it is told otherwise.
    view.scheduleDelayedItemsLayout()


def install() -> bool:
    global _installed
    if _installed:
        return True
    from calibre.gui2.library.alternate_views import CoverDelegate

    orig_set_dimensions = CoverDelegate.set_dimensions

    def set_dimensions(self):
        ans = orig_set_dimensions(self)
        scale = factor()
        if scale == 1.0:
            return ans
        try:
            margin = self.MARGIN
            cover = self.cover_size
            # Whatever the original added beyond cover + margins + title is the
            # emblem gutter. Carried over rather than recomputed, so the four
            # emblem preferences keep meaning what they mean.
            plain = cover + QSize(2 * margin, (2 * margin) + self.title_height)
            extra = self.item_size - plain

            self.cover_size = QSize(max(24, int(cover.width() * scale)), max(36, int(cover.height() * scale)))
            self.item_size = self.cover_size + QSize(2 * margin, (2 * margin) + self.title_height) + extra

            if gprefs['cover_grid_spacing'] < 0.01:
                self.spacing = max(6, min(50, int(0.1 * self.cover_size.width())))

            dpr = self.parent().device_pixel_ratio
            self.cover_cache.set_thumbnail_size(int(dpr * self.cover_size.width()), int(dpr * self.cover_size.height()))
        except Exception:
            # A tile at the wrong size is a smaller problem than a grid that
            # will not paint, so keep whatever the original worked out.
            import traceback

            traceback.print_exc()
        return ans

    try:
        CoverDelegate.set_dimensions = set_dimensions
    except AttributeError, TypeError:
        return False
    _installed = True
    return True

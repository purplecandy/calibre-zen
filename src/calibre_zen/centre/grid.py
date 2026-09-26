#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
How big a cover-grid tile is, and what shape the cover in it is.

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

import os

from qt.core import QSize, Qt

from calibre.gui2 import gprefs
from calibre_zen.theme.tokens import components

PREF_KEY = 'zen_grid_density'
ENV_VAR = 'CALIBRE_ZEN_GRID'
CROP_VAR = 'CALIBRE_ZEN_GRID_CROP'

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
    forget_filled()  # the cropped copies were cut to the old tile
    # setSpacing already asks for a relayout, but the item size changed too and
    # a QListView caches that per item until it is told otherwise.
    view.scheduleDelayedItemsLayout()


# One shape for every tile {{{

# calibre scales a cover to *fit* the tile's cover box and centres it, so a
# 2:3 cover fills the height, a squarer one fills the width and stops short,
# and a shelf of them has a ragged edge where the tiles do not. The book table
# already crops its row thumbnails to fill (`table.py`), so this is the grid
# catching up rather than a new idea.
#
# Done to the pixmap rather than to the painting, which is what makes it cheap:
# a thumbnail that already fills the box leaves calibre's own centring offsets
# at zero, so the cover, the ring around it and the emblem's right offset all
# line up without any of them being told about it.
#
# Filling means trimming, so the cost was measured rather than waved at. Over a
# real shelf, against calibre's default tile (three quarters as wide as it is
# tall), the median cover loses 6% of one dimension and the worst 13%. It also
# settled a wrong instinct: covers cluster nearer 4:5 than 2:3, so re-shaping
# the tile to 2:3 -- which sounds like the shape of a book -- would have made
# the median trim 16%, not smaller. Whatever tile the reader has configured is
# the right one to fill.
#
# Some readers would rather see every cover whole, and they have a point: a
# crop is an edit to someone's cover art. So the shape is a choice, in the view
# switcher's menu beside the tile size -- `uniform` (the default, cropped to
# the tile) or `natural` (calibre's own fit). A natural cover is also seated
# on the bottom of its box instead of floating in the middle of it (`seat`),
# so a shelf of mixed shapes shares a baseline the way books on a shelf do,
# and the hover bar hangs on the cover's own foot.
#
# CALIBRE_ZEN_GRID_CROP=0 pins `natural` and =1 pins `uniform`, as before;
# the menu entry is disabled while the environment has the last word.

_filled: dict = {}
FILL_CACHE = 600  # cropped pixmaps held at once; a screenful is a fraction of this


def forget_filled() -> None:
    _filled.clear()


def fill(pixmap, width: int, height: int):
    """
    `pixmap` scaled to cover `width` x `height`, taken from the middle.

    Keyed on the pixmap's own cache key, so a cover is cropped once rather than
    on every repaint of every visible tile, and a re-rendered thumbnail gets a
    new key by itself.

    The crop is central because a book cover's title is usually at the top and
    its author at the foot, and trimming from one end would reliably cut one of
    them. Covers that are nowhere near the tile's shape are upscaled to fill,
    which costs a little sharpness -- the alternative is the ragged shelf.
    """
    if pixmap is None or pixmap.isNull():
        return pixmap
    if pixmap.width() == width and pixmap.height() == height:
        return pixmap
    key = (pixmap.cacheKey(), width, height)
    ans = _filled.get(key)
    if ans is None:
        if len(_filled) > FILL_CACHE:
            _filled.clear()
        scaled = pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - width) // 2)
        y = max(0, (scaled.height() - height) // 2)
        ans = _filled[key] = scaled.copy(x, y, width, height)
    return ans


SHAPE_KEY = 'zen_grid_covers'
SHAPES = ('uniform', 'natural')


def shape_label(name: str) -> str:
    return {'uniform': _('Uniform'), 'natural': _('Natural')}.get(name, name)


def shape_note(name: str) -> str:
    return {'uniform': _('Every cover cut to the same shape'), 'natural': _('Every cover whole, in its own shape')}.get(name, '')


def shape_pinned() -> bool:
    "Whether CALIBRE_ZEN_GRID_CROP decides, so the menu cannot."
    return bool(os.environ.get(CROP_VAR))


def cover_shape() -> str:
    "The shape in force: the environment, then the stored choice, then uniform."
    env = os.environ.get(CROP_VAR)
    if env:
        return 'natural' if env.lower() in ('0', 'false', 'no', 'off') else 'uniform'
    chosen = gprefs.get(SHAPE_KEY)
    return chosen if chosen in SHAPES else SHAPES[0]


def cropping() -> bool:
    return cover_shape() == 'uniform'


def set_cover_shape(name: str, gui=None) -> None:
    "Store the choice and repaint the grid with it. Nothing is re-rendered."
    if name not in SHAPES or shape_pinned():
        return
    gprefs.set(SHAPE_KEY, name)
    forget_filled()
    view = None if gui is None else getattr(gui, 'grid_view', None)
    if view is not None:
        view.viewport().update()


def seat(delegate, rect) -> None:
    """
    Move a cover that is shorter than its box down onto the box's floor.

    calibre centres a cover in its box both ways. `rect` is that centred
    cover, and it is the very QRect the delegate goes on to use for emblems
    and a flush-bottom title, so it is moved in place and they follow it. The
    box is `cover_size` tall -- the tile less its margins, title and emblem
    gutter, which is exactly how `set_dimensions` builds it. A cropped cover
    fills the box and is not moved.
    """
    box = getattr(delegate, 'cover_size', None)
    if box is None:
        return
    dy = (box.height() - rect.height()) // 2
    if dy > 0:
        rect.translate(0, dy)


def attach(gui) -> bool:
    """
    Make one grid's thumbnails the shape of its tiles. Safe to call twice.

    The cache instance is wrapped rather than the class: the book table keeps
    its own `CoverThumbnailCache`, and it is already cropping for itself. The
    shape is asked on every call, so the menu can change it in a running grid.
    """
    view = getattr(gui, 'grid_view', None)
    delegate = None if view is None else getattr(view, 'delegate', None)
    cache = None if delegate is None else getattr(delegate, 'cover_cache', None)
    if cache is None or getattr(cache, 'zen_uniform', False):
        return False
    orig = cache.thumbnail_as_pixmap

    def thumbnail_as_pixmap(book_id):
        pixmap = orig(book_id)
        if pixmap is None:
            return None  # still rendering; never block a paint on it
        if not cropping():
            return pixmap
        width, height = cache.thumbnail_size
        return fill(pixmap, width, height)

    cache.thumbnail_as_pixmap = thumbnail_as_pixmap
    cache.zen_uniform = True
    return True


# }}}


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

#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
One monochrome SVG plus one colour in, one QIcon out.

The icon sets worth using are line icons drawn in `currentColor`, which is a CSS
idea Qt's SVG renderer does not have. Substituting the colour into the source
before handing it to Qt is what makes an icon set follow the palette instead of
shipping two hand-coloured copies of every glyph.

The colour is resolved when the icon is *painted*, not when it is built, which
is what lets the palette change under a running window. A `QIcon` built from
pixmaps is a photograph: an icon a QAction grabbed while the theme was light
stays light-inked forever, and on a dark background that is an invisible
toolbar. `LiveIcon` is a `QIconEngine` instead, so every paint asks the palette
what colour it is now -- measured, not assumed: before this, a held icon stayed
(31, 35, 40) against a #24262a window.

An engine also has to answer `availableSizes()`, because calibre tests icons
with `QIcon.is_ok()`, which is `not isNull() and len(availableSizes()) > 0`
(`gui2/__init__.py:309`). An SVG-backed QIcon reports none and would fail that
test; this reports the list below.
"""

import re

from qt.core import QEvent, QIcon, QIconEngine, QImage, QMenu, QObject, QPainter, QPixmap, QSize, Qt

# Every size calibre asks a toolbar, menu, list or status bar for. Rendering the
# set once per icon costs a few hundred microseconds and means Qt never scales
# a line icon, which is where they go soft.
SIZES = (16, 20, 24, 32, 48, 64)


STROKE_WIDTH = re.compile(r'stroke-width="[^"]*"')


def restyle(svg: str, color: str, stroke: float) -> str:
    """
    Substitute the colour and the stroke weight into the source.

    The weight is a property of the UI, not of the glyph: a line icon drawn for
    a 24px box is a marker pen at 18px, and every icon has to be re-weighted
    together or the toolbar stops looking like one set.
    """
    svg = svg.replace('currentColor', color)
    return STROKE_WIDTH.sub(f'stroke-width="{stroke}"', svg)


def render(svg: str, size: int, dpr: float) -> QPixmap:
    from PyQt6.QtSvg import QSvgRenderer

    px = max(1, round(size * dpr))
    img = QImage(px, px, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:
        QSvgRenderer(svg.encode('utf-8')).render(p)
    finally:
        p.end()
    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(dpr)
    return pm


def icon(svg: str, color: str, stroke: float, dpr: float = 1.0) -> QIcon:
    ans = QIcon()
    styled = restyle(svg, color, stroke)
    for size in SIZES:
        ans.addPixmap(render(styled, size, dpr))
    return ans


# Rendered pixmaps, keyed by everything that changes one. Bounded by the number
# of glyphs times the sizes above times the number of palettes a session sees.
_pixmaps: dict = {}


def clear_pixmaps() -> None:
    _pixmaps.clear()


# The modes Qt asks for when a glyph is being drawn on the selection fill,
# measured rather than assumed: a highlighted menu item comes through as
# Active, a selected row in an item view as Selected, and -- against
# expectation -- a pressed tool button is plain Normal. Both of those fills are
# the accent, and the label next to the glyph flips to HighlightedText, so the
# glyph has to as well or it is drawn in the window's ink on the accent: in the
# light theme that is #0a0a0a on #171717, which is not a dim icon, it is no
# icon at all.
#
# Active is not only the menu's, though. QCommonStyle asks for Active for a
# *hovered* auto-raise tool button too -- every button on the toolbar and the
# status bar -- and there the fill is a translucent wash, not the accent, so
# a glyph that flipped went near-invisible on hover. The two cannot be told
# apart by mode, so they are told apart by moment: MenuPaintWatch marks the
# span of a QMenu's paint event, and Active means on-accent only inside it.
ON_ACCENT_MODES = (QIcon.Mode.Selected,)
_painting_menu = False


def on_accent(mode) -> bool:
    "Whether this mode, right now, means the glyph is on the accent fill."
    return mode in ON_ACCENT_MODES or (mode == QIcon.Mode.Active and _painting_menu)


class MenuPaintWatch(QObject):
    """
    Marks the span of a QMenu's paint.

    An application-wide filter sees every event before it is delivered, and
    delivery is synchronous: the next event of any kind filtered anywhere in
    the application arrives after the menu has finished painting. So the flag
    goes up on a QMenu's Paint and comes down on whatever event follows.
    Kept to two comparisons, because it runs for everything.
    """

    def eventFilter(self, obj, ev):  # noqa: N802  (matching the Qt name is the point)
        global _painting_menu
        if _painting_menu:
            _painting_menu = False
        if ev.type() == QEvent.Type.Paint and isinstance(obj, QMenu):
            _painting_menu = True
        return False


_watch = None


def install() -> bool:
    "Install the menu-paint watch. Call once, with a QApplication alive."
    global _watch
    if _watch is not None:
        return True
    from calibre.gui2 import qapplication_or_fail

    app = qapplication_or_fail()
    _watch = MenuPaintWatch(app)
    app.installEventFilter(_watch)
    return True


class LiveIcon(QIconEngine):
    """
    One glyph, re-inked from the palette on every paint.

    Holds the SVG source and a palette *role* rather than a colour, so the
    same engine serves a light and a dark theme and an icon handed to a
    QAction at startup is still the right colour after the reader switches.

    The role is what the glyph means; the *mode* Qt asks for decides which
    colour that role resolves to, because a glyph on the selection fill has to
    flip along with the label beside it.
    """

    def __init__(self, svg: str, role: str, stroke: float):
        super().__init__()
        self.svg = svg
        self.role = role
        self.stroke = stroke

    def color(self, mode=QIcon.Mode.Normal) -> str:
        from calibre_zen.icons import registry

        return registry.color_for('on-accent' if on_accent(mode) else self.role)

    def pixmap(self, size, mode=QIcon.Mode.Normal, state=QIcon.State.Off) -> QPixmap:
        from calibre.gui2 import qapplication_or_fail

        dpr = qapplication_or_fail().devicePixelRatio()
        px = max(1, min(size.width(), size.height()))
        color = self.color(mode)
        key = (self.svg, color, self.stroke, px, dpr, mode)
        ans = _pixmaps.get(key)
        if ans is None:
            ans = render(restyle(self.svg, color, self.stroke), px, dpr)
            if mode == QIcon.Mode.Disabled:
                # Qt generates a disabled variant for a pixmap-backed QIcon;
                # an engine has to say what disabled looks like itself.
                faded = QPixmap(ans.size())
                faded.setDevicePixelRatio(ans.devicePixelRatio())
                faded.fill(Qt.GlobalColor.transparent)
                painter = QPainter(faded)
                painter.setOpacity(0.4)
                painter.drawPixmap(0, 0, ans)
                painter.end()
                ans = faded
            _pixmaps[key] = ans
        return ans

    def paint(self, painter, rect, mode, state) -> None:
        painter.drawPixmap(rect, self.pixmap(rect.size(), mode, state))

    def availableSizes(self, mode=QIcon.Mode.Normal, state=QIcon.State.Off) -> list:  # noqa: N802  (matching the Qt name is the point)
        return [QSize(s, s) for s in SIZES]

    def clone(self) -> LiveIcon:
        return LiveIcon(self.svg, self.role, self.stroke)


def live_icon(svg: str, role: str, stroke: float) -> QIcon:
    "A QIcon that follows the palette instead of freezing the colour it was built in."
    return QIcon(LiveIcon(svg, role, stroke))

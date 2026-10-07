#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The tray's icon: Tabler's `books` glyph, drawn from its SVG at every size a
menubar or tray asks for.

On macOS it is drawn black and marked as a mask, which Qt hands to AppKit as
a template image: the menubar recolours it for light, dark and a selected
item, as it does every other status item. Elsewhere it is drawn in the
palette's text colour.

The state shows in the icon too, in a way that survives being a template:

    sharing             the glyph
    starting, paused    the glyph, faded
    stopped             the glyph, with a dot in the corner
"""

import os

GLYPH = 'books'
SIZES = (16, 18, 22, 24, 32)
FADED_OPACITY = 0.45


def glyph_path(glyph: str = GLYPH) -> str:
    from calibre_zen.icons.pack import ASSETS

    return os.path.join(ASSETS, 'tabler', f'{glyph}.svg')


def glyph_svg(color: str, glyph: str = GLYPH) -> bytes:
    with open(glyph_path(glyph), encoding='utf-8') as f:
        return f.read().replace('currentColor', color).encode('utf-8')


def render(svg: bytes, size: int, dpr: float = 1.0, faded: bool = False, dot: bool = False, color: str = '#000'):
    from qt.core import QByteArray, QColor, QPainter, QPixmap, QRectF, QSvgRenderer, Qt

    px = max(1, round(size * dpr))
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(svg))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if faded:
        p.setOpacity(FADED_OPACITY)
    renderer.render(p, QRectF(0, 0, px, px))
    if dot:
        p.setOpacity(1)
        r = px * 0.36
        p.setPen(Qt.PenStyle.NoPen)
        # Knock a ring out of the glyph first, so the dot reads as a dot and
        # not as a smudge on the books' spines.
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        p.setBrush(QColor(0, 0, 0))
        p.drawEllipse(QRectF(px - r - px * 0.06, px - r - px * 0.06, r + px * 0.06, r + px * 0.06))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.setBrush(QColor(color))
        p.drawEllipse(QRectF(px - r, px - r, r, r))
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def make_icon(color: str, mask: bool, faded: bool = False, dot: bool = False):
    from qt.core import QIcon

    svg = glyph_svg(color)
    icon = QIcon()
    for size in SIZES:
        for dpr in (1.0, 2.0):
            icon.addPixmap(render(svg, size, dpr, faded=faded, dot=dot, color=color))
    if mask:
        icon.setIsMask(True)
    return icon


class Icons:
    "One icon per look, made once. `mask` on macOS, where the menubar colours it."

    def __init__(self, color: str, mask: bool):
        self.color, self.mask = color, mask
        self._cache = {}

    def get(self, faded: bool = False, dot: bool = False):
        key = (faded, dot)
        if key not in self._cache:
            self._cache[key] = make_icon(self.color, self.mask, faded=faded, dot=dot)
        return self._cache[key]

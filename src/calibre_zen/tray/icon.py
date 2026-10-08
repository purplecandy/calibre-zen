#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The tray's icon: calibre-zen's own mark, drawn at every size a menubar or tray
asks for.

The app icon is a dark square with three pale waves across it. A menubar icon
has one colour, so the mark here is that square in one colour with the waves
cut out of it, each wave as far as its own opacity in the app icon (a little
stronger, so the three still read apart at 16 px). The waves come from
`waves.svg`, which is `imgsrc/calibre.svg` without its square: a package ships
`src/` but not `imgsrc/`.

On macOS it is drawn black and marked as a mask, which Qt hands to AppKit as
a template image: the menubar recolours it for light, dark and a selected
item, as it does every other status item. Elsewhere it is drawn in the
palette's text colour.

The state shows in the icon too, in a way that survives being a template:

    sharing             the mark
    starting, paused    the mark, faded
    stopped             the mark, with a dot in the corner
"""

import os
import re

SIZES = (16, 18, 22, 24, 32)
FADED_OPACITY = 0.45
# How much stronger the waves are cut than the app icon draws them.
WAVE_BOOST = 1.6
INSET = 0.08  # of the side, left clear around the square
RADIUS = 0.24  # of the square's side, close to the Dock's rounded square


def waves_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'waves.svg')


def waves_svg() -> bytes:
    with open(waves_path(), encoding='utf-8') as f:
        svg = f.read()
    return re.sub(r'opacity="([\d.]+)"', lambda m: f'opacity="{min(1.0, float(m.group(1)) * WAVE_BOOST):.2f}"', svg).encode('utf-8')


def draw_mark(p, px: int, color: str, waves: bytes):
    "The rounded square in `color`, with the waves cut out of it."
    from qt.core import QByteArray, QColor, QImage, QPainter, QPainterPath, QRectF, QSvgRenderer

    layer = QImage(px, px, QImage.Format.Format_ARGB32_Premultiplied)
    layer.fill(0)
    q = QPainter(layer)
    q.setRenderHint(QPainter.RenderHint.Antialiasing)
    inset = px * INSET
    box = QRectF(inset, inset, px - 2 * inset, px - 2 * inset)
    outline = QPainterPath()
    outline.addRoundedRect(box, box.width() * RADIUS, box.width() * RADIUS)
    q.fillPath(outline, QColor(color))
    q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
    QSvgRenderer(QByteArray(waves)).render(q, QRectF(0, 0, px, px))
    q.end()
    p.drawImage(0, 0, layer)


def render(waves: bytes, size: int, dpr: float = 1.0, faded: bool = False, dot: bool = False, color: str = '#000'):
    from qt.core import QColor, QPainter, QPixmap, QRectF, Qt

    px = max(1, round(size * dpr))
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if faded:
        p.setOpacity(FADED_OPACITY)
    draw_mark(p, px, color, waves)
    if dot:
        p.setOpacity(1)
        r = px * 0.36
        p.setPen(Qt.PenStyle.NoPen)
        # Knock a ring out of the mark first, so the dot reads as a dot and
        # not as a smudge on the mark.
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

    waves = waves_svg()
    icon = QIcon()
    for size in SIZES:
        for dpr in (1.0, 2.0):
            icon.addPixmap(render(waves, size, dpr, faded=faded, dot=dot, color=color))
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

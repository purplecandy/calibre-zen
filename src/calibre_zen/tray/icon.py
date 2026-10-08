#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The tray's icon: calibre-zen's own mark, drawn at every size a menubar or tray
asks for.

The app icon is a dark square with three pale waves across it. A menubar icon
has one colour, so the mark here is that square in one colour with the waves
cut out of it, each wave as far as its own opacity in the app icon (a little
stronger, so they still read at 16 px). `CALIBRE_ZEN_TRAY_ICON` picks the shape:

    square    the app icon's shape (the default)
    circle    the same waves, cut out of a circle
    books     Tabler's `books` glyph, as before

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
SHAPES = ('square', 'circle', 'books')
SIZES = (16, 18, 22, 24, 32)
FADED_OPACITY = 0.45
# How much stronger the waves are cut than the app icon draws them, so the
# three bands stay apart at menubar size.
WAVE_BOOST = 1.6
INSET = 0.08  # of the side, around the shape, as status items leave
RADIUS = 0.24  # of the shape's side, close to the Dock's squircle


def shape() -> str:
    value = os.environ.get('CALIBRE_ZEN_TRAY_ICON', '').strip().lower()
    return value if value in SHAPES else 'square'


def waves_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'waves.svg')


def waves_svg() -> bytes:
    import re

    with open(waves_path(), encoding='utf-8') as f:
        svg = f.read()
    return re.sub(r'opacity="([\d.]+)"', lambda m: f'opacity="{min(1.0, float(m.group(1)) * WAVE_BOOST):.2f}"', svg).encode('utf-8')


def glyph_path(glyph: str = GLYPH) -> str:
    from calibre_zen.icons.pack import ASSETS

    return os.path.join(ASSETS, 'tabler', f'{glyph}.svg')


def glyph_svg(color: str, glyph: str = GLYPH) -> bytes:
    with open(glyph_path(glyph), encoding='utf-8') as f:
        return f.read().replace('currentColor', color).encode('utf-8')


def draw_mark(p, px: int, color: str, form: str, waves: bytes):
    "The shape in `color`, with the waves cut out of it."
    from qt.core import QByteArray, QColor, QImage, QPainter, QPainterPath, QRectF, QSvgRenderer

    layer = QImage(px, px, QImage.Format.Format_ARGB32_Premultiplied)
    layer.fill(0)
    q = QPainter(layer)
    q.setRenderHint(QPainter.RenderHint.Antialiasing)
    inset = px * INSET
    box = QRectF(inset, inset, px - 2 * inset, px - 2 * inset)
    outline = QPainterPath()
    if form == 'circle':
        outline.addEllipse(box)
    else:
        outline.addRoundedRect(box, box.width() * RADIUS, box.width() * RADIUS)
    q.fillPath(outline, QColor(color))
    q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
    QSvgRenderer(QByteArray(waves)).render(q, QRectF(0, 0, px, px))
    q.end()
    p.drawImage(0, 0, layer)


def render(svg: bytes, size: int, dpr: float = 1.0, faded: bool = False, dot: bool = False, color: str = '#000', form: str = 'books'):
    from qt.core import QByteArray, QColor, QPainter, QPixmap, QRectF, QSvgRenderer, Qt

    px = max(1, round(size * dpr))
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if faded:
        p.setOpacity(FADED_OPACITY)
    if form == 'books':
        QSvgRenderer(QByteArray(svg)).render(p, QRectF(0, 0, px, px))
    else:
        draw_mark(p, px, color, form, svg)
    if dot:
        p.setOpacity(1)
        r = px * 0.36
        p.setPen(Qt.PenStyle.NoPen)
        # Knock a ring out of the glyph first, so the dot reads as a dot and
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


def make_icon(color: str, mask: bool, faded: bool = False, dot: bool = False, form: str | None = None):
    from qt.core import QIcon

    form = form or shape()
    svg = glyph_svg(color) if form == 'books' else waves_svg()
    icon = QIcon()
    for size in SIZES:
        for dpr in (1.0, 2.0):
            icon.addPixmap(render(svg, size, dpr, faded=faded, dot=dot, color=color, form=form))
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

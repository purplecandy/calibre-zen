#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
One monochrome SVG plus one colour in, one QIcon out.

The icon sets worth using are line icons drawn in `currentColor`, which is a CSS
idea Qt's SVG renderer does not have. Substituting the colour into the source
before handing it to Qt is what makes an icon set follow the palette instead of
shipping two hand-coloured copies of every glyph.

QIcon must be built from real pixmaps rather than from the SVG path: calibre
tests icons with `QIcon.is_ok()`, which requires availableSizes() to be
non-empty, and an SVG-backed QIcon reports none.
"""

from qt.core import QIcon, QImage, QPainter, QPixmap, Qt

# Every size calibre asks a toolbar, menu, list or status bar for. Rendering the
# set once per icon costs a few hundred microseconds and means Qt never scales
# a line icon, which is where they go soft.
SIZES = (16, 20, 24, 32, 48, 64)


def colorize(svg: str, color: str) -> str:
    return svg.replace('currentColor', color)


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


def icon(svg: str, color: str, dpr: float = 1.0) -> QIcon:
    ans = QIcon()
    colored = colorize(svg, color)
    for size in SIZES:
        ans.addPixmap(render(colored, size, dpr))
    return ans

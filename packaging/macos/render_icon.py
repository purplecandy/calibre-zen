#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Render imgsrc/calibre.svg into a macOS .iconset.

`imgsrc/generate.py` would normally do the SVG rasterising, but it wants
rsvg-convert, zopflipng and inkscape. Qt is already here -- it is what the
application is built on -- so the icon is rendered with the same renderer that
draws every other glyph in the overlay.

Run with the bundle's own interpreter:

    calibre-debug -e packaging/macos/render_icon.py -- <svg> <out.iconset>
"""

import os
import sys

from qt.core import QGuiApplication, QImage, QPainter, Qt

# The sizes Apple's iconutil expects, as (points, scale). A .icns missing one
# of these is accepted but then macOS picks the nearest and rescales it, which
# is where an icon goes soft in the Dock.
SIZES = ((16, 1), (16, 2), (32, 1), (32, 2), (128, 1), (128, 2), (256, 1), (256, 2), (512, 1), (512, 2))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    svg_path, out_dir = args[-2], args[-1]
    QGuiApplication([])
    from PyQt6.QtSvg import QSvgRenderer

    with open(svg_path, 'rb') as f:
        data = f.read()
    os.makedirs(out_dir, exist_ok=True)
    for points, scale in SIZES:
        px = points * scale
        img = QImage(px, px, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        QSvgRenderer(data).render(painter)
        painter.end()
        suffix = '' if scale == 1 else f'@{scale}x'
        name = f'icon_{points}x{points}{suffix}.png'
        if not img.save(os.path.join(out_dir, name)):
            raise SystemExit(f'Failed to write {name}')
        print(f'  {px:>4}px  {name}')


main()

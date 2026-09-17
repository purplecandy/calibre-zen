#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Render imgsrc/calibre.svg into the images the Windows package needs: the MSIX
logo set, and a multi-size .ico for calibre-zen.exe.

Same idea as packaging/macos/render_icon.py: Qt is the renderer the application
is built on, so the icon is drawn by the same code as every glyph in the
overlay, and the bundle's own Pillow assembles the .ico.

Run with the bundle's own interpreter:

    calibre-debug -e packaging/windows/render_assets.py -- <svg> <out dir>
"""

import os
import sys

from qt.core import QGuiApplication, QImage, QPainter, QRectF, Qt

# MSIX visual assets: name -> (width, height). The icon is drawn square,
# centred, at the shorter side, so the wide tile gets a centred glyph on a
# transparent field rather than a stretched one.
MSIX = {
    'Square44x44Logo.png': (44, 44),
    'Square71x71Logo.png': (71, 71),
    'Square150x150Logo.png': (150, 150),
    'Square310x310Logo.png': (310, 310),
    'Wide310x150Logo.png': (310, 150),
    'StoreLogo.png': (50, 50),
}
# Taskbar and Start use these exact sizes of the 44x44 logo when present;
# without them Windows scales the 44 and the result goes soft.
TARGET_SIZES = (16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def render(renderer, w, h):
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    side = min(w, h)
    renderer.render(p, QRectF((w - side) / 2, (h - side) / 2, side, side))
    p.end()
    return img


def save(img, path):
    if not img.save(path):
        raise SystemExit(f'Failed to write {path}')
    print(f'  {img.width():>4}x{img.height():<4} {os.path.basename(path)}')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    svg_path, out_dir = args[-2], args[-1]
    QGuiApplication([])
    from PyQt6.QtSvg import QSvgRenderer

    with open(svg_path, 'rb') as f:
        renderer = QSvgRenderer(f.read())
    assets = os.path.join(out_dir, 'Assets')
    os.makedirs(assets, exist_ok=True)

    for name, (w, h) in MSIX.items():
        save(render(renderer, w, h), os.path.join(assets, name))
    for px in TARGET_SIZES:
        img = render(renderer, px, px)
        save(img, os.path.join(assets, f'Square44x44Logo.targetsize-{px}.png'))
        save(img, os.path.join(assets, f'Square44x44Logo.targetsize-{px}_altform-unplated.png'))

    # The .ico: every size rendered by Qt, not one size resampled by Pillow.
    from PIL import Image

    frames = []
    for px in ICO_SIZES:
        path = os.path.join(out_dir, f'ico-{px}.png')
        save(render(renderer, px, px), path)
        frames.append(Image.open(path))
    ico = os.path.join(out_dir, 'calibre-zen.ico')
    frames[-1].save(ico, format='ICO', sizes=[(px, px) for px in ICO_SIZES], append_images=frames[:-1])
    for px in ICO_SIZES:
        os.remove(os.path.join(out_dir, f'ico-{px}.png'))
    print(f'  {len(ICO_SIZES)} sizes  calibre-zen.ico')


main()

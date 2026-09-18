#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Render imgsrc/calibre.svg into a macOS .iconset, in the shape macOS expects.

`imgsrc/generate.py` would normally do the SVG rasterising, but it wants
rsvg-convert, zopflipng and inkscape. Qt is already here -- it is what the
application is built on -- so the icon is rendered with the same renderer that
draws every other glyph in the overlay.

The artwork is a full-bleed opaque square. Since Big Sur an app icon is a
rounded square that does not fill its canvas: on Apple's 1024-point template
the shape is 824 points wide, centred, with 100 points of margin on each side
and corners of radius 185.4, plus a soft shadow beneath. macOS does not apply
that shape for you; an icon that ignores it sits in Launchpad and the Dock as
a hard square among rounded ones. So the artwork is clipped to that shape,
and the shadow drawn, here -- by Qt for the SVG and the bundle's Pillow for
the compositing, since Qt's blur effect crashes under the offscreen platform.

Run with the bundle's own interpreter:

    calibre-debug -e packaging/macos/render_icon.py -- <svg> <out.iconset>
"""

import io
import os
import sys

from qt.core import QGuiApplication, QImage, QPainter, Qt

# The sizes Apple's iconutil expects, as (points, scale). A .icns missing one
# of these is accepted but then macOS picks the nearest and rescales it, which
# is where an icon goes soft in the Dock.
SIZES = ((16, 1), (16, 2), (32, 1), (32, 2), (128, 1), (128, 2), (256, 1), (256, 2), (512, 1), (512, 2))

# Apple's icon template, as fractions of the canvas.
SHAPE = 824 / 1024  # the rounded square's side
RADIUS = 185.4 / 824  # its corner radius, relative to that side
SHADOW_OFFSET = 12 / 1024  # downwards
SHADOW_BLUR = 14 / 1024  # gaussian radius
SHADOW_ALPHA = 0.30


def artwork(renderer, side):
    """The SVG rendered square at `side` px, as a Pillow image."""
    img = QImage(side, side, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(p)
    p.end()
    from qt.core import QBuffer, QIODevice

    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, 'PNG')
    from PIL import Image

    return Image.open(io.BytesIO(bytes(buf.data()))).convert('RGBA')


def render(renderer, px):
    from PIL import Image, ImageDraw, ImageFilter

    # Work at 4x for anything small, so the corners and the shadow stay smooth
    # after the final downscale.
    scale = 4 if px < 256 else 1
    big = px * scale
    side = round(big * SHAPE)
    off = (big - side) // 2
    radius = side * RADIUS

    mask = Image.new('L', (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle((off, off, off + side - 1, off + side - 1), radius=radius, fill=255)

    canvas = Image.new('RGBA', (big, big), (0, 0, 0, 0))
    # The shadow: the shape, black at low alpha, blurred, nudged down.
    shadow_alpha = mask.point(lambda v: int(v * SHADOW_ALPHA))
    shadow = Image.new('RGBA', (big, big), (0, 0, 0, 0))
    shadow.putalpha(shadow_alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(big * SHADOW_BLUR))
    canvas.alpha_composite(shadow, (0, round(big * SHADOW_OFFSET)))
    # The artwork, clipped to the shape.
    art = artwork(renderer, side)
    clipped = Image.new('RGBA', (big, big), (0, 0, 0, 0))
    clipped.paste(art, (off, off))
    clipped.putalpha(Image.composite(clipped.getchannel('A'), Image.new('L', (big, big), 0), mask))
    canvas.alpha_composite(clipped)
    if scale != 1:
        canvas = canvas.resize((px, px), Image.Resampling.LANCZOS)
    return canvas


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    svg_path, out_dir = args[-2], args[-1]
    QGuiApplication([])
    from PyQt6.QtSvg import QSvgRenderer

    with open(svg_path, 'rb') as f:
        renderer = QSvgRenderer(f.read())
    os.makedirs(out_dir, exist_ok=True)
    for points, scale in SIZES:
        px = points * scale
        img = render(renderer, px)
        suffix = '' if scale == 1 else f'@{scale}x'
        name = f'icon_{points}x{points}{suffix}.png'
        img.save(os.path.join(out_dir, name), 'PNG')
        print(f'  {px:>4}px  {name}')


main()

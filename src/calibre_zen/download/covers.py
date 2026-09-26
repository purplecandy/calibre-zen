#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The covers, as a grid of tiles.

calibre's `CoversView` is a `QListView` in icon mode with a 190x260 grid, and
its `CoverDelegate` paints the default item -- a selection block and two lines
of centred text -- and then the cover over the top, or a spinner while a
source is still looking. The view, the model and the delegate all stay: the
model still owns the covers and their order, the view its context menu, Enter
and double-click, and the delegate its spinner animation, which the view
repaints through. Only the delegate's `paint` and `sizeHint` are replaced
(class-level, in `install()`), and the view gets a grid sized from the tokens.

A tile is a 2:3 box with the cover fitted into it, sitting on its bottom edge
so a row of covers of different shapes reads as a shelf, and two lines under
it: where the cover came from and its size in pixels, which is what the
model's display text already holds. The first tile is the book's current
cover and says "Keep current cover". A selected tile gets a ring round the
cover, the same mark the cover grid uses.
"""

from qt.core import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QRect, QRectF, QSize, QStyle, Qt

from calibre_zen.download.chrome import colors, draw_spinner
from calibre_zen.theme.tokens import components, primitives


def tile_size() -> QSize:
    pad = components.DOWNLOAD_TILE_PAD
    return QSize(components.DOWNLOAD_COVER_W + 2 * pad, components.DOWNLOAD_COVER_H + 2 * pad + components.DOWNLOAD_TILE_TEXT)


def split_text(text: str) -> tuple:
    "The model's two lines: the source, and either 'WxH' or 'Searching...'."
    first, _sep, second = (text or '').partition('\n')
    w, x, h = second.partition('x')
    if x and w.isdigit() and h.isdigit():
        second = f'{w} × {h}'
    return first, second


def fitted(pmap: QPixmap, box: QRect) -> QRect:
    "Where a cover lands in its box: fitted whole, centred across, on the box's bottom edge."
    if pmap.isNull():
        return QRect(box)
    dpr = pmap.devicePixelRatio() or 1
    w, h = pmap.width() / dpr, pmap.height() / dpr
    if w <= 0 or h <= 0:
        return QRect(box)
    scale = min(box.width() / w, box.height() / h)
    sw, sh = max(1, round(w * scale)), max(1, round(h * scale))
    return QRect(box.left() + (box.width() - sw) // 2, box.bottom() - sh + 1, sw, sh)


def size_hint(self, option, index):
    return tile_size()


def paint(self, painter, option, index):
    chrome = colors()
    selected = bool(option.state & QStyle.StateFlag.State_Selected)
    hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
    waiting = self.animator.is_running() and bool(index.data(Qt.ItemDataRole.UserRole))
    source, detail = split_text(str(index.data(Qt.ItemDataRole.DisplayRole) or ''))
    keep = index.row() == 0

    pad = components.DOWNLOAD_TILE_PAD
    tile = option.rect
    box = QRect(0, 0, components.DOWNLOAD_COVER_W, components.DOWNLOAD_COVER_H)
    box.moveTopLeft(tile.topLeft())
    box.translate((tile.width() - box.width()) // 2, pad)
    radius = components.PREVIEW_COVER_RADIUS

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    pmap = index.data(Qt.ItemDataRole.DecorationRole)
    pmap = pmap if isinstance(pmap, QPixmap) else QPixmap(pmap) if pmap is not None else QPixmap()
    if waiting or pmap.isNull():
        art = QRect(box)
        path = QPainterPath()
        path.addRoundedRect(QRectF(art), radius, radius)
        painter.fillPath(path, QColor(chrome.track))
        if waiting:
            spin = QRect(0, 0, components.DOWNLOAD_STATE_SPINNER, components.DOWNLOAD_STATE_SPINNER)
            spin.moveCenter(art.center())
            draw_spinner(painter, self.animator, spin, option.palette.color(option.palette.ColorRole.Base))
    else:
        art = fitted(pmap, box)
        path = QPainterPath()
        path.addRoundedRect(QRectF(art), radius, radius)
        painter.save()
        painter.setClipPath(path)
        painter.drawPixmap(art, pmap)
        painter.restore()
        # A hairline round the artwork, so a white cover on a white page
        # still has an edge.
        painter.setPen(QPen(QColor(chrome.border), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(art).adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)

    if selected or hovered:
        ring = components.DOWNLOAD_RING
        gap = components.DOWNLOAD_RING_GAP
        off = gap + ring / 2
        ring_rect = QRectF(art).adjusted(-off, -off, off, off)
        painter.setPen(QPen(QColor(chrome.accent if selected else chrome.scroll_hover), ring))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(ring_rect, radius + off, radius + off)

    # Two lines under the box.
    text_top = box.bottom() + 1 + components.DOWNLOAD_TILE_TEXT_GAP
    width = tile.width() - 4
    heading = QFont(option.font)
    heading.setWeight(QFont.Weight(primitives.FONT_WEIGHT['semibold']))
    caption = QFont(option.font)
    caption.setPixelSize(components.FONT_SIZE_CAPTION)
    first = _('Keep current cover') if keep else source
    painter.setFont(heading)
    fm = painter.fontMetrics()
    line = QRect(tile.left() + 2, text_top, width, fm.height())
    painter.setPen(option.palette.color(option.palette.ColorRole.Text))
    flags = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine
    painter.drawText(line, flags, fm.elidedText(first, Qt.TextElideMode.ElideRight, width))
    painter.setFont(caption)
    fm2 = painter.fontMetrics()
    line2 = QRect(line.left(), line.bottom() + 1 + components.DOWNLOAD_LINE_GAP, width, fm2.height())
    painter.setPen(QColor(chrome.muted))
    painter.drawText(line2, flags, fm2.elidedText(detail, Qt.TextElideMode.ElideRight, width))
    painter.restore()


def dress_view(view) -> None:
    from qt.core import QFrame

    view.setObjectName('zenCoverGrid')
    view.setFrameShape(QFrame.Shape.NoFrame)
    view.setGridSize(tile_size())
    view.setSpacing(0)
    view.setUniformItemSizes(True)
    view.setMouseTracking(True)
    view.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover)
    view.setIconSize(QSize(components.DOWNLOAD_COVER_W, components.DOWNLOAD_COVER_H))

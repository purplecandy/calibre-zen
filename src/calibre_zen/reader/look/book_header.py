#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The book, at the top of the contents panel: its cover, title and authors.

A contents list on its own says nothing about which book it is the contents
of. The header is what Apple Books and the main window's preview put there: a
small cover, the title in two lines at most, the authors under it, and an
info button that opens calibre's own book details (the `metadata` shortcut).

Read from the book calibre has already prepared for reading, not from a
library: the prepared directory holds `calibre-book-metadata.json` and the
manifest that names the cover image, so a book opened from the file manager
gets a header too.

Two wraps, from outside: `qt.dress` adds the header to the panel once the
window is built, and `EbookViewer.load_finished` fills it for each book.
"""

import json
import os

from qt.core import QFontMetrics, QHBoxLayout, QLabel, QPainter, QPainterPath, QPixmap, QRectF, QSize, QSizePolicy, Qt, QToolButton, QVBoxLayout, QWidget

from calibre_zen.theme.tokens import components

MARK = 'zen_book_header'
MANIFEST = 'calibre-book-manifest.json'
METADATA = 'calibre-book-metadata.json'


def read_book(base: str) -> dict:
    "Title, authors and cover path of a prepared book. Missing pieces are empty; never raises."
    ans = {'title': '', 'authors': '', 'cover': ''}
    if not base:
        return ans
    try:
        with open(os.path.join(base, METADATA), 'rb') as f:
            mi = json.loads(f.read())
        ans['title'] = mi.get('title') or ''
        authors = mi.get('authors') or []
        ans['authors'] = ' & '.join(a for a in authors if a and a != 'Unknown') if isinstance(authors, list) else str(authors)
    except Exception:
        pass
    try:
        with open(os.path.join(base, MANIFEST), 'rb') as f:
            manifest = json.loads(f.read())
        name = manifest.get('raster_cover_name') or ''
        path = os.path.join(base, *name.split('/')) if name else ''
        if path and os.path.isfile(path):
            ans['cover'] = path
    except Exception:
        pass
    return ans


def elide_lines(text: str, fm: QFontMetrics, width: int, lines: int) -> str:
    "`text` word-wrapped into at most `lines` lines of `width`, the last one cut with an ellipsis."
    words = text.split()
    out = []
    while words and len(out) < lines:
        line = words.pop(0)
        while words and fm.horizontalAdvance(line + ' ' + words[0]) <= width:
            line += ' ' + words.pop(0)
        out.append(line)
    if words and out:
        out[-1] = fm.elidedText(out[-1] + ' ' + ' '.join(words), Qt.TextElideMode.ElideRight, width)
    elif out and fm.horizontalAdvance(out[-1]) > width:
        out[-1] = fm.elidedText(out[-1], Qt.TextElideMode.ElideRight, width)
    return '\n'.join(out)


def rounded(pixmap: QPixmap, size: QSize, radius: float, dpr: float) -> QPixmap:
    "The cover scaled into `size` (aspect kept, centred), corners rounded, drawn for the screen's pixel ratio."
    out = QPixmap(int(size.width() * dpr), int(size.height() * dpr))
    out.setDevicePixelRatio(dpr)
    out.fill(Qt.GlobalColor.transparent)
    scaled = pixmap.scaled(out.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    scaled.setDevicePixelRatio(dpr)
    w, h = scaled.width() / dpr, scaled.height() / dpr
    x, y = (size.width() - w) / 2, (size.height() - h) / 2
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(x, y, w, h), radius, radius)
    p.setClipPath(clip)
    p.drawPixmap(QRectF(x, y, w, h), scaled, QRectF(scaled.rect()))
    p.end()
    return out


class BookHeader(QWidget):
    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.setObjectName('zenDockBook')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.title_text = self.authors_text = ''
        self.cover_source = None

        lay = QHBoxLayout(self)
        pad = components.READER_PANEL_PAD
        lay.setContentsMargins(pad, pad, pad // 2, pad)
        lay.setSpacing(components.READER_BOOK_GAP)

        self.cover = c = QLabel(self)
        c.setObjectName('zenDockBookCover')
        c.setFixedSize(components.READER_BOOK_COVER_W, components.READER_BOOK_COVER_H)
        c.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(c, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(2)
        self.title = t = QLabel(self)
        t.setObjectName('zenDockBookTitle')
        f = t.font()
        f.setPixelSize(components.READER_BOOK_TITLE_SIZE)
        f.setWeight(f.Weight.DemiBold)
        t.setFont(f)
        t.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.authors = a = QLabel(self)
        a.setObjectName('zenDockBookAuthors')
        a.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text.addStretch(1)
        text.addWidget(t)
        text.addWidget(a)
        text.addStretch(1)
        lay.addLayout(text, 1)

        self.info = b = QToolButton(self)
        b.setObjectName('zenDockBookInfo')
        b.setAutoRaise(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        side = components.READER_TITLE_BUTTON
        b.setFixedSize(side, side)
        icon = self.glyph('info-circle')
        if icon is None:
            b.setText('i')
        else:
            b.setIcon(icon)
            b.setIconSize(QSize(components.READER_BOOK_INFO_ICON, components.READER_BOOK_INFO_ICON))
        from calibre.utils.localization import _

        b.setToolTip(_('Show book details'))
        b.clicked.connect(self.show_details)
        lay.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)
        self.setVisible(False)

    @staticmethod
    def glyph(name: str):
        try:
            from calibre_zen.icons import registry

            return registry.glyph_icon(name)
        except Exception:
            return None

    def show_details(self):
        self.viewer.web_view.trigger_shortcut('metadata')

    def set_book(self, book: dict) -> None:
        self.title_text = book.get('title') or ''
        self.authors_text = book.get('authors') or ''
        self.cover_source = QPixmap(book['cover']) if book.get('cover') else None
        if self.cover_source is not None and self.cover_source.isNull():
            self.cover_source = None
        self.cover.setVisible(self.cover_source is not None)
        self.setVisible(bool(self.title_text or self.cover_source))
        self.setToolTip('\n'.join(x for x in (self.title_text, self.authors_text) if x))
        self.relayout()

    def relayout(self) -> None:
        width = max(40, self.title.width())
        self.title.setText(elide_lines(self.title_text, QFontMetrics(self.title.font()), width, 2))
        self.authors.setText(QFontMetrics(self.authors.font()).elidedText(self.authors_text, Qt.TextElideMode.ElideRight, width))
        self.authors.setVisible(bool(self.authors_text))
        if self.cover_source is not None:
            size = QSize(components.READER_BOOK_COVER_W, components.READER_BOOK_COVER_H)
            self.cover.setPixmap(rounded(self.cover_source, size, components.READER_BOOK_COVER_RADIUS, self.devicePixelRatioF()))

    def resizeEvent(self, ev):  # noqa: N802  (matching the Qt name is the point)
        super().resizeEvent(ev)
        self.relayout()

    def sizeHint(self):  # noqa: N802
        pad = components.READER_PANEL_PAD
        return QSize(200, components.READER_BOOK_COVER_H + 2 * pad)


def add(viewer) -> None:
    "Put the header at the top of the contents panel, once."
    if getattr(viewer, MARK, None) is not None:
        return
    header = BookHeader(viewer, viewer.toc_container)
    viewer.toc_container.layout().insertWidget(0, header)
    setattr(viewer, MARK, header)


def update(viewer) -> None:
    header = getattr(viewer, MARK, None)
    if header is None:
        return
    data = getattr(viewer, 'current_book_data', None) or {}
    header.set_book(read_book(data.get('base') or ''))


def wrap_load_finished(ui) -> bool:
    cls = ui.EbookViewer
    orig = cls.load_finished
    if getattr(orig, MARK, False):
        return False

    def load_finished(self, ok, data):
        ans = orig(self, ok, data)
        try:
            if ok:
                update(self)
        except Exception:
            import traceback

            traceback.print_exc()
        return ans

    setattr(load_finished, MARK, True)
    load_finished.__wrapped__ = orig
    cls.load_finished = load_finished
    return True

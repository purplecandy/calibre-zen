#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The top half: what is selected, in the largest type on the screen.

Deliberately a stub -- cover, title, author, and nothing else. The design pass
for it comes later; what it has to be right about now is where it gets its data
and when it updates, because that is the part the later pass should not have to
redo.

It follows `library_view`'s current row rather than whichever view is on
screen: `AlternateViews` keeps the main view's current index in step with the
grid and the bookshelf in both directions (`alternate_views.py:582-597`), so
one connection covers all three.

calibre's own Book details panel is untouched and stays wherever the reader
docked it. This is not a replacement for it and should not grow into one
without that being a decision.
"""

from qt.core import QColor, QHBoxLayout, QLabel, QPixmap, QSize, Qt, QVBoxLayout, QWidget

from calibre.gui2.library.caches import CoverThumbnailCache
from calibre_zen.theme import rewrite
from calibre_zen.theme.tokens import components, primitives


class PreviewPane(QWidget):
    def __init__(self, gui, parent=None):
        super().__init__(parent)
        self.setObjectName('zenPreview')
        self.gui = gui
        self.book_id = None
        self.setMinimumHeight(components.PREVIEW_COVER_H // 2)

        layout = QHBoxLayout(self)
        pad = components.PREVIEW_PAD
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(pad)

        self.cover = QLabel(self)
        self.cover.setFixedSize(QSize(components.PREVIEW_COVER_W, components.PREVIEW_COVER_H))
        self.cover.setScaledContents(True)
        layout.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(4)
        self.title = QLabel(self)
        self.title.setWordWrap(True)
        self.author = QLabel(self)
        self.author.setWordWrap(True)
        text.addWidget(self.title)
        text.addWidget(self.author)
        text.addStretch(1)
        layout.addLayout(text, 1)

        self.covers = CoverThumbnailCache(
            thumbnail_size=(components.PREVIEW_COVER_W * 2, components.PREVIEW_COVER_H * 2),
            name='zen-preview-thumbnail-cache',
            version=1,
            ram_limit=40,
            parent=self,
        )
        self.covers.rendered.connect(self.cover_rendered)
        self.refresh_palette()

    def refresh_palette(self) -> None:
        chrome = rewrite.chrome()
        self.title.setStyleSheet(f'font-size: 20px; font-weight: {primitives.FONT_WEIGHT["semibold"]};')
        self.author.setStyleSheet(f'color: {chrome.muted};')
        self.placeholder = QPixmap(self.cover.size())
        self.placeholder.fill(QColor(chrome.track))

    # Wiring {{{

    def attach(self) -> None:
        "Follow the library view's current row. Safe to call again."
        view = self.gui.library_view
        self.covers.set_database(view._model.db)
        selection = view.selectionModel()
        if selection is not None:
            try:
                selection.currentChanged.disconnect(self.current_changed)
            except TypeError:
                pass
            selection.currentChanged.connect(self.current_changed)
        self.show_index(view.currentIndex())

    def current_changed(self, current, previous=None) -> None:
        self.show_index(current)

    def cover_rendered(self, book_id, pixmap) -> None:
        if book_id == self.book_id:
            self.set_cover(pixmap)

    # }}}

    def show_index(self, index) -> None:
        if index is None or not index.isValid():
            self.book_id = None
            self.title.setText('')
            self.author.setText('')
            self.cover.setPixmap(self.placeholder)
            return
        model = index.model()
        self.book_id = index.data(Qt.ItemDataRole.UserRole)
        self.title.setText(self.column_text(model, index.row(), 'title'))
        self.author.setText(self.column_text(model, index.row(), 'authors'))
        self.set_cover(None if self.book_id is None else self.covers.thumbnail_as_pixmap(self.book_id))

    def column_text(self, model, row: int, name: str) -> str:
        "Read the field out of its own cell -- already formatted, no metadata lookup."
        try:
            column = model.column_map.index(name)
        except AttributeError, ValueError:
            return ''
        value = model.index(row, column).data(Qt.ItemDataRole.DisplayRole)
        return '' if value is None else str(value)

    def set_cover(self, pixmap) -> None:
        if pixmap is None or pixmap.isNull():
            self.cover.setPixmap(self.placeholder)
            return
        self.cover.setPixmap(pixmap)

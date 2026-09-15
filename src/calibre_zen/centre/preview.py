#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The top half: what is selected, and what is known about it.

Cover, series, title, authors, a line of facts, the tags as pills and the
description -- roughly the header every modern reading app puts above a book,
built out of what calibre already stores rather than out of what those apps
fetch from a server. Ratings counts, reader histograms and genre taxonomies
have no local equivalent and are not invented here.

Everything comes from `db.new_api.get_proxy_metadata(book_id)`, which reads
each field from the database only when it is asked for -- so the handful used
here cost a handful of lookups, not a full metadata load. Fields are rendered
with `ProxyMetadata.format_field`, which is calibre's own formatter: the rating
arrives as "4.5" out of five rather than the 0-10 integer stored, a date as
"Mar 2015" in the reader's locale, and a series as "Name [2]". Formatting them
here would mean disagreeing with every other place in calibre that shows the
same value.

It follows `library_view`'s current row rather than whichever view is on
screen: `AlternateViews` keeps the main view's current index in step with the
grid and the bookshelf in both directions (`alternate_views.py:582-597`), so
one connection covers all three. It also listens for `dataChanged`, so editing
a book's metadata updates the panel without a reselect.

calibre's own Book details panel is untouched and stays wherever the reader
docked it. This is the glance; that is still the full record, and the two are
not meant to converge.
"""

from qt.core import QColor, QHBoxLayout, QLabel, QPainter, QPainterPath, QPixmap, QRectF, QSize, Qt, QTextDocument, QVBoxLayout, QWidget

from calibre.gui2.library.caches import CoverThumbnailCache
from calibre_zen.theme import generate, rewrite
from calibre_zen.theme.tokens import components

SEPARATOR = ' · '


def plain_text(html: str) -> str:
    """
    A book's description, as text.

    calibre stores comments as HTML. Qt's own parser is already here and gives
    back clean text; `calibre.utils.html2text` is the other candidate and it
    returns Markdown, which would put literal asterisks on the screen wherever
    a description happened to use bold.
    """
    if not html:
        return ''
    doc = QTextDocument()
    doc.setHtml(html)
    return ' '.join(doc.toPlainText().split())


class Pill(QLabel):
    "One tag. A dynamic property rather than an objectName -- there are many."

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setProperty('zenPill', True)


class PreviewPane(QWidget):
    def __init__(self, gui, parent=None):
        super().__init__(parent)
        self.setObjectName('zenPreview')
        self.gui = gui
        self.book_id = None
        self._model = None
        self.setMinimumHeight(components.PREVIEW_COVER_H // 3)

        outer = QHBoxLayout(self)
        pad = components.PREVIEW_PAD
        outer.setContentsMargins(pad, pad, pad, pad)
        outer.setSpacing(pad)

        self.cover = QLabel(self)
        self.cover.setFixedSize(QSize(components.PREVIEW_COVER_W, components.PREVIEW_COVER_H))
        outer.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignTop)

        column = QVBoxLayout()
        column.setSpacing(components.PREVIEW_GAP)
        outer.addLayout(column, 1)

        self.series = QLabel(self)
        self.series.setObjectName('zenPreviewSeries')
        self.title = QLabel(self)
        self.title.setObjectName('zenPreviewTitle')
        self.title.setWordWrap(True)
        self.authors = QLabel(self)
        self.authors.setObjectName('zenPreviewAuthors')
        self.authors.setWordWrap(True)
        column.addWidget(self.series)
        column.addWidget(self.title)
        column.addWidget(self.authors)

        # The facts line: a star, the rating, then everything else run together
        # with middle dots. The star is a pixmap rather than a character
        # because the UI font is not guaranteed to have one.
        facts = QHBoxLayout()
        facts.setSpacing(4)
        self.star = QLabel(self)
        self.star.setFixedSize(QSize(components.PREVIEW_MARK, components.PREVIEW_MARK))
        self.rating = QLabel(self)
        self.rating.setObjectName('zenPreviewFacts')
        self.facts = QLabel(self)
        self.facts.setObjectName('zenPreviewFacts')
        facts.addWidget(self.star)
        facts.addWidget(self.rating)
        facts.addWidget(self.facts, 1)
        column.addLayout(facts)

        self.tags = QHBoxLayout()
        self.tags.setSpacing(5)
        column.addLayout(self.tags)

        self.description = QLabel(self)
        self.description.setObjectName('zenPreviewDescription')
        self.description.setWordWrap(True)
        self.description.setTextFormat(Qt.TextFormat.PlainText)
        self.description.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        column.addWidget(self.description, 1)

        self.covers = CoverThumbnailCache(
            thumbnail_size=(components.PREVIEW_COVER_W * 2, components.PREVIEW_COVER_H * 2),
            name='zen-preview-thumbnail-cache',
            version=2,
            ram_limit=40,
            parent=self,
        )
        self.covers.rendered.connect(self.cover_rendered)
        self.refresh_palette()
        self.show_index(None)

    # Wiring {{{

    def attach(self) -> None:
        "Follow the library view's current row and its metadata. Safe to call again."
        view = self.gui.library_view
        model = view._model
        self.covers.set_database(model.db)
        selection = view.selectionModel()
        if selection is not None:
            try:
                selection.currentChanged.disconnect(self.current_changed)
            except TypeError:
                pass
            selection.currentChanged.connect(self.current_changed)
        if model is not self._model:
            if self._model is not None:
                try:
                    self._model.dataChanged.disconnect(self.data_changed)
                except TypeError:
                    pass
            model.dataChanged.connect(self.data_changed)
            self._model = model
        self.show_index(view.currentIndex())

    def current_changed(self, current, previous=None) -> None:
        self.show_index(current)

    def data_changed(self, *args) -> None:
        # An edit anywhere can be an edit to this book; re-reading six fields
        # is cheaper than working out whether it was.
        self.show_index(self.gui.library_view.currentIndex())

    def cover_rendered(self, book_id, pixmap) -> None:
        if book_id == self.book_id:
            self.set_cover(pixmap)

    def refresh_palette(self) -> None:
        chrome = rewrite.chrome()
        self.star.setPixmap(generate.mark_icon('star', chrome.accent).pixmap(components.PREVIEW_MARK, components.PREVIEW_MARK))
        self.placeholder = self.rounded(None, chrome)

    # }}}

    # Painting the cover {{{

    def rounded(self, pixmap, chrome) -> QPixmap:
        "The cover, corner-rounded to match a row card and a button."
        size = self.cover.size()
        dpr = self.devicePixelRatioF()
        out = QPixmap(int(size.width() * dpr), int(size.height() * dpr))
        out.setDevicePixelRatio(dpr)
        out.fill(QColor(0, 0, 0, 0))
        painter = QPainter(out)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, size.width(), size.height()), components.PREVIEW_COVER_RADIUS, components.PREVIEW_COVER_RADIUS)
        if pixmap is None or pixmap.isNull():
            painter.fillPath(path, QColor(chrome.track))
        else:
            painter.setClipPath(path)
            scaled = pixmap.scaled(
                size * dpr,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            scaled.setDevicePixelRatio(dpr)
            x = (size.width() - scaled.width() / dpr) / 2
            y = (size.height() - scaled.height() / dpr) / 2
            painter.drawPixmap(int(x), int(y), scaled)
        painter.end()
        return out

    def set_cover(self, pixmap) -> None:
        self.cover.setPixmap(self.placeholder if pixmap is None or pixmap.isNull() else self.rounded(pixmap, rewrite.chrome()))

    # }}}

    # Filling it in {{{

    def show_index(self, index) -> None:
        if index is None or not index.isValid() or self._model is None:
            return self.show_nothing()
        self.book_id = index.data(Qt.ItemDataRole.UserRole)
        if self.book_id is None:
            return self.show_nothing()
        try:
            api = self._model.db.new_api
            mi = api.get_proxy_metadata(self.book_id)
        except Exception:
            return self.show_nothing()

        self.series.setText((mi.format_field('series')[1] or '').upper())
        self.series.setVisible(bool(self.series.text()))
        self.title.setText(mi.title or '')
        self.authors.setText(mi.format_field('authors')[1] or '')

        rating = mi.format_field('rating')[1]
        self.star.setVisible(bool(rating))
        self.rating.setVisible(bool(rating))
        self.rating.setText(rating or '')
        facts = SEPARATOR.join(self.fact_parts(mi, api))
        # The rating is its own label so the star can sit against it, which
        # leaves it to this to put the dot back between the two halves.
        self.facts.setText(SEPARATOR.lstrip() + facts if rating and facts else facts)

        self.set_tags(list(mi.tags or ()))
        self.description.setText(plain_text(mi.comments))
        self.set_cover(self.covers.thumbnail_as_pixmap(self.book_id))

    def fact_parts(self, mi, api) -> list:
        """
        The run-together line after the rating.

        Only what is actually known -- a book with no publisher should not show
        an empty gap between two dots.
        """
        parts = []
        published = mi.format_field('pubdate')[1]
        if published:
            parts.append(published)
        pages = api.field_for('pages', self.book_id, default_value=None)
        if pages:
            parts.append(_('%d pages') % pages)
        if mi.publisher:
            parts.append(mi.publisher)
        formats = api.formats(self.book_id) or ()
        if formats:
            parts.append(', '.join(formats))
        return parts

    def set_tags(self, tags: list) -> None:
        while self.tags.count():
            item = self.tags.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        shown = tags[: components.PREVIEW_MAX_TAGS]
        for tag in shown:
            self.tags.addWidget(Pill(tag, self))
        if len(tags) > len(shown):
            self.tags.addWidget(Pill(f'+{len(tags) - len(shown)}', self))
        self.tags.addStretch(1)

    def show_nothing(self) -> None:
        self.book_id = None
        for label in (self.series, self.title, self.authors, self.rating, self.facts, self.description):
            label.setText('')
        self.series.setVisible(False)
        self.star.setVisible(False)
        self.rating.setVisible(False)
        self.set_tags([])
        self.cover.setPixmap(self.placeholder)

    # }}}

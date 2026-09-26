#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The matches, one card each.

calibre's `ResultsView` is a five-column `QTableView`: rank, title and author
as rich text, year and publisher as rich text, and two check-mark columns for
"has cover" and "has summary". The view stays -- its keyboard handling, its
double-click to accept and its selection are what the dialog's Next button
reads -- and it is turned into a list: the rank column is kept and every other
column hidden, the rank column stretched across, and `MatchDelegate` paints a
whole card into it from the `Metadata` the model already hands out as
`UserRole`. What the hidden columns said is on the card, in words.

The headers go too, and with them clicking to sort. The same five sorts are
on a menu in the page header (`SORTS`), which calls the view's own
`sortByColumn`, so the model's `sort` is still the thing that orders them.

**The cover on a card is a placeholder.** At this stage calibre has only
asked each source *whether* it has a cover; the images are fetched on the
next page, per source, not per match. A thumbnail here would mean a download
of our own before the reader has chosen anything, which is fetching logic,
not presentation. So a card shows a 2:3 tile with the title's initial, and
says in words whether a cover was reported.
"""

from qt.core import QColor, QFont, QItemSelectionModel, QPainter, QPainterPath, QPalette, QPen, QRect, QRectF, QSize, QStyle, QStyledItemDelegate, Qt

from calibre.gui2 import qapplication_or_fail
from calibre_zen.download.chrome import colors
from calibre_zen.theme.tokens import components, primitives

# The page header's sort menu: a label, the model column calibre sorts by and
# the order to ask for. calibre's ResultsModel.sort reverses on *ascending*
# (it sorts with reverse=order == AscendingOrder), so "best first" is
# descending on the rank and "newest first" is ascending on the date.
SORTS = (
    ('Best match', 0, Qt.SortOrder.DescendingOrder),
    ('Title', 1, Qt.SortOrder.DescendingOrder),
    ('Newest', 2, Qt.SortOrder.AscendingOrder),
    ('With a cover', 3, Qt.SortOrder.AscendingOrder),
    ('With a summary', 4, Qt.SortOrder.AscendingOrder),
)


def source_names(book) -> list:
    """
    Which configured sources a match came from, as far as calibre still knows.

    A result crosses a process boundary as OPF before the dialog sees it, and
    the plugin that found it is not in the OPF. What survives is each
    source's own identifier -- `google:`, `amazon:`, `edelweiss:` -- and every
    source declares which of those it writes in its `touched_fields`. ISBN is
    written by nearly all of them, so it says nothing about which. A merged
    match names every source it came from.
    """
    ids = {k.lower() for k in (getattr(book, 'identifiers', None) or {})}
    if not ids:
        return []
    names = []
    for plugin, keys in _source_keys():
        if ids & keys:
            names.append(plugin)
    return names


_keys_cache = None


def _source_keys() -> list:
    global _keys_cache
    if _keys_cache is None:
        from calibre.customize.ui import metadata_plugins

        out = []
        for p in metadata_plugins(['identify']):
            keys = {f.partition(':')[2].lower() for f in getattr(p, 'touched_fields', ()) if f.startswith('identifier:')}
            keys.discard('isbn')
            if keys:
                out.append((p.name, keys))
        _keys_cache = out
    return _keys_cache


def year_of(book) -> str:
    from calibre.utils.date import format_date, is_date_undefined

    d = getattr(book, 'pubdate', None)
    if d is None or is_date_undefined(d):
        return ''
    return format_date(d, 'yyyy')


def facts_line(book) -> str:
    "Publisher and year, joined the way the preview joins its facts."
    return ' · '.join(x for x in ((getattr(book, 'publisher', None) or '').strip(), year_of(book)) if x)


def has_line(book) -> str:
    "What calibre's two check-mark columns said, in words."
    parts = []
    if getattr(book, 'has_cached_cover_url', False):
        parts.append(_('Cover'))
    if getattr(book, 'comments', None):
        parts.append(_('Summary'))
    return ' · '.join(parts) if parts else _('No cover')


def initial(title: str) -> str:
    for word in (title or '').split():
        if word.lower() not in {'the', 'a', 'an'} and word[:1].isalnum():
            return word[:1].upper()
    return (title or '?')[:1].upper()


class MatchDelegate(QStyledItemDelegate):
    "One match: a card with a cover tile, title, authors, publisher and year, and its source."

    def sizeHint(self, option, index):  # noqa: N802  (matching the Qt name is the point)
        return QSize(components.DOWNLOAD_MATCH_MIN_WIDTH, components.DOWNLOAD_MATCH_HEIGHT)

    def paint(self, painter, option, index):
        from calibre.ebooks.metadata import authors_to_string

        book = index.data(Qt.ItemDataRole.UserRole)
        if book is None:
            return
        chrome = colors()
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        gap = components.DOWNLOAD_MATCH_GAP
        card = QRectF(option.rect).adjusted(1, gap / 2, -1, -gap / 2)
        radius = components.RADIUS_PANEL
        ring = components.DOWNLOAD_RING
        # The page a form's groups are drawn on (18-forms.qss), so a card and
        # the panel beside it are the same surface.
        # The application's, not the option's: the sheet makes this view's
        # own background transparent, and the option carries that.
        base = qapplication_or_fail().palette().color(QPalette.ColorRole.Base)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        if selected:
            # A ring, and a light wash inside it: the card stays a card with
            # its text in the ordinary colours, and the ring is what says
            # "this one". A solid accent block the size of a card would be
            # the loudest thing on the page.
            half = ring / 2
            path.addRoundedRect(card.adjusted(half, half, -half, -half), radius - half, radius - half)
            painter.fillPath(path, base)
            painter.fillPath(path, _rgba(chrome.hover))
            painter.setPen(QPen(QColor(chrome.accent), ring))
            painter.drawPath(path)
        else:
            path.addRoundedRect(card.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
            painter.fillPath(path, QColor(chrome.surface_hover) if hovered else base)
            painter.setPen(QPen(QColor(chrome.border_strong if hovered else chrome.border), 1))
            painter.drawPath(path)

        pad = components.DOWNLOAD_MATCH_PAD
        inner = card.toRect().adjusted(pad, 0, -pad, 0)
        cover = QRect(0, 0, components.DOWNLOAD_MATCH_COVER_W, components.DOWNLOAD_MATCH_COVER_H)
        cover.moveCenter(QRect(inner.left(), inner.top(), cover.width(), inner.height()).center())
        self.paint_cover(painter, cover, book, chrome, option.font)

        body = QFont(option.font)
        caption = QFont(option.font)
        caption.setPixelSize(components.FONT_SIZE_CAPTION)
        heading = QFont(option.font)
        heading.setWeight(QFont.Weight(primitives.FONT_WEIGHT['semibold']))
        heading.setPixelSize(components.DOWNLOAD_MATCH_TITLE_SIZE)
        text = option.palette.color(option.palette.ColorRole.Text)
        muted = QColor(chrome.muted)

        # The right-hand corners: the source at the top, what it reported
        # having at the bottom. Each only narrows the line beside it.
        sources = ', '.join(source_names(book))
        has = has_line(book)
        caption_bold = QFont(caption)
        caption_bold.setWeight(QFont.Weight(primitives.FONT_WEIGHT['semibold']))
        painter.setFont(caption_bold)
        source_w = min(painter.fontMetrics().horizontalAdvance(sources) + 2, components.DOWNLOAD_MATCH_SOURCE_MAX) if sources else 0
        painter.setFont(caption)
        has_w = min(painter.fontMetrics().horizontalAdvance(has) + 2, components.DOWNLOAD_MATCH_SOURCE_MAX)
        left = cover.right() + 1 + pad
        right = inner.right()

        lines = [
            (book.title or _('Unknown'), heading, text, source_w),
            (authors_to_string(book.authors) if book.authors else '', body, text, 0),
            (facts_line(book), caption, muted, has_w),
        ]
        lines = [x for x in lines if x[0]]
        heights = []
        for _t, font, _c, _w in lines:
            painter.setFont(font)
            heights.append(painter.fontMetrics().height())
        total = sum(heights) + components.DOWNLOAD_LINE_GAP * (len(lines) - 1)
        y = inner.top() + (inner.height() - total) // 2
        for (t, font, color, beside), h in zip(lines, heights):
            painter.setFont(font)
            painter.setPen(color)
            limit = right - (beside + pad if beside else 0)
            line = QRect(left, y, max(0, limit - left), h)
            painter.drawText(
                line,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine,
                painter.fontMetrics().elidedText(t, Qt.TextElideMode.ElideRight, line.width()),
            )
            y += h + components.DOWNLOAD_LINE_GAP

        flags = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine
        painter.setPen(muted)
        if sources:
            painter.setFont(caption_bold)
            fm = painter.fontMetrics()
            top = QRect(right - source_w, cover.top(), source_w, fm.height())
            painter.drawText(top, flags, fm.elidedText(sources, Qt.TextElideMode.ElideRight, source_w))
        painter.setFont(caption)
        fm = painter.fontMetrics()
        bottom = QRect(right - has_w, cover.bottom() - fm.height() + 1, has_w, fm.height())
        painter.drawText(bottom, flags, fm.elidedText(has, Qt.TextElideMode.ElideRight, has_w))
        painter.restore()

    def paint_cover(self, painter, rect: QRect, book, chrome, font) -> None:
        radius = components.TABLE_COVER_RADIUS
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), radius, radius)
        painter.fillPath(path, QColor(chrome.track))
        f = QFont(font)
        f.setFamily(components.FONT_FAMILY_SERIF)
        f.setPixelSize(int(rect.height() * 0.3))
        painter.setFont(f)
        painter.setPen(QColor(chrome.scroll_hover))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, initial(book.title))


def _rgba(value: str) -> QColor:
    "Chrome writes its translucent colours as CSS rgba(); QColor wants them taken apart."
    if not value.startswith('rgba('):
        return QColor(value)
    r, g, b, a = (x.strip() for x in value[5:-1].split(','))
    alpha = float(a)
    return QColor(int(r), int(g), int(b), int(alpha * 255) if alpha <= 1 else int(alpha))


def dress_view(view) -> None:
    "Everything about the view that does not depend on a model: once, at construction."
    from qt.core import QAbstractItemView, QFrame

    view.setObjectName('zenMatchList')
    view.setFrameShape(QFrame.Shape.NoFrame)
    view.setShowGrid(False)
    view.setAlternatingRowColors(False)
    view.setWordWrap(False)
    view.setMouseTracking(True)
    view.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover)
    view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    view.horizontalHeader().setVisible(False)
    view.verticalHeader().setVisible(False)
    view.zen_delegate = MatchDelegate(view)


def dress_model(view) -> None:
    """
    After `show_results` has set a new model: one visible column, stretched,
    painted by MatchDelegate, and rows the card's height.

    `show_results` gives columns 1 and 2 calibre's rich-text delegate and then
    sizes rows and columns to their contents; a stretched section ignores the
    column sizing, and the rows are set after it.
    """
    from qt.core import QHeaderView

    model = view.model()
    if model is None:
        return
    header = view.horizontalHeader()
    for col in range(model.columnCount()):
        view.setColumnHidden(col, col != 0)
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    view.setItemDelegateForColumn(0, view.zen_delegate)
    vh = view.verticalHeader()
    vh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
    vh.setDefaultSectionSize(components.DOWNLOAD_MATCH_HEIGHT)
    for row in range(model.rowCount()):
        view.setRowHeight(row, components.DOWNLOAD_MATCH_HEIGHT)


def apply_sort(view, which: int) -> None:
    "Sort the matches as the header's menu asks, and keep the first one chosen."
    try:
        _label, column, order = SORTS[which]
    except IndexError:
        return
    model = view.model()
    if model is None or model.rowCount() == 0:
        return
    view.sortByColumn(column, order)
    dress_model(view)
    idx = model.index(0, 0)
    view.setCurrentIndex(idx)
    view.selectionModel().select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
    view.show_details(idx)

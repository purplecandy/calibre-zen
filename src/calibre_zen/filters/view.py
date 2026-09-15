#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The list itself: a flat `QListView`, a model holding one level's `Entry` rows,
and a delegate that paints them.

Why a painted list rather than a column of real row widgets, which is what the
reference design looks like and what the first experiment built: a category in
calibre is not a three-item picker. "Tags" in a working library is routinely
several thousand values, and a few thousand `QWidget`s is a second of build
time, a visible stall on every recount and tens of megabytes. A `QListView`
creates nothing per row and paints only what is on screen, and a level swap
becomes a model reset rather than a teardown of a layout.

The cost is that everything is drawn by hand -- there is no QSS for a chevron
that only appears on some rows. What the sheet still owns is the row's
*background*: `paint()` hands that to the style first, the way calibre's own
`TagDelegate` does, so hover and the panel's colours stay in
`qss/app/11-filters.qss` with the rest of the look, and only the foreground is
in this file.
"""

from qt.core import QAbstractListModel, QColor, QFont, QIcon, QListView, QModelIndex, QPalette, QPen, QRect, QSize, QStyledItemDelegate, Qt, pyqtSignal

from calibre.gui2 import empty_index, qapplication_or_fail
from calibre_zen.theme import generate, rewrite
from calibre_zen.theme.tokens import components, primitives

ENTRY_ROLE = Qt.ItemDataRole.UserRole


class FilterListModel(QAbstractListModel):
    "One level's rows. Replaced wholesale; nothing here is edited in place."

    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries = []

    def set_entries(self, entries: list) -> None:
        self.beginResetModel()
        self.entries = entries
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802  (matching the Qt name is the point)
        return 0 if parent.isValid() else len(self.entries)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.entries):
            return None
        entry = self.entries[index.row()]
        if role == ENTRY_ROLE:
            return entry
        if role == Qt.ItemDataRole.DisplayRole:
            return entry.label
        return None

    def entry_at(self, index):
        if not index.isValid() or not 0 <= index.row() < len(self.entries):
            return None
        return self.entries[index.row()]


class FilterDelegate(QStyledItemDelegate):
    """
    label -- value -- mark -- chevron, and a hairline underneath.

    Colours come from `Chrome`, recomputed when the palette changes rather than
    per row: a `Chrome` is two dozen blends and a list repaints a screenful at
    a time. The marks are the same `theme/marks/*.svg` the stylesheet uses,
    rendered per colour and cached, so a chevron here and a chevron on a combo
    box are one drawing.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icons = {}
        self.refresh_palette()

    def refresh_palette(self) -> None:
        self.chrome = rewrite.chrome()
        # The label's colour comes from the application palette rather than
        # from option.palette, so that every colour this delegate draws with
        # has one source: Chrome is built from the application palette too, and
        # a label that disagreed with the hairline under it would be disagreeing
        # about which theme is on.
        self.text_color = qapplication_or_fail().palette().color(QPalette.ColorRole.WindowText)
        self._icons.clear()

    def icon(self, name: str, color: str) -> QIcon:
        key = (name, color)
        icon = self._icons.get(key)
        if icon is None:
            icon = self._icons[key] = generate.mark_icon(name, color)
        return icon

    def sizeHint(self, option, index) -> QSize:  # noqa: N802  (matching the Qt name is the point)
        entry = index.data(ENTRY_ROLE)
        if entry is None:
            return super().sizeHint(option, index)
        if entry.kind == 'header':
            height = components.FILTER_HEADER_HEIGHT
        elif entry.strong:
            height = components.FILTER_ROW_HEIGHT
        else:
            height = components.FILTER_VALUE_ROW_HEIGHT
        return QSize(option.rect.width(), height)

    def paint(self, painter, option, index) -> None:
        entry = index.data(ENTRY_ROLE)
        if entry is None:
            return super().paint(painter, option, index)
        # The furniture first and the content never: painting against an index
        # into an empty model is how calibre's own TagDelegate asks the style
        # -- which is to say the app sheet -- for the row's background, hover
        # included, without it also drawing text we are about to lay out
        # ourselves. A header skips even that, so the view's colour shows
        # through and each group gets air above it.
        if entry.kind != 'header':
            QStyledItemDelegate.paint(self, painter, option, empty_index)
        self.initStyleOption(option, index)
        painter.save()
        if entry.kind == 'header':
            self._paint_header(painter, option, entry, self.chrome)
        else:
            self._paint_row(painter, option, entry, self.chrome)
        painter.restore()

    # Painting {{{

    def _hairline(self, painter, rect, chrome) -> None:
        painter.setPen(QPen(QColor(chrome.border_weak)))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

    def _paint_header(self, painter, option, entry, chrome) -> None:
        font = QFont(option.font)
        font.setPixelSize(components.FONT_SIZE_CAPTION)
        font.setWeight(QFont.Weight(primitives.FONT_WEIGHT['semibold']))
        painter.setFont(font)
        painter.setPen(QPen(QColor(chrome.muted)))
        rect = option.rect.adjusted(components.FILTER_PAD_X, 0, -components.FILTER_PAD_X, -2)
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom | Qt.TextFlag.TextSingleLine, entry.label)
        self._hairline(painter, option.rect, chrome)

    def _paint_row(self, painter, option, entry, chrome) -> None:
        pad = components.FILTER_PAD_X
        gap = components.FILTER_GAP
        mark = components.FILTER_MARK_SIZE
        rect = option.rect
        left = rect.left() + pad
        right = rect.right() - pad

        if entry.chevron:
            box = QRect(0, 0, mark, mark)
            box.moveCenter(QRect(right - mark, rect.top(), mark, rect.height()).center())
            self.icon('chevron-right', chrome.muted).paint(painter, box)
            right -= mark + gap

        if entry.mark:
            color = chrome.accent if entry.mark == 'check' else chrome.danger
            box = QRect(0, 0, mark, mark)
            box.moveCenter(QRect(right - mark, rect.top(), mark, rect.height()).center())
            self.icon(entry.mark, color).paint(painter, box)
            right -= mark + gap

        painter.setFont(QFont(option.font))
        if entry.value:
            # The value never takes more than half the row: a label elided to
            # make room for "Match any of the items" is the wrong trade, and
            # drawText clips rather than eliding when it is simply given too
            # little, which reads as a typo rather than as a truncation.
            #
            # elidedText() is asked only when the value genuinely does not fit.
            # Handing it exactly horizontalAdvance() elides anyway -- the
            # integer advance rounds down below the real width -- which is how
            # "any" came back as "a...".
            metrics = painter.fontMetrics()
            cap = max(0, right - left) // 2
            width = metrics.horizontalAdvance(entry.value)
            text = entry.value
            if width > cap:
                text, width = metrics.elidedText(entry.value, Qt.TextElideMode.ElideRight, cap), cap
            box = QRect(right - width, rect.top(), width, rect.height())
            painter.setPen(QPen(QColor(chrome.muted)))
            painter.drawText(box, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine, text)
            right -= width + gap

        label_font = QFont(option.font)
        if entry.strong:
            label_font.setWeight(QFont.Weight(primitives.FONT_WEIGHT['semibold']))
        painter.setFont(label_font)
        painter.setPen(QPen(self.text_color))
        box = QRect(left, rect.top(), max(0, right - left), rect.height())
        label = painter.fontMetrics().elidedText(entry.label, Qt.TextElideMode.ElideRight, box.width())
        painter.drawText(box, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine, label)

        self._hairline(painter, rect, chrome)

    # }}}


class FilterView(QListView):
    """
    Hover, one click, and a right-click that is forwarded to calibre's own
    context menu.

    A row can have two targets -- mark the value, or descend into its children
    -- so the click has to be hit-tested rather than just handed over as
    `clicked`. The tag browser does the same thing for its note and link
    glyphs, and for the same reason.
    """

    activated_entry = pyqtSignal(object, bool)  # entry, was the chevron hit
    context_requested = pyqtSignal(object, object)  # entry, global position

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('zenFilterList')
        self._model = FilterListModel(self)
        self.setModel(self._model)
        self.delegate = FilterDelegate(self)
        self.setItemDelegate(self.delegate)
        self.setSelectionMode(QListView.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.setUniformItemSizes(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setFrameShape(QListView.Shape.NoFrame)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

    def set_entries(self, entries: list) -> None:
        self._model.set_entries(entries)

    def refresh_palette(self) -> None:
        self.delegate.refresh_palette()
        self.viewport().update()

    def entry_at(self, pos):
        return self._model.entry_at(self.indexAt(pos))

    def _on_chevron(self, pos, index) -> bool:
        rect = self.visualRect(index)
        zone = components.FILTER_PAD_X + components.FILTER_MARK_SIZE + components.FILTER_GAP
        return pos.x() >= rect.right() - zone

    def mouseMoveEvent(self, e) -> None:
        entry = self.entry_at(e.pos())
        if entry is not None and entry.kind == 'row':
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(e.pos())
            entry = self._model.entry_at(index)
            if entry is not None and entry.kind == 'row':
                self.activated_entry.emit(entry, self._on_chevron(e.pos(), index))
        super().mouseReleaseEvent(e)

    def contextMenuEvent(self, e) -> None:
        entry = self.entry_at(e.pos())
        if entry is not None and entry.kind == 'row':
            self.context_requested.emit(entry, e.globalPos())
            e.accept()
            return
        super().contextMenuEvent(e)

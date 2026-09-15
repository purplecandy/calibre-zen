#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The book list, restyled: one composite **Details** cell per row -- cover
thumbnail, series line, bold title, author -- followed by whatever other
columns the reader has configured, on tall rounded row cards.

`BooksView` paints nothing itself; every cell goes through a delegate assigned
per column by `TableView.set_delegates`. So the look is entirely reachable from
outside, and none of the behaviour has to move: sorting, inline editing, column
resizing and the column-header context menu are all driven by the header and
the model, not by the delegates.

**Details is not a new column.** It is the `title` column, taken over: its
header says "Details", its cell paints the composite, and `authors` and
`series` are hidden because they are now inside it. Adding a column to
`BooksModel` would have meant a model of our own and an index translation on
every one of the couple of hundred places that talk to this view.

**None of that is written to the reader's library.** `BooksView.get_old_state`
and `write_state` are the only two methods that name the per-library pref
(`views.py:1001, 1127`), so wrapping them to use a key of our own gives the
overlay its own column layout: widths, sort order and hidden columns persist
normally *into our key*, calibre's key is never written again, and
CALIBRE_ZEN_CENTRE=0 hands back the layout the reader had. It also means the
arrangement is expressed as a *state dict* rather than as calls against the
header -- `apply_state` then does the hiding and the moving, in calibre's own
code, with its own save-state batching and its own Qt bug workarounds.

The card is drawn a cell at a time, because that is the only place a
`QTableView` lets anyone draw. Adjacent cells fill identically with no gap
between them and only the row's two outer ends are rounded, so N cells read as
one rounded row; `qss/app/12-centre.qss` takes away the item's own background
so Qt does not paint over it.
"""

from qt.core import QColor, QFont, QPainter, QPainterPath, QPalette, QPen, QRect, QRectF, QSize, QStyle, Qt

from calibre.gui2 import qapplication_or_fail
from calibre.gui2.library.caches import CoverThumbnailCache
from calibre.gui2.library.delegates import StyledItemDelegate
from calibre_zen.theme import rewrite
from calibre_zen.theme.tokens import components, primitives

# The composite is the title column wearing a different hat; these two are
# folded into it and hidden.
DETAILS_COLUMN = 'title'
FOLDED_COLUMNS = ('authors', 'series')

# Our own per-library column state, so calibre's stays exactly as the reader
# left it. Bump the suffix, not the prefix, if the arrangement ever changes
# shape enough that an old saved layout would be wrong.
STATE_KEY_PREFIX = 'zen centre '


# The saved layout {{{


def move_to_front(positions: dict, name: str) -> dict:
    "The visual positions that result from dragging `name` to the far left."
    start = positions.get(name)
    if start is None or start == 0:
        return positions
    out = {}
    for key, pos in positions.items():
        if key == name:
            out[key] = 0
        elif pos < start:
            out[key] = pos + 1
        else:
            out[key] = pos
    return out


def arrange(state: dict, column_map) -> dict:
    """
    Bake the Details arrangement into a saved-state dict.

    Done here rather than against the header so that `apply_state` -- which
    already batches save-state, works around a Qt relayout bug and knows about
    `ondevice` -- is the only thing that touches sections.
    """
    state = dict(state)
    hidden = set(state.get('hidden_columns') or ())
    hidden.update(name for name in FOLDED_COLUMNS if name in column_map)
    hidden.discard(DETAILS_COLUMN)
    state['hidden_columns'] = sorted(hidden)

    state['column_positions'] = move_to_front(dict(state.get('column_positions') or {}), DETAILS_COLUMN)

    sizes = dict(state.get('column_sizes') or {})
    sizes[DETAILS_COLUMN] = max(sizes.get(DETAILS_COLUMN, 0), components.TABLE_DETAILS_WIDTH)
    state['column_sizes'] = sizes
    return state


# }}}


def setup_view(view) -> None:
    """
    The three things about the view itself that the card look needs.

    Alternating stripes and grid lines are two more ideas about where a row
    ends, and the card is already one -- both off. The last section stretches
    so a row card reaches the right edge instead of stopping at the last
    column and leaving the card's end floating in the middle of the viewport;
    the cost is that the rightmost column can no longer be dragged narrower,
    which is the trade the reference design makes too.

    Header labels stay centred. `setDefaultAlignment` does nothing here --
    calibre's own `HeaderView.paintSection` assigns
    `opt.textAlignment = AlignHCenter` unconditionally (`views.py:125`) -- and
    left-aligning them means reimplementing that method's fifty lines of sort
    indicator and elide handling to change one flag. Not worth it for this.
    """
    view.setAlternatingRowColors(False)
    view.setShowGrid(False)
    view.horizontalHeader().setStretchLastSection(True)


# }}}


# Covers {{{

_cover_cache = None


def cover_cache():
    """
    Thumbnails for the Details cell.

    A cache of our own, with its own name: the grid view's is sized for a grid
    tile and sharing it would have the two of them re-rendering every cover
    past each other. Rendering is on a background thread and
    `thumbnail_as_pixmap` returns None for "not yet" -- never block a paint on
    it, draw the placeholder and wait for `rendered`.
    """
    global _cover_cache
    if _cover_cache is None:
        _cover_cache = CoverThumbnailCache(
            thumbnail_size=(components.TABLE_COVER_W * 2, components.TABLE_COVER_H * 2),
            name='zen-row-thumbnail-cache',
            version=1,
            ram_limit=300,
        )
    return _cover_cache


# }}}


# Painting {{{

# Chrome is two dozen colour blends, and a delegate paints one cell at a time:
# a screenful of a ten-column table is two hundred calls per repaint. Built
# once and dropped when the palette changes, which is what makes the theme
# switcher's effect reach the rows.
_chrome = None


def colors():
    "The live Chrome, built once per palette."
    global _chrome
    if _chrome is None:
        _chrome = rewrite.chrome()
    return _chrome


def forget_colors() -> None:
    "Called when the palette changes, so the next paint rebuilds from it."
    global _chrome
    _chrome = None


def text_color() -> QColor:
    "The label colour, from the application palette -- the same source as Chrome."
    return qapplication_or_fail().palette().color(QPalette.ColorRole.WindowText)


def card_path(rect: QRect, radius: int, round_left: bool, round_right: bool) -> QPainterPath:
    """
    The row card's slice for one cell: rounded only where the row actually
    ends, square where it meets the next cell along.
    """
    path = QPainterPath()
    r = QRectF(rect)
    if not round_left and not round_right:
        path.addRect(r)
        return path
    d = radius * 2
    path.moveTo(r.left() + (radius if round_left else 0), r.top())
    path.lineTo(r.right() - (radius if round_right else 0), r.top())
    if round_right:
        path.arcTo(QRectF(r.right() - d, r.top(), d, d), 90, -90)
        path.lineTo(r.right(), r.bottom() - radius)
        path.arcTo(QRectF(r.right() - d, r.bottom() - d, d, d), 0, -90)
    else:
        path.lineTo(r.right(), r.bottom())
    path.lineTo(r.left() + (radius if round_left else 0), r.bottom())
    if round_left:
        path.arcTo(QRectF(r.left(), r.bottom() - d, d, d), 270, -90)
        path.lineTo(r.left(), r.top() + radius)
        path.arcTo(QRectF(r.left(), r.top(), d, d), 180, -90)
    else:
        path.lineTo(r.left(), r.top())
    path.closeSubpath()
    return path


class ZenCellDelegate(StyledItemDelegate):
    """
    One cell. Draws the row card, then either the composite (Details) or hands
    over to the delegate calibre assigned for that column.

    Subclasses `StyledItemDelegate` rather than `QStyledItemDelegate` because
    `TableView` reads `is_editable_with_tab` and `ignore_kb_mods_on_edit` off
    whatever `itemDelegateForIndex` returns (`pin_columns.py:85-100`), and
    forwards every editing method to the wrapped delegate so that a rating
    column still opens a rating editor and a date column a date editor.
    """

    def __init__(self, inner, view, is_details: bool):
        super().__init__(view)
        self.inner = inner
        self.view = view
        self.is_details = is_details

    # Editing is the inner delegate's, unchanged {{{

    @property
    def is_editable_with_tab(self):
        return getattr(self.inner, 'is_editable_with_tab', True)

    @property
    def ignore_kb_mods_on_edit(self):
        return getattr(self.inner, 'ignore_kb_mods_on_edit', False)

    def createEditor(self, parent, option, index):  # noqa: N802  (matching the Qt name is the point)
        return self.inner.createEditor(parent, option, index)

    def setEditorData(self, editor, index):  # noqa: N802
        return self.inner.setEditorData(editor, index)

    def setModelData(self, editor, model, index):  # noqa: N802
        return self.inner.setModelData(editor, model, index)

    def updateEditorGeometry(self, editor, option, index):  # noqa: N802
        return self.inner.updateEditorGeometry(editor, option, index)

    # }}}

    def sizeHint(self, option, index):  # noqa: N802
        return QSize(self.inner.sizeHint(option, index).width(), components.TABLE_ROW_HEIGHT)

    def paint(self, painter, option, index):
        chrome = colors()
        card = option.rect.adjusted(0, components.TABLE_ROW_GAP // 2, 0, -(components.TABLE_ROW_GAP + 1) // 2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        first, last = self.row_ends(index)
        painter.fillPath(card_path(card, components.TABLE_ROW_RADIUS, first, last), QColor(self.card_color(chrome, selected, hovered)))
        painter.restore()

        if self.is_details:
            self.paint_details(painter, option, index, chrome, selected)
            return

        # Hand the content -- and only the content -- to calibre's delegate.
        # The card is already down, so the state flags that would make it draw
        # its own panel over the top are cleared, and the text colour is put
        # where an unselected cell's would be so clearing State_Selected does
        # not also lose the contrast.
        option.state &= ~QStyle.StateFlag.State_Selected
        option.state &= ~QStyle.StateFlag.State_MouseOver
        option.rect = option.rect.adjusted(components.TABLE_PAD_X, 0, -components.TABLE_PAD_X, 0)
        option.palette.setColor(QPalette.ColorRole.Text, QColor(chrome.accent_text) if selected else text_color())
        self.inner.paint(painter, option, index)

    # Helpers {{{

    def card_color(self, chrome, selected: bool, hovered: bool) -> str:
        if selected:
            return chrome.accent
        if hovered:
            return chrome.alt
        return chrome.menu_bg

    def row_ends(self, index) -> tuple:
        "Whether this cell is the left end of its row, the right end, or neither."
        header = self.view.horizontalHeader()
        visible = [i for i in range(header.count()) if not header.isSectionHidden(i)]
        if not visible:
            return True, True
        order = sorted(visible, key=header.visualIndex)
        return index.column() == order[0], index.column() == order[-1]

    def sibling_text(self, index, name: str) -> str:
        """
        A folded column's text, read out of its own cell.

        Hiding a section does not remove it from the model, so the author and
        series strings are already there, already formatted the way the reader
        asked for -- no metadata lookup per paint.
        """
        model = index.model()
        try:
            column = model.column_map.index(name)
        except AttributeError, ValueError:
            return ''
        value = model.index(index.row(), column).data(Qt.ItemDataRole.DisplayRole)
        return '' if value is None else str(value)

    # }}}

    def paint_details(self, painter, option, index, chrome, selected: bool) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = option.rect
        left = rect.left() + components.TABLE_PAD_X

        cover_rect = QRect(left, 0, components.TABLE_COVER_W, components.TABLE_COVER_H)
        cover_rect.moveCenter(QRect(left, rect.top(), components.TABLE_COVER_W, rect.height()).center())
        self.paint_cover(painter, cover_rect, index, chrome)
        left = cover_rect.right() + components.TABLE_PAD_X

        text_rect = QRect(left, rect.top(), max(0, rect.right() - components.TABLE_PAD_X - left), rect.height())
        series = self.sibling_text(index, 'series')
        title = str(index.data(Qt.ItemDataRole.DisplayRole) or '')
        author = self.sibling_text(index, 'authors')

        body = QFont(option.font)
        caption = QFont(option.font)
        caption.setPixelSize(components.FONT_SIZE_CAPTION)
        heading = QFont(option.font)
        heading.setWeight(QFont.Weight(primitives.FONT_WEIGHT['semibold']))

        strong = QColor(chrome.accent_text) if selected else text_color()
        muted = QColor(chrome.accent_text) if selected else QColor(chrome.muted)

        lines = []
        if series:
            lines.append((series, caption, muted))
        lines.append((title, heading, strong))
        if author:
            lines.append((author, body, muted))

        heights = []
        for text, font, _color in lines:
            painter.setFont(font)
            heights.append(painter.fontMetrics().height())
        total = sum(heights) + components.TABLE_LINE_GAP * (len(lines) - 1)
        y = text_rect.top() + (text_rect.height() - total) // 2

        for (text, font, color), height in zip(lines, heights):
            painter.setFont(font)
            painter.setPen(QPen(color))
            line = QRect(text_rect.left(), y, text_rect.width(), height)
            painter.drawText(
                line,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine,
                painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, line.width()),
            )
            y += height + components.TABLE_LINE_GAP
        painter.restore()

    def paint_cover(self, painter, rect, index, chrome) -> None:
        book_id = index.data(Qt.ItemDataRole.UserRole)
        pixmap = None
        if book_id is not None:
            pixmap = cover_cache().thumbnail_as_pixmap(book_id)

        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), components.TABLE_COVER_RADIUS, components.TABLE_COVER_RADIUS)
        if pixmap is None or pixmap.isNull():
            # None means "being rendered"; a null pixmap means the book has no
            # cover. Both get the same placeholder, so a row does not change
            # height or shift when the real one arrives.
            painter.fillPath(path, QColor(chrome.track))
            return
        painter.save()
        painter.setClipPath(path)
        scaled = pixmap.scaled(
            rect.size() * painter.device().devicePixelRatio(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(painter.device().devicePixelRatio())
        target = QRect(0, 0, rect.width(), rect.height())
        target.moveCenter(rect.center())
        painter.drawPixmap(target, scaled)
        painter.restore()


# }}}

#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
What a cover-grid tile does under the pointer.

Two things, and they are the first of the overlay's work to reach how the
cover grid is *drawn* rather than only how big it is (`grid.py`):

    a ring   around the hovered or selected cover, concentric with whatever
             corner radius the reader has set for covers
    a card   above the tile: the title, its year, the author, and the series
             if there is one

The ring replaces the tile's fill rather than joining it. Upstream's first act
in `paint` is a full-tile selection highlight, which in this palette is the
accent -- the same colour the ring wants to be, so on a focused view the two
would have cancelled out. The state flags are cleared before the original
runs, the same way `table.py` clears them before handing a cell to calibre's
delegate. A tile is an object rather than a band: it takes an outline, not a
wash.

The ring itself is drawn from a wrap of `CoverDelegate.paint_cover`, which
upstream calls with exactly the cover's rectangle -- the one rect in that delegate that
knows where the artwork ended up after being centred in a tile that is rarely
its shape. `paint` is wrapped too, but only to leave the row and the state
flags somewhere `paint_cover` can find them: that method is handed a painter, a
rect and a pixmap and nothing else. The alternative was to re-derive the
cover's rect out here from MARGIN, the title height and the pixmap's size,
which is six lines of arithmetic that would go quietly wrong the next time
upstream changed one of them.

Hover is tracked here rather than read off `option.state`, because the card
needs the tile's rectangle and a rest timer anyway, and one event filter
answers all three questions. It also means the ring does not depend on the
viewport having mouse tracking turned on, which is not ours to assume.

The card replaces calibre's tooltip for this view rather than joining it:
`CoverDelegate.helpEvent` is wrapped to say "handled" without showing
anything, which is how a delegate declines to show a tooltip. Nothing is lost
by that -- the card carries the same facts, the series line included.

Colours come from `Chrome`, so the card is the same surface as every other
tooltip in the app rather than a second opinion about what a floating panel
looks like. It is a `Qt::ToolTip` window, which means `theme/popups.py` has
already arranged for its corners and its pointer to composite against whatever
is behind them instead of against a square block.
"""

from qt.core import (
    QAbstractItemView,
    QColor,
    QEvent,
    QFont,
    QFontMetrics,
    QHelpEvent,
    QModelIndex,
    QObject,
    QPainter,
    QPainterPath,
    QPen,
    QPoint,
    QRect,
    QRectF,
    QSize,
    QStyle,
    QStyleOptionViewItem,
    Qt,
    QTimer,
    QWidget,
    pyqtSlot,
)

from calibre_zen.centre.table import colors
from calibre_zen.theme.tokens import components

_installed = False


# The ring {{{


def cover_path(rect: QRect, grow: int) -> QPainterPath:
    """
    The cover's own rounded shape, grown by `grow` pixels.

    `cover_corner_radius` is a reader preference and can be a percentage or a
    number of pixels (`gui2/__init__.py:2046`). A percentage grows with the
    box on its own; an absolute radius has to be grown by hand, or the ring
    is a different shape from the thing it is drawn around.
    """
    from calibre.gui2 import gprefs

    box = QRectF(rect).adjusted(-grow, -grow, grow, grow)
    path = QPainterPath()
    radius = gprefs['cover_corner_radius']
    if radius <= 0:
        path.addRect(box)
        return path
    relative = gprefs['cover_corner_radius_unit'] == '%'
    mode = Qt.SizeMode.RelativeSize if relative else Qt.SizeMode.AbsoluteSize
    size = radius if relative else radius + grow
    path.addRoundedRect(box, size, size, mode)
    return path


def ring_color(selected: bool, hovered: bool) -> str | None:
    """
    Selected is the accent, hovered is muted, and selected wins when it is
    both. Two weights rather than one, because they say different things: one
    is what you have chosen and the other is only what you are pointing at.
    """
    chrome = colors()
    if selected:
        return chrome.accent
    if hovered:
        return chrome.muted
    return None


def draw_ring(painter: QPainter, rect: QRect, selected: bool, hovered: bool) -> bool:
    colour = ring_color(selected, hovered)
    if colour is None:
        return False
    painter.save()
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        grow = components.GRID_RING_GAP + (components.GRID_RING / 2)
        painter.strokePath(cover_path(rect, grow), QPen(QColor(colour), components.GRID_RING))
    finally:
        painter.restore()
    return True


# }}}


# The card {{{


def book_lines(view, index) -> list | None:
    """
    What the card says about a book: a list of rows, each a list of runs, each
    run `(text, bold, muted)`.

    Read off the same fields calibre's own tooltip reads, so the card is not a
    second answer to the same question.
    """
    from calibre.ebooks.metadata import authors_to_string, fmt_sidx
    from calibre.utils.date import is_date_undefined

    model = index.model()
    db = getattr(model, 'db', None)
    if db is None:
        return None
    try:
        book_id = db.id(index.row())
    except Exception:
        return None
    api = db.new_api
    title = api.field_for('title', book_id, default_value='')
    if not title:
        return None
    rows = [[(title, True, False)]]

    pubdate = api.field_for('pubdate', book_id)
    if pubdate is not None and not is_date_undefined(pubdate):
        rows[0].append((f' ({pubdate.year})', False, True))

    authors = api.field_for('authors', book_id, default_value=())
    if authors:
        rows.append([(_('By %s') % authors_to_string(authors), False, False)])

    series = api.field_for('series', book_id)
    if series:
        from calibre.gui2 import config

        sidx = fmt_sidx(
            api.field_for('series_index', book_id, default_value=1.0),
            use_roman=config['use_roman_numerals_for_series_number'],
        )
        rows.append([(_('Book %(sidx)s of %(series)s') % dict(sidx=sidx, series=series), False, True)])
    return rows


class HoverCard(QWidget):
    """
    A tooltip with a pointer, placed against a tile rather than the cursor.

    Frameless and `Qt::ToolTip`, so it never takes focus and never activates
    the window; transparent to the mouse, so it cannot take the hover away
    from the tile that caused it.
    """

    def __init__(self, view):
        super().__init__(view, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.rows = []
        self.below = False  # the pointer is on top, because the card is under the tile
        self.point_x = 0  # where the pointer sits along the card's width

    # Geometry {{{

    def fonts(self) -> tuple:
        plain = QFont(self.font())
        bold = QFont(plain)
        bold.setWeight(QFont.Weight.DemiBold)
        return plain, bold

    def measure(self) -> QSize:
        plain, bold = self.fonts()
        fm = {True: QFontMetrics(bold), False: QFontMetrics(plain)}
        room = components.GRID_CARD_MAX_W - (2 * components.GRID_CARD_PAD_X)
        width = height = 0
        for i, row in enumerate(self.rows):
            width = max(width, sum(fm[b].horizontalAdvance(t) for t, b, _m in row))
            height += fm[row[0][1]].height()
            if i:
                height += components.GRID_CARD_LINE_GAP
        width = min(width, room)
        return QSize(
            width + (2 * components.GRID_CARD_PAD_X),
            height + (2 * components.GRID_CARD_PAD_Y) + components.GRID_CARD_POINT,
        )

    def show_for(self, view, rect: QRect, rows: list) -> None:
        "Place the card against `rect`, a tile in `view`'s viewport coordinates."
        self.rows = rows
        size = self.measure()
        self.resize(size)

        viewport = view.viewport()
        top_left = viewport.mapToGlobal(rect.topLeft())
        centre_x = top_left.x() + (rect.width() // 2)
        screen = view.screen()
        area = screen.availableGeometry() if screen is not None else None

        y = top_left.y() - size.height() - components.GRID_CARD_GAP
        self.below = area is not None and y < area.top()
        if self.below:
            y = top_left.y() + rect.height() + components.GRID_CARD_GAP

        x = centre_x - (size.width() // 2)
        if area is not None:
            x = max(area.left(), min(x, area.right() - size.width()))
        # The pointer keeps aiming at the tile even when the card had to be
        # pushed sideways to stay on the screen.
        room = components.GRID_CARD_RADIUS + components.GRID_CARD_POINT
        self.point_x = max(room, min(centre_x - x, size.width() - room))

        self.move(QPoint(x, y))
        self.update()
        self.show()
        self.raise_()

    # }}}

    def paintEvent(self, ev):  # noqa: N802  (matching the Qt name is the point)
        chrome = colors()
        point = components.GRID_CARD_POINT
        body = QRectF(self.rect())
        if self.below:
            body.setTop(body.top() + point)
        else:
            body.setBottom(body.bottom() - point)

        path = QPainterPath()
        radius = components.GRID_CARD_RADIUS
        path.addRoundedRect(body, radius, radius)
        nose = QPainterPath()
        tip = body.top() - point if self.below else body.bottom() + point
        nose.moveTo(self.point_x - point, body.top() if self.below else body.bottom())
        nose.lineTo(self.point_x, tip)
        nose.lineTo(self.point_x + point, body.top() if self.below else body.bottom())
        nose.closeSubpath()

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            painter.fillPath(path.united(nose), QColor(chrome.tooltip_bg))
            self.paint_text(painter, body, chrome)
        finally:
            painter.end()

    def paint_text(self, painter: QPainter, body: QRectF, chrome) -> None:
        plain, bold = self.fonts()
        strong = QColor(chrome.tooltip_fg)
        # The tooltip's own foreground, pulled toward its background: a muted
        # grey from the window would be the wrong muted against this surface.
        soft = QColor(chrome.tooltip_fg)
        soft.setAlpha(165)

        x = int(body.left()) + components.GRID_CARD_PAD_X
        y = int(body.top()) + components.GRID_CARD_PAD_Y
        room = int(body.width()) - (2 * components.GRID_CARD_PAD_X)
        for i, row in enumerate(self.rows):
            if i:
                y += components.GRID_CARD_LINE_GAP
            fm = QFontMetrics(bold if row[0][1] else plain)
            line_height = fm.height()
            # Only the first run is elided: the year and the rest are short and
            # are the part that stops being findable if they are cut.
            tail = sum(QFontMetrics(bold if b else plain).horizontalAdvance(t) for t, b, _m in row[1:])
            cursor = x
            for j, (text, is_bold, is_muted) in enumerate(row):
                font = bold if is_bold else plain
                metrics = QFontMetrics(font)
                shown = text
                if j == 0:
                    cap = room - tail
                    if metrics.horizontalAdvance(text) > cap:
                        shown = metrics.elidedText(text, Qt.TextElideMode.ElideRight, cap)
                painter.setFont(font)
                painter.setPen(soft if is_muted else strong)
                painter.drawText(QRect(cursor, y, room, line_height), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, shown)
                cursor += metrics.horizontalAdvance(shown)
            y += line_height


# }}}


# Following the pointer {{{


class TileHover(QObject):
    """
    One event filter on the grid's viewport: it owns the hovered row, the ring
    repaints and the card.

    The card waits for the pointer to rest. Sweeping across a shelf of covers
    should not fire twenty tooltips, and a ring is instant feedback enough
    while the pointer is still moving.
    """

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.row = -1
        self.card = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(components.GRID_CARD_DELAY)
        self.timer.timeout.connect(self.reveal)
        viewport = view.viewport()
        viewport.setMouseTracking(True)
        viewport.installEventFilter(self)
        bar = view.verticalScrollBar()
        if bar is not None:
            bar.valueChanged.connect(self.forget)

    def eventFilter(self, obj, ev):  # noqa: N802
        kind = ev.type()
        if kind == QEvent.Type.MouseMove:
            self.moved(ev)
        elif kind in (QEvent.Type.Leave, QEvent.Type.Hide, QEvent.Type.Wheel, QEvent.Type.MouseButtonPress):
            self.forget()
        return False

    def moved(self, ev) -> None:
        try:
            pos = ev.position().toPoint()
        except AttributeError:
            pos = ev.pos()
        index = self.view.indexAt(pos)
        row = index.row() if index.isValid() else -1
        if row == self.row:
            return
        self.set_row(row)
        self.timer.stop()
        if row >= 0:
            self.hide_card()
            self.timer.start()

    def set_row(self, row: int) -> None:
        "Move the ring. Both the row it left and the row it arrived at repaint."
        model = self.view.model()
        was, self.row = self.row, row
        delegate = self.view.itemDelegate()
        if delegate is not None:
            delegate.zen_hover_row = row
        if model is None:
            return
        for r in (was, row):
            if r >= 0:
                self.view.update(model.index(r, 0))

    def reveal(self) -> None:
        if self.row < 0 or not self.view.isVisible():
            return
        model = self.view.model()
        if model is None:
            return
        index = model.index(self.row, 0)
        if not index.isValid():
            return
        rows = book_lines(self.view, index)
        if not rows:
            return
        if self.card is None:
            self.card = HoverCard(self.view)
        self.card.show_for(self.view, self.view.visualRect(index), rows)

    def hide_card(self) -> None:
        if self.card is not None:
            self.card.hide()

    def forget(self) -> None:
        self.timer.stop()
        self.hide_card()
        if self.row >= 0:
            self.set_row(-1)


# }}}


def attach(gui) -> bool:
    "Give the grid its hover controller. Safe to call twice."
    view = getattr(gui, 'grid_view', None)
    if view is None or getattr(view, 'zen_hover', None) is not None:
        return False
    view.zen_hover = TileHover(view)
    return True


def install() -> bool:
    """
    Wrap the three delegate methods. `attach()` is separate because it needs a
    live grid view, which does not exist until the main window is built.
    """
    global _installed
    if _installed:
        return True
    from calibre.gui2.library.alternate_views import CoverDelegate

    orig_paint = CoverDelegate.paint
    orig_paint_cover = CoverDelegate.paint_cover

    def paint(self, painter, option, index):
        # paint_cover() is handed a painter and a rect, so the state it would
        # need to know whether to draw a ring is left here for it.
        self.zen_paint_state = (index.row(), option.state)
        # And then the flags are cleared, so the delegate draws no fill behind
        # the cover. Upstream's first line is a full-tile selection highlight,
        # which in this palette is the accent -- the same colour as the ring,
        # which would therefore have been invisible on a focused view. A tile
        # is an object rather than a band: it takes an outline, not a wash.
        option.state &= ~QStyle.StateFlag.State_Selected
        option.state &= ~QStyle.StateFlag.State_MouseOver
        try:
            return orig_paint(self, painter, option, index)
        finally:
            self.zen_paint_state = None

    def paint_cover(self, painter, rect, pixmap):
        ans = orig_paint_cover(self, painter, rect, pixmap)
        state = getattr(self, 'zen_paint_state', None)
        if state is None:
            return ans
        try:
            row, flags = state
            selected = bool(flags & QStyle.StateFlag.State_Selected)
            hovered = row == getattr(self, 'zen_hover_row', -1)
            draw_ring(painter, rect, selected, hovered)
        except Exception:
            # A missing ring is a smaller problem than a grid that will not
            # paint, and this runs once per visible tile.
            pass
        return ans

    @pyqtSlot(QHelpEvent, QAbstractItemView, QStyleOptionViewItem, QModelIndex, result='bool')
    def helpEvent(self, event, view, option, index):  # noqa: N802
        # True means "handled": no tooltip. The card says the same things, and
        # two of them at once would fight over the same corner of the screen.
        return True

    try:
        CoverDelegate.paint = paint
        CoverDelegate.paint_cover = paint_cover
        CoverDelegate.helpEvent = helpEvent
    except AttributeError, TypeError:
        return False
    _installed = True
    return True

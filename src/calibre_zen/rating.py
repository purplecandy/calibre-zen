#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Star ratings you click, instead of a drop-down of star characters.

calibre has one rating widget, `widgets2.RatingEditor`, and it is a QComboBox
whose items are strings of star glyphs in a special font: open the list, find
the row with the right number of stars, pick it. The scroll wheel changes it
as the pointer passes over on its way down a form, and "Not rated" is a sixth
row in the same list. It is used by the Edit metadata dialog, by custom rating
columns in both the single and the bulk editor, by the bulk editor's own
Rating field, as the book list's in-cell editor, and in the review of
downloaded metadata.

It stays a QComboBox. Every one of those callers talks to it through
`rating_value`, `currentIndex`, `setCurrentIndex` and the combo's change
signals -- the book list's delegate, the bulk dialog's generated form and
`RatingEdit`, which subclasses it -- so replacing the class would mean finding
each of them, and missing one would mean a crash in a dialog nobody opened
while testing. What is wrapped instead is how it is drawn and how it takes
input, on the class itself, so every subclass and every instance anywhere gets
it and the index underneath means what it always meant:

- five stars, painted, inside the field's own frame (the sheet's QComboBox
  rules still draw the border, the hover and the focus ring);
- the pointer previews the rating it would set, and a click sets it; a column
  that allows half stars takes the left half of a star as a half;
- a small cross at the end clears it, and so do Delete, Backspace and 0;
- the arrow keys step it, Home and End go to the ends, the digit keys work as
  they always did, and nothing opens a list;
- the wheel is left for the scroll area the field is sitting in.

Off with `CALIBRE_ZEN_RATING=0`.
"""

from calibre_zen import features

_installed = False


def enabled() -> bool:
    return features.enabled('rating')


def install() -> bool:
    "Wrap RatingEditor. Safe to call twice. Needs a QApplication."
    global _installed
    if _installed or not enabled():
        return _installed
    from qt.core import QComboBox, QKeyCombination, Qt

    from calibre.gui2.widgets2 import RatingEditor

    orig_init = RatingEditor.__init__
    orig_key_press = RatingEditor.keyPressEvent

    def __init__(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        self._zen_hover = None  # the rating under the pointer, 0-10, or None
        self._zen_clear_hover = False
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        # Wheel focus is how a combo box ends up changing as a form scrolls past it.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.currentIndexChanged.connect(self.update)

    def sizeHint(self):
        ans = QComboBox.sizeHint(self)
        ans.setWidth(natural_width(self))
        return ans

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, ev):
        paint(self)

    def mousePressEvent(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton:
            return QComboBox.mousePressEvent(self, ev)
        ev.accept()
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        pos = ev.position().toPoint()
        if self.rating_value and clear_rect(self).contains(pos):
            set_value(self, 0)
            return
        val = value_at(self, pos.x())
        if val is not None:
            set_value(self, val)

    def mouseReleaseEvent(self, ev):
        ev.accept()

    def mouseDoubleClickEvent(self, ev):
        # Two quick clicks on a star are two clicks on a star, not a list.
        self.mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        pos = ev.position().toPoint()
        hover = value_at(self, pos.x())
        on_clear = bool(self.rating_value) and clear_rect(self).contains(pos)
        if hover != self._zen_hover or on_clear != self._zen_clear_hover:
            self._zen_hover, self._zen_clear_hover = hover, on_clear
            self.update()
        ev.accept()

    def leaveEvent(self, ev):
        self._zen_hover, self._zen_clear_hover = None, False
        self.update()
        return QComboBox.leaveEvent(self, ev)

    def wheelEvent(self, ev):
        ev.ignore()

    def showPopup(self):
        # Nothing to choose from: the stars are the choice.
        pass

    def keyPressEvent(self, ev):
        k = ev.key()
        step = 1 if self.is_half_star else 2
        val = self.rating_value
        if k in (Qt.Key.Key_Left, Qt.Key.Key_Down, Qt.Key.Key_Minus):
            val -= step
        elif k in (Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Plus):
            val += step
        elif k in (Qt.Key.Key_Home, Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            val = 0
        elif k == Qt.Key.Key_End:
            val = 10
        elif k in (Qt.Key.Key_Space, Qt.Key.Key_F4) or ev.keyCombination() == QKeyCombination(Qt.KeyboardModifier.AltModifier, Qt.Key.Key_Down):
            # The keys that would have opened the list.
            ev.accept()
            return
        else:
            return orig_key_press(self, ev)
        if ev.modifiers() & ~Qt.KeyboardModifier.KeypadModifier:
            # Leave Alt+Left and friends to whoever owns them: the Edit
            # metadata dialog's Previous and Next are exactly those.
            return orig_key_press(self, ev)
        ev.accept()
        set_value(self, val)

    RatingEditor.__init__ = __init__
    RatingEditor.sizeHint = sizeHint
    RatingEditor.minimumSizeHint = minimumSizeHint
    RatingEditor.paintEvent = paintEvent
    RatingEditor.mousePressEvent = mousePressEvent
    RatingEditor.mouseReleaseEvent = mouseReleaseEvent
    RatingEditor.mouseDoubleClickEvent = mouseDoubleClickEvent
    RatingEditor.mouseMoveEvent = mouseMoveEvent
    RatingEditor.leaveEvent = leaveEvent
    RatingEditor.wheelEvent = wheelEvent
    RatingEditor.showPopup = showPopup
    RatingEditor.keyPressEvent = keyPressEvent
    wrap_delegate()
    _installed = True
    return True


def wrap_delegate() -> None:
    """
    The book list's rating cells, drawn with the same stars as the editor.

    `RatingDelegate` draws a rating as text in calibre's star font, whose
    half star is a different glyph from its whole one. It is also what opens
    the editor above, so a cell that says four stars in one drawing and the
    editor that opens over it in another would be the first thing anyone
    noticed. An unrated book's cell stays empty, as it always was.
    """
    from qt.core import QApplication, QColor, QPainter, QPalette, QSize, QStyle, QStyleOptionViewItem, Qt

    from calibre.gui2.library.delegates import RatingDelegate
    from calibre_zen.theme.tokens import components

    orig_size_hint = RatingDelegate.sizeHint

    def geometry(option):
        s = max(8, min(components.RATING_STAR_CELL, option.rect.height() - 6))
        return s, components.RATING_GAP - 1

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ''
        style = opt.widget.style() if opt.widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        val = cell_value(index.data(Qt.ItemDataRole.DisplayRole))
        if not val:
            return
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        fill = QColor(option.palette.color(QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text))
        # The empty stars are the filled colour, faded, rather than a chrome
        # colour: a selected row's fill is the accent, and it has to read there.
        empty = QColor(fill)
        empty.setAlphaF(0.35)
        s, gap = geometry(option)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_stars(painter, option.rect.left() + components.RATING_CELL_PAD, option.rect.center().y() + 0.5, s, gap, val, fill, empty)
        painter.restore()

    def sizeHint(self, option, index):
        ans = orig_size_hint(self, option, index)
        s, gap = geometry(option) if option.rect.height() > 0 else (components.RATING_STAR_CELL, components.RATING_GAP - 1)
        return QSize(2 * components.RATING_CELL_PAD + 5 * s + 4 * gap, ans.height())

    RatingDelegate.paint = paint
    RatingDelegate.sizeHint = sizeHint


def cell_value(val) -> int:
    "What a rating cell holds, as 0-10. The model hands over ints, floats or None."
    try:
        return max(0, min(10, round(float(val or 0))))
    except TypeError, ValueError:
        return 0


# Geometry {{{


def metrics(w) -> tuple:
    """
    (pad, star, gap) for this editor. In a table cell it takes the cell's own
    numbers, so the stars do not jump when the editor opens over them.
    """
    from calibre_zen.theme.tokens import components

    if in_item_view(w):
        return components.RATING_CELL_PAD, max(8, min(components.RATING_STAR_CELL, w.height() - 6)), components.RATING_GAP - 1
    return components.RATING_PAD, max(8, min(components.RATING_STAR, w.height() - 10)), components.RATING_GAP


def pitch(w) -> int:
    _pad, star, gap = metrics(w)
    return star + gap


def natural_width(w) -> int:
    from calibre_zen.theme.tokens import components

    stars = 5 * components.RATING_STAR + 4 * components.RATING_GAP
    return 2 * components.RATING_PAD + stars + components.RATING_GAP + clear_box()


def clear_box() -> int:
    from calibre_zen.theme.tokens import components

    return components.RATING_CLEAR + 8


def star_rect(w, i):
    from qt.core import QRectF

    pad, star, _gap = metrics(w)
    return QRectF(pad + i * pitch(w), (w.height() - star) / 2, star, star)


def clear_rect(w):
    from qt.core import QRect

    box = clear_box()
    pad, _star, _gap = metrics(w)
    return QRect(pad + 5 * pitch(w), (w.height() - box) // 2, box, box)


def value_at(w, x: float):
    """
    The rating, 1 to 10, a click at `x` would set; None outside the stars.

    The gap after a star belongs to that star, so there is no dead strip
    between two of them where the pointer sets nothing.
    """
    pad, _star, gap = metrics(w)
    rel = x - pad + gap / 2
    if rel < 0:
        return None
    i, within = divmod(rel, pitch(w))
    if i >= 5:
        return None
    i = int(i)
    if w.is_half_star and within < pitch(w) / 2:
        return 2 * i + 1
    return 2 * i + 2


def set_value(w, val: int) -> None:
    val = max(0, min(10, int(val)))
    if not w.is_half_star:
        val = (val + 1) // 2 * 2
    if val != w.rating_value:
        w.rating_value = val
    w.update()


# }}}

# Painting {{{


def star_path(rect):
    "A five-point star filling `rect`, point up."
    import math

    from qt.core import QPainterPath, QPointF

    cx, cy = rect.center().x(), rect.center().y() + rect.height() * 0.04
    outer = rect.width() / 2
    inner = outer * 0.5
    path = QPainterPath()
    for n in range(10):
        r = outer if n % 2 == 0 else inner
        a = -math.pi / 2 + n * math.pi / 5
        pt = QPointF(cx + r * math.cos(a), cy + r * math.sin(a))
        if n == 0:
            path.moveTo(pt)
        else:
            path.lineTo(pt)
    path.closeSubpath()
    return path


def in_item_view(w) -> bool:
    "An editor open in a table cell draws on the cell, without a field's frame."
    from qt.core import QAbstractItemView

    parent = w.parentWidget()
    return parent is not None and isinstance(parent.parentWidget(), QAbstractItemView)


def draw_stars(p, x: float, cy: float, size: float, gap: float, value: int, fill, empty, show_empty: bool = True) -> None:
    """
    Five stars from `x`, centred on `cy`, `value` halves of them filled.
    Shared by the editor and the book list's cells, so the two cannot drift.
    """
    from qt.core import QPen, QRectF, Qt

    from calibre_zen.theme.tokens import components

    stroke = components.RATING_STROKE
    for i in range(5):
        rect = QRectF(x + i * (size + gap), cy - size / 2, size, size)
        path = star_path(rect.adjusted(stroke / 2, stroke / 2, -stroke / 2, -stroke / 2))
        filled = min(2, max(0, value - 2 * i))  # halves of this star
        if filled < 2 and show_empty:
            p.setPen(QPen(empty, stroke, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        if filled:
            p.save()
            if filled == 1:
                p.setClipRect(QRectF(rect.left(), rect.top(), rect.width() / 2, rect.height()))
            # Stroked in its own colour as well as filled, which is what
            # rounds the points to match the outline beside it.
            p.setPen(QPen(fill, stroke, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(fill)
            p.drawPath(path)
            p.restore()


def paint(w) -> None:
    from qt.core import QColor, QIcon, QPainter, QPen, QRectF, QStyle, QStyleOptionComboBox, QStylePainter, Qt

    from calibre_zen.theme import rewrite
    from calibre_zen.theme.tokens import components

    chrome = rewrite.chrome()
    p = QStylePainter(w)
    if in_item_view(w):
        p.fillRect(w.rect(), w.palette().base())
    else:
        # The field's frame from the sheet -- border, hover, focus ring --
        # with no text, no icon and no arrow drawn into it.
        opt = QStyleOptionComboBox()
        w.initStyleOption(opt)
        opt.subControls = QStyle.SubControl.SC_ComboBoxFrame
        # Only as wide as the stars. A grid that stretches the widget across
        # its column -- the custom columns page does -- would otherwise get a
        # long empty field with five stars at one end of it.
        opt.rect.setWidth(min(w.width(), natural_width(w)))
        opt.currentText = ''
        opt.currentIcon = QIcon()
        p.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    enabled = w.isEnabled()
    current = w.rating_value
    hover = w._zen_hover if enabled and not w._zen_clear_hover else None
    # The pointer shows the rating a click would set, in full: the pointer
    # is there to say it is a preview.
    shown = current if hover is None else hover
    _pad, s, _gap = metrics(w)
    fill = QColor(chrome.accent if enabled else chrome.muted)
    empty = QColor(chrome.muted if enabled else chrome.border)
    draw_stars(p, star_rect(w, 0).left(), w.height() / 2, s, pitch(w) - s, shown, fill, empty)

    if current and enabled and (w.underMouse() or w.hasFocus()):
        c = components.RATING_CLEAR
        cross = QRectF(0, 0, c, c)
        cross.moveCenter(QRectF(clear_rect(w)).center())
        colour = QColor(chrome.accent if w._zen_clear_hover else chrome.muted)
        p.setPen(QPen(colour, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(cross.topLeft(), cross.bottomRight())
        p.drawLine(cross.topRight(), cross.bottomLeft())
    p.end()


# }}}

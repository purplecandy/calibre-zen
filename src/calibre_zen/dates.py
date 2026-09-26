#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The calendar a date field opens, drawn in the theme.

Every date field in calibre -- the Edit metadata dialog's Date and Published,
custom date columns in the single and the bulk editor, the bulk editor's own
dates, and the book list's date cells -- is a `widgets2.DateTimeEdit`, and
each one builds its popup calendar the same way: a `widgets2.CalendarWidget`,
calibre's thin subclass of QCalendarWidget, handed to `setCalendarWidget`.

Stock, that calendar paints itself from the palette's Highlight role: a solid
accent bar across the top with the month in bold white, weekends in red, and a
table of square cells with the selected day as a filled block. None of it
reads any token, and the popup is a square window under rounded menus.

Two wraps, both on calibre's classes:

`DateTimeEdit.__init__`
    After calibre builds the calendar, `decorate()` names it for the sheet
    (16-dates.qss dresses the header, the chevrons and the frame like a menu),
    quiets the weekday names and the weekends, and adds a footer with Today
    and Clear -- what a reader otherwise finds only in the field's context
    menu or behind the = and - keys.

`CalendarWidget.paintCell`
    The days themselves: a rounded cell for the selected day in the accent, a
    ring for today, a wash under the pointer, and the days of the months
    either side in the muted ink.

A date field that is not calibre's -- a plain QDateTimeEdit somewhere in a
plugin -- gets the sheet's arrow and nothing else.

Off with `CALIBRE_ZEN_DATES=0`.
"""

from qt.core import QEvent, QObject

from calibre_zen import features

_installed = False


def enabled() -> bool:
    return features.enabled('dates')


def install() -> bool:
    "Wrap calibre's date field and its calendar. Safe to call twice. Needs a QApplication."
    global _installed
    if _installed or not enabled():
        return _installed
    from qt.core import QCalendarWidget

    from calibre.gui2.widgets2 import CalendarWidget, DateTimeEdit

    orig_init = DateTimeEdit.__init__

    def __init__(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        cw = getattr(self, 'cw', None)
        if cw is not None:
            try:
                decorate(cw, self)
            except Exception:
                # The calendar still works undressed; a date field that fails
                # to build does not.
                import traceback

                traceback.print_exc()

    def sizeHint(self):
        return with_footer(self, QCalendarWidget.sizeHint(self))

    def minimumSizeHint(self):
        return with_footer(self, QCalendarWidget.minimumSizeHint(self))

    DateTimeEdit.__init__ = __init__
    CalendarWidget.paintCell = paint_cell
    CalendarWidget.sizeHint = sizeHint
    CalendarWidget.minimumSizeHint = minimumSizeHint
    _installed = True
    return True


def decorate(cw, edit) -> None:
    from qt.core import QAbstractItemView, QBrush, QCalendarWidget, QColor, QHBoxLayout, QPalette, Qt, QTextCharFormat, QToolButton, QWidget

    from calibre_zen.theme import rewrite

    cw.setObjectName('zenCalendar')
    cw.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    cw.setGridVisible(False)
    cw.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
    cw.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)

    # The weekday names: small and muted, on no fill of their own. Every day
    # gets the same format, which is what takes the red off the weekend --
    # the header takes its colour from the weekday's format.
    chrome = rewrite.chrome()
    header = QTextCharFormat()
    header.setForeground(QBrush(QColor(chrome.muted)))
    header.setBackground(QBrush(Qt.GlobalColor.transparent))
    header.setFontWeight(400)
    cw.setHeaderTextFormat(header)
    for day in Qt.DayOfWeek:
        cw.setWeekdayTextFormat(day, header)

    # Stock, the navigation bar fills itself with Highlight and writes its
    # buttons in HighlightedText. The sheet can colour the buttons, but only
    # this can stop the fill.
    nav = cw.findChild(QWidget, 'qt_calendar_navigationbar')
    if nav is not None:
        nav.setAutoFillBackground(False)
        pal = nav.palette()
        pal.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.transparent)
        nav.setPalette(pal)
        layout = nav.layout()
        if layout is not None:
            layout.setContentsMargins(6, 6, 6, 2)

    view = cw.findChild(QAbstractItemView, 'qt_calendar_calendarview')
    if view is not None:
        view.setMouseTracking(True)
        vp = view.viewport()
        vp.setMouseTracking(True)
        vp.setAutoFillBackground(False)
        tracker = HoverTracker(cw, vp)
        vp.installEventFilter(tracker)
        cw._zen_hover = tracker

    footer = QWidget(cw)
    footer.setObjectName('zenCalendarFooter')
    footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    fl = QHBoxLayout(footer)
    fl.setContentsMargins(6, 4, 6, 6)
    today = QToolButton(footer)
    today.setObjectName('zenCalendarToday')
    today.setText(_('Today'))
    today.setAutoRaise(True)
    today.clicked.connect(lambda: finish(cw, edit, edit.today_date))
    clear = QToolButton(footer)
    clear.setObjectName('zenCalendarClear')
    clear.setText(_('Clear'))
    clear.setAutoRaise(True)
    clear.clicked.connect(lambda: finish(cw, edit, edit.clear_date))
    fl.addWidget(clear)
    fl.addStretch()
    fl.addWidget(today)
    lay = cw.layout()
    if lay is not None:
        lay.addWidget(footer)
        cw._zen_footer = footer


def with_footer(cw, size):
    """
    QCalendarWidget works its size out from its own rows and navigation bar,
    not from its layout, so a footer added to that layout is not counted and
    the popup -- sized from the calendar's hint -- squeezes the last weeks out.
    """
    footer = getattr(cw, '_zen_footer', None)
    if footer is not None:
        size.setHeight(size.height() + footer.sizeHint().height())
    return size


def finish(cw, edit, action) -> None:
    "Run a footer action on the field, then close the popup it is sitting in."
    action()
    win = cw.window()
    # Before its first showing the calendar is still the field's child, and
    # its window is the dialog. Only the popup is ours to close.
    if win is not edit.window():
        win.hide()
    edit.setFocus()


class HoverTracker(QObject):
    "Where the pointer is over the days, for paint_cell. None when it is not over them."

    def __init__(self, cw, viewport):
        super().__init__(cw)
        self.viewport = viewport
        self.pos = None

    def eventFilter(self, obj, ev):  # noqa: N802  (matching the Qt name is the point)
        t = ev.type()
        if t == QEvent.Type.MouseMove:
            self.pos = ev.position().toPoint()
            self.viewport.update()
        elif t in (QEvent.Type.Leave, QEvent.Type.Hide):
            self.pos = None
            self.viewport.update()
        return False


def paint_cell(self, painter, rect, date) -> None:
    from qt.core import QColor, QDate, QFont, QPainter, QPen, QRectF, Qt

    from calibre_zen.theme import rewrite
    from calibre_zen.theme.tokens import components

    chrome = rewrite.chrome()
    in_month = date.month() == self.monthShown() and date.year() == self.yearShown()
    selected = date == self.selectedDate()
    today = date == QDate.currentDate()
    allowed = self.minimumDate() <= date <= self.maximumDate()
    tracker = getattr(self, '_zen_hover', None)
    hovered = allowed and tracker is not None and tracker.pos is not None and rect.contains(tracker.pos)

    side = min(rect.width(), rect.height()) - 2
    cell = QRectF(0, 0, side, side)
    cell.moveCenter(QRectF(rect).center())
    radius = components.RADIUS_CONTROL

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if selected:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(chrome.accent_hover if hovered else chrome.accent))
        painter.drawRoundedRect(cell, radius, radius)
    elif hovered:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(chrome.surface_hover))
        painter.drawRoundedRect(cell, radius, radius)
    if today and not selected:
        painter.setPen(QPen(QColor(chrome.border_strong), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(cell.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)

    if selected:
        ink = QColor(chrome.accent_text)
    elif not allowed:
        ink = QColor(chrome.border_strong)
    elif not in_month:
        ink = QColor(chrome.muted)
    else:
        ink = self.palette().color(self.foregroundRole())
    font = QFont(self.font())
    if today:
        font.setWeight(QFont.Weight.DemiBold)
    painter.setFont(font)
    painter.setPen(ink)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(date.day()))
    painter.restore()

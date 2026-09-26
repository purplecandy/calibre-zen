#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The lists that drop down under a field, dressed like the menus.

Two kinds, one look: a menu's surface, frame and radius around rows with a
menu item's height and a rounded selection, all from the same tokens.

**A combo box's own list.** Fusion hands QComboBox a `QComboMenuDelegate`,
which draws each row as a menu item: the sheet's `::item` rules never reach
it, so rows come out 24px tall with a square block for the selection, inside
the container's square frame. When a combo box is polished, a combo box still
on that delegate gets a QStyledItemDelegate instead -- one that calibre gave
its own delegate keeps it -- and the container stops painting the menu panel
Fusion asks it for, leaving the list's own rounded frame (04-fields.qss) as
the edge.

**calibre's autocomplete list.** Publisher, Series, Tags and every other field
that completes from the library open `complete2.Completer`: a QListView with
the Popup window flag, parented to the field. When the field is a combo box --
`EditWithComplete`, which is most of them -- none of the application sheet
reaches that list. Measured, not guessed: a QListView made a Popup under a
QComboBox comes back in the platform's "Sans Serif" with 16px rows and
alternating stripes, even after an explicit re-polish, and the same list under
a line edit is styled normally. So each Completer carries a sheet of its own,
`qss/local/completer.qss` plus the app's scrollbar rules, rebuilt only when the
palette or the scheme changes. Qt gives a scroll area's sheet background to its
viewport, a square that paints over the frame's rounded corners, and ignores
its padding; so the viewport is left unfilled and inset, and the rounded
surface and border are painted under it by `Surface`.

`Completer.popup` sizes the window from `sizeHintForRow(0)` plus a fixed 6px,
which was right for 16px rows and no padding. The wrap lets it place the list,
then corrects the height for the padding and frame, keeps the list LIST_GAP
clear of the field, and if calibre put it above the field for want of room
below, keeps it above.
"""

from qt.core import QAbstractItemView, QComboBox, QEvent, QFrame, QObject

from calibre_zen.theme import generate

POLISH = QEvent.Type.Polish
SHOW = QEvent.Type.Show
CONTAINER = 'QComboBoxPrivateContainer'

_installed = False
_filter = None
_sheets = {}  # name -> (palette key, sheet)


def install() -> bool:
    "Wrap Completer and watch for combo boxes. Safe to call twice. Needs a QApplication."
    global _installed, _filter
    if _installed:
        return True
    from calibre.gui2 import qapplication_or_fail
    from calibre.gui2.complete2 import Completer

    app = qapplication_or_fail()
    _filter = ComboWatch(app)
    app.installEventFilter(_filter)

    orig_init = Completer.__init__
    orig_popup = Completer.popup

    def __init__(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        self.setObjectName('zenCompleter')
        self.setAlternatingRowColors(False)
        dress(self)

    def popup(self, select_first=True):
        dress(self)
        orig_popup(self, select_first=select_first)
        try:
            fit(self)
        except Exception:
            # A list a few pixels off is better than no list.
            pass

    Completer.__init__ = __init__
    Completer.popup = popup
    _installed = True
    return True


def sheet(name: str) -> str:
    """
    A dropping list's own sheet, `qss/local/<name>.qss` plus the app's
    scrollbar rules, for the palette and scheme in use now.
    """
    from calibre.gui2 import qapplication_or_fail
    from calibre_zen.theme.tokens import schemes

    app = qapplication_or_fail()
    pal = app.palette()
    is_dark = bool(app.property('is_dark_theme'))
    key = (pal.cacheKey(), is_dark, schemes.active().name)
    cached = _sheets.get(name)
    if cached is None or cached[0] != key:
        m = generate.mapping(pal, is_dark)
        cached = _sheets[name] = (key, generate.render(f'local/{name}.qss', m) + '\n' + generate.render('app/05-scrollbars.qss', m))
    return cached[1]


def dress(view) -> None:
    from qt.core import QFrame

    from calibre_zen.theme.tokens import components

    text = sheet('completer')
    if view.styleSheet() != text:
        view.setStyleSheet(text)
    if getattr(view, '_zen_surface', None) is None:
        # Qt gives a scroll area's sheet background to its viewport, a
        # square inset one pixel inside the border, which paints over the
        # frame's rounded corners -- and it ignores the sheet's padding. So
        # the viewport is left unfilled and inset by the padding, and the
        # rounded surface and its border are painted here, under it.
        view.setFrameShape(QFrame.Shape.NoFrame)
        view.viewport().setAutoFillBackground(False)
        pad = components.LIST_PAD + 1
        view.setViewportMargins(pad, pad, pad, pad)
        view._zen_surface = Surface(view)
        view.installEventFilter(view._zen_surface)


class ComboWatch(QObject):
    """
    The application-wide filter: a combo box being polished gets a delegate
    the sheet can style. Every other event costs one comparison.
    """

    def eventFilter(self, obj, ev):  # noqa: N802  (matching the Qt name is the point)
        t = ev.type()
        if t == POLISH and isinstance(obj, QComboBox):
            try:
                restyle_combo(obj)
            except Exception:
                # A square list is never worth a combo box failing to polish.
                pass
        elif t == SHOW and isinstance(obj, QFrame) and obj.metaObject().className() == CONTAINER:
            # A list opening after the theme changed: its sheet was built for
            # the old palette -- a no-op when nothing has changed. And the
            # list's row positions were worked out before its sheet gave the
            # rows their padding: the popup is sized for 26px rows while the
            # rows still sit 16px apart until something lays them out again.
            try:
                dress_container(obj)
                view = obj.findChild(QAbstractItemView)
                if view is not None:
                    view.doItemsLayout()
            except Exception:
                pass
        return False


def restyle_combo(combo) -> None:
    from qt.core import QStyledItemDelegate

    delegate = combo.itemDelegate()
    if delegate is not None and delegate.metaObject().className() == 'QComboMenuDelegate':
        combo.setItemDelegate(QStyledItemDelegate(combo))
    view = combo.view()
    container = view.parentWidget() if view is not None else None
    if isinstance(container, QFrame) and container.metaObject().className() == CONTAINER:
        dress_container(container)


def dress_container(container) -> None:
    # Fusion says a combo box's list is a menu, so the container paints a
    # menu panel -- a white fill and a grey square border -- around the list's
    # rounded frame. The app sheet cannot name the container (its rule never
    # matches); a sheet of its own can, and then has to carry the list's look
    # as well. See qss/local/combo-list.qss.
    text = sheet('combo-list')
    if container.styleSheet() != text:
        container.setStyleSheet(text)


class Surface(QObject):
    "Paints the list's rounded surface and border before Qt paints the rest."

    def eventFilter(self, obj, ev):  # noqa: N802  (matching the Qt name is the point)
        if ev.type() == QEvent.Type.Paint and obj is self.parent():
            try:
                paint_surface(obj)
            except Exception:
                pass
        return False


def paint_surface(view) -> None:
    from qt.core import QColor, QPainter, QPen, QRectF

    from calibre_zen.theme import rewrite
    from calibre_zen.theme.tokens import components

    chrome = rewrite.chrome()
    p = QPainter(view)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(chrome.border_strong), 1))
    p.setBrush(QColor(chrome.menu_bg))
    r = components.RADIUS_PANEL
    p.drawRoundedRect(QRectF(view.rect()).adjusted(0.5, 0.5, -0.5, -0.5), r, r)
    p.end()


def fit(view) -> None:
    from qt.core import QPoint, QRect

    from calibre_zen.theme.tokens import components

    widget = view.parent()
    model = view.model()
    if widget is None or model is None or not view.isVisible() or not model.rowCount():
        return
    rows = min(view.max_visible_items, model.rowCount())
    # What the frame and the sheet's padding take, measured off the widget
    # rather than parsed back out of the sheet.
    chrome = view.height() - view.viewport().height()
    height = rows * view.sizeHintForRow(0) + chrome
    field_top = widget.mapToGlobal(QPoint(0, 0)).y()
    field_bottom = field_top + widget.height()
    geom = QRect(view.geometry())
    screen = widget.screen().availableGeometry()
    if geom.top() >= field_top:
        geom.moveTop(field_bottom + components.LIST_GAP)
        geom.setHeight(min(height, screen.bottom() - geom.top()))
    else:
        geom.setHeight(min(height, field_top - components.LIST_GAP - screen.top()))
        geom.moveBottom(field_top - components.LIST_GAP)
    view.setGeometry(geom)

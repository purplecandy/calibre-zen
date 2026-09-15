#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
A rounded popup needs a rounded window, not just a rounded border.

`border-radius` on a menu, a tooltip or a combo box's list rounds what the
sheet *draws*. The window it is drawn into is still a rectangle, and Qt fills
that rectangle with the widget's background before the sheet paints over it,
so each corner keeps a square block and the rounding never shows.

Measured rather than assumed, with the dark scheme installed:

    menu             every pixel of the grab, (0, 0) included, is #171717
                     opaque -- the rounding is drawn and then filled behind
    combo box list   the container comes back #0e0e0e against a #171717 list,
                     so the square is a different colour from the thing on
                     top of it, which is why that one reads as a defect
                     rather than as a square menu

`WA_TranslucentBackground` is the fix: Qt stops pre-filling the rectangle, so
whatever the sheet does not paint stays at alpha 0 and the corner shows what
is behind the window. It has to be set before the platform window is created,
which means at `Polish` -- by the time anyone holds a reference to a menu it
is usually too late.

Nothing here knows any of those widgets by name. The rule is "a top-level
popup", which is what a menu, a tooltip and a combo box's container have in
common and what every other rounded thing in the sheet -- a group box, a list,
a tab pane -- does not: those are inside a window someone else has already
painted, so their corners were never a problem.

The hook is an application-wide event filter because it is the only one that
sees all three: a combo box's container and a line edit's context menu are
built in C++, so wrapping `QMenu.__init__` -- which does work, and is what
`theme/variants.py` does to QPushButton -- would leave both of those square.
Every event that is not a Polish costs one integer comparison.

`CALIBRE_ZEN_ROUND_POPUPS=0` turns it off. This is the only thing the overlay
does to a native window rather than to a painted one, so it gets its own way
back: a compositor that disagrees should cost the corners, not the theme.
"""

import os

from qt.core import QEvent, QObject, Qt, QWidget

_installed = False
_filter = None

# Qt::Popup is a menu or a combo box's list; Qt::ToolTip is a tooltip. Both are
# windows of their own that we have given a radius. Everything else that floats
# -- a dialog, a splash screen -- is square and stays that way.
POPUP_TYPES = frozenset({int(Qt.WindowType.Popup), int(Qt.WindowType.ToolTip)})
POLISH = QEvent.Type.Polish
TRANSLUCENT = Qt.WidgetAttribute.WA_TranslucentBackground


def enabled() -> bool:
    return os.environ.get('CALIBRE_ZEN_ROUND_POPUPS', '1') not in ('0', 'false', 'no', 'off')


def is_popup(w: QWidget) -> bool:
    "A window of its own, of the kind that floats over the one below it."
    if not w.isWindow():
        return False
    return int(w.windowFlags() & Qt.WindowType.WindowType_Mask) in POPUP_TYPES


def shape(w: QWidget) -> bool:
    """
    Let this window's corners be whatever the sheet leaves unpainted.

    Returns whether the attribute is now set, which is not the same as having
    set it: a widget that already had it counts, and one that refuses does not.
    """
    if not w.testAttribute(TRANSLUCENT):
        w.setAttribute(TRANSLUCENT, True)
    return w.testAttribute(TRANSLUCENT)


class PopupShaper(QObject):
    """
    The application-wide filter. Kept as small as it can be: this runs for
    every event delivered anywhere in the application, so the first line has
    to reject all of them but one kind.
    """

    def eventFilter(self, obj, ev):  # noqa: N802  (matching the Qt name is the point)
        if ev.type() == POLISH and isinstance(obj, QWidget) and is_popup(obj):
            try:
                shape(obj)
            except Exception:
                # A corner is never worth a widget failing to polish.
                pass
        return False


def install() -> bool:
    """
    Watch for popups being polished. Call once, with a QApplication alive.

    The filter is parented to the application so Qt keeps it: an event filter
    that Python collects is removed from under Qt without it noticing.
    """
    global _installed, _filter
    if _installed or not enabled():
        return _installed
    from calibre.gui2 import qapplication_or_fail

    app = qapplication_or_fail()
    _filter = PopupShaper(app)
    app.installEventFilter(_filter)
    _installed = True
    return True

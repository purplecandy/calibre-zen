#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Which half of a split button the pointer is on.

A `MenuButtonPopup` tool button is two targets wearing one skin: the icon runs
the action, the strip on the right opens the menu. calibre's toolbar mixes
those with `InstantPopup` buttons, which are one target that opens a menu, and
draws both with the same chevron -- so the only way to find out which kind you
were pointing at was to click it and see what happened.

`02-buttons.qss` draws a seam down a split button so the two kinds can be told
apart at rest. This is the other half of that: which side of the seam is live.

Qt does not answer the question. A hovered tool button reports
`activeSubControls = SC_ToolButton` whichever half the pointer is over --
measured, not assumed, with real hover events against an offscreen button --
and `QStyleOptionToolButton` only names `SC_ToolButtonMenu` once the menu half
is *pressed*. So `QToolButton::menu-button:hover` fires for the whole button
and lights the strip when the pointer is nowhere near it, which is the exact
ambiguity the seam is there to remove.

What this does instead: on a hover move, ask the style for the menu strip's
rectangle -- so the answer follows the sheet's own `width`, not a number
repeated here -- and record the half in a dynamic property the sheet reads.
Re-polishing is what makes a property-based rule take effect, so it is done
only when the half actually changes, which is once per crossing of the seam
rather than once per mouse move.

Installed on the buttons calibre's two toolbar classes build, rather than
through an application-wide event filter: hover moves are the highest-volume
event there is, and the buttons that need this are all made in one place.

`CALIBRE_ZEN_SPLIT=0` leaves the seam and hands the hover back to Qt, which
lights the whole button as one shape.
"""

from qt.core import QEvent, QObject, QStyle, QStyleOptionToolButton, QToolButton

from calibre_zen import features

# The name the stylesheet selects on. 'action' when the pointer is on the icon,
# 'menu' when it is on the strip, absent when the button is not hovered at all.
PROPERTY = 'zenSplit'

# HoverLeave alone is not enough: a button that is hidden or disabled under the
# pointer never gets one, and would keep its last half forever.
ENTER = frozenset({QEvent.Type.HoverEnter, QEvent.Type.HoverMove})
LEAVE = frozenset({QEvent.Type.HoverLeave, QEvent.Type.Leave, QEvent.Type.Hide, QEvent.Type.FocusOut})

_installed = False
_tracker = None


def enabled() -> bool:
    return features.enabled('splits')


def is_split(widget) -> bool:
    return isinstance(widget, QToolButton) and widget.popupMode() == QToolButton.ToolButtonPopupMode.MenuButtonPopup


def menu_rect(button):
    "Where the sheet put the menu strip, asked of the style rather than assumed."
    option = QStyleOptionToolButton()
    button.initStyleOption(option)
    style = button.style()
    if style is None:
        return None
    rect = style.subControlRect(QStyle.ComplexControl.CC_ToolButton, option, QStyle.SubControl.SC_ToolButtonMenu, button)
    return rect if rect.isValid() and not rect.isEmpty() else None


def mark(button, half: str) -> None:
    "Record the half, and re-polish only if it changed."
    if button.property(PROPERTY) == half:
        return
    button.setProperty(PROPERTY, half)
    style = button.style()
    if style is not None:
        style.unpolish(button)
        style.polish(button)
    button.update()


class SplitTracker(QObject):
    "One instance, filtering every split button it has been attached to."

    def eventFilter(self, obj, event):  # noqa: N802  (matching the Qt name is the point)
        try:
            kind = event.type()
            if kind in ENTER:
                rect = menu_rect(obj)
                mark(obj, 'menu' if rect is not None and rect.contains(event.position().toPoint()) else 'action')
            elif kind in LEAVE:
                mark(obj, '')
        except Exception:
            # A hover that raises must not eat the event; the worst case is a
            # button that lights as one shape, which is where we started.
            pass
        return False


def watch(widget) -> bool:
    "Track this button's halves. Safe to call twice on the same button."
    if _tracker is None or not is_split(widget) or widget.property(PROPERTY) is not None:
        return False
    widget.setProperty(PROPERTY, '')
    widget.installEventFilter(_tracker)
    return True


def install() -> bool:
    """
    Wrap the two places calibre configures a toolbar button.

    Both `ToolBar` and `SearchToolBar` have a `setup_tool_button` that is
    handed every button their bar builds and returns the widget -- which makes
    them the one place a split button can be recognised without watching the
    whole application.
    """
    global _installed, _tracker
    if _installed or not enabled():
        return _installed
    from calibre.gui2.bars import SearchToolBar, ToolBar

    _tracker = SplitTracker()

    def wrap(cls):
        orig = cls.setup_tool_button

        def setup_tool_button(self, bar, ac, menu_mode=None):
            ans = orig(self, bar, ac, menu_mode)
            watch(ans)
            return ans

        cls.setup_tool_button = setup_tool_button

    try:
        wrap(ToolBar)
        wrap(SearchToolBar)
    except AttributeError, TypeError:
        _tracker = None
        return False
    _installed = True
    return True

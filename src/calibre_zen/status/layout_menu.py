#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The Layout button's popup, as a menu.

calibre's `LayoutMenu` is a hand-painted strip of seven tiles -- a name, a
64px icon drawn bright or dull, and a bold Show or Hide under it -- floated
over the window at the status bar's height. None of that goes through the
style: it is `QPainter` on a `QWidget`, so the sheet cannot reach it, and next
to a status bar of line glyphs it is the one thing in the window drawn to a
different scale.

The same seven switches as a `QMenu`: the panel's name, its glyph, and a tick
while it is showing. A menu is already everything this needs to be -- rounded,
palette-coloured, keyboard-navigable, dismissed by a click outside -- and it
is what the reader's hand expects from a button that opens a list.

One wrap, no upstream file edited. `LayoutMenu.toggle_visibility` is what the
Layout button's `clicked` is connected to (`init.py:700`); ours pops the menu
above the button instead. Choosing an entry does what the tile did:
`button.click()` on the layout toggle it stands for, so the showing, the
preference and the toggle's own state are all still calibre's.
"""

from qt.core import QMenu, QPoint

_installed = False


def build_menu(buttons, parent=None) -> QMenu:
    """
    A menu for a set of layout toggle buttons.

    Each toggle carries its own label, icon and checked state, and `click()`
    on it is the whole of toggling that panel -- which is what the tile did.
    The tooltip is the toggle's, which names the shortcut.
    """
    menu = QMenu(parent)
    menu.setObjectName('zenLayoutMenu')
    menu.setToolTipsVisible(True)
    for button in buttons:
        action = menu.addAction(button.icon(), getattr(button, 'label', None) or button.text())
        action.setCheckable(True)
        action.setChecked(button.isChecked())
        action.setToolTip(button.toolTip())
        action.setEnabled(button.isEnabled())
        action.triggered.connect(lambda _checked=False, b=button: b.click())
    return menu


def popup_for(gui) -> QMenu | None:
    "The menu for this window's toggles, rebuilt each time so the ticks are current."
    buttons = getattr(gui, 'layout_buttons', None)
    if not buttons:
        return None
    old = getattr(gui, 'zen_layout_menu', None)
    if old is not None:
        old.deleteLater()
    menu = gui.zen_layout_menu = build_menu(buttons, gui)
    return menu


def show_above(menu: QMenu, anchor) -> None:
    "Pop the menu with its bottom edge on the anchor's top edge, like the strip it replaces."
    top_left = anchor.mapToGlobal(QPoint(0, 0))
    height = menu.sizeHint().height()
    menu.popup(QPoint(top_left.x(), top_left.y() - height))


def install() -> bool:
    "Wrap LayoutMenu.toggle_visibility. Safe to call twice."
    global _installed
    if _installed:
        return True
    from calibre.gui2.layout_menu import LayoutMenu

    orig_toggle = LayoutMenu.toggle_visibility

    def toggle_visibility(self):
        gui = self.parent()
        anchor = getattr(gui, 'layout_button', None)
        menu = popup_for(gui) if gui is not None else None
        if menu is None or anchor is None:
            return orig_toggle(self)
        if self.isVisible():
            self.hide()
        show_above(menu, anchor)

    LayoutMenu.toggle_visibility = toggle_visibility
    _installed = True
    return True

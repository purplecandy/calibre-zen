#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The centre, rearranged: a preview above the list, and a strip between them.

`CentralContainer` treats the centre as one opaque widget. It is handed in
exactly once -- `central.py:423`, `initialize_with_gui(gui, book_list_widget)`,
where the argument is `gui.stack` -- and everything the container ever does to
it afterwards is reparent it, `setVisible` it and `setGeometry` it. It never
calls a method on it and never reads its size hints. So passing a wrapper in
place of `gui.stack` is the whole structural change, and `gui.stack` keeps its
identity, which is what `ui.py:1050` and `ui.py:1192` still address by index.

The strip holds calibre's own `SearchBar`, moved here whole. Moving it is one
`addWidget` -- everything it registered (shortcuts, actions, the saved-searches
toolbar layout) was bound at construction against the main window and does not
care where the frame ends up, and `toggle_search_bar` still hides the frame, so
Alt+Shift+F and the status-bar button keep working.

The switcher does not switch anything itself. It sets `gui.grid_view_button`'s
checked state, and calibre's `AlternateViewsButtons.toggle_view`
(`init.py:309-323`) does the rest: shows the view, un-checks the bookshelf
button, fixes the sort button's visibility and saves the preference. Same
"drive the real control, name nothing" approach as the filter panel's Sort-by
row -- the day upstream changes what switching a view means, this follows.
"""

from qt.core import QHBoxLayout, QMenu, QSplitter, Qt, QToolButton, QVBoxLayout, QWidget

from calibre.gui2 import gprefs
from calibre_zen.centre import grid
from calibre_zen.centre.preview import PreviewPane
from calibre_zen.icons import registry
from calibre_zen.theme import generate, rewrite
from calibre_zen.theme.tokens import components

SPLITTER_KEY = 'zen_centre_splitter_state'
PREVIEW_KEY = 'zen_preview_visible'


def preview_wanted() -> bool:
    "Whether the preview is shown. On unless the reader has hidden it."
    return bool(gprefs.get(PREVIEW_KEY, True))


class PreviewToggle(QToolButton):
    """
    Show or hide the preview, from the strip.

    A checkable button that says its state twice: the word Preview beside an
    eye that is open while the preview is up and struck through while it is
    not. Live, unlike the switches in the toolbar's Zen menu -- a widget can
    be hidden and shown without a restart -- and remembered in gprefs.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('zenPreviewToggle')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setText(_('Preview'))
        self.setCheckable(True)
        self.setChecked(preview_wanted())
        self.toggled.connect(self.describe)
        self.describe(self.isChecked())

    def describe(self, shown: bool) -> None:
        "The eye and the tooltip follow the state."
        icon = registry.glyph_icon('eye' if shown else 'eye-off')
        if icon is not None and not icon.isNull():
            self.setIcon(icon)
        self.setToolTip(_('Hide the preview') if shown else _('Show the preview'))


class ViewSwitcher(QToolButton):
    "Grid or Table. Bookshelf keeps its own status-bar button."

    def __init__(self, gui, parent=None):
        super().__init__(parent)
        self.setObjectName('zenViewSwitcher')
        self.gui = gui
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_ = QMenu(self)
        self.menu_.aboutToShow.connect(self.build_menu)
        self.setMenu(self.menu_)
        self.refresh()

    def grid_shown(self) -> bool:
        button = getattr(self.gui, 'grid_view_button', None)
        return bool(button is not None and button.isChecked())

    def build_menu(self) -> None:
        self.menu_.clear()
        chrome = rewrite.chrome()
        check = generate.mark_icon('check', chrome.accent)
        showing_grid = self.grid_shown()
        for label, wants_grid in ((_('Table'), False), (_('Grid'), True)):
            action = self.menu_.addAction(label)
            if wants_grid == showing_grid:
                action.setIcon(check)
            action.triggered.connect(lambda _checked=False, g=wants_grid: self.choose(g))

        # How big a grid tile is belongs with the control that chooses the
        # grid, not three screens away in Preferences. Shown in both modes so
        # it can be set before switching, disabled in Table mode so it is
        # clear which view it governs.
        self.menu_.addSeparator()
        size_menu = self.menu_.addMenu(_('Grid size'))
        size_menu.setEnabled(showing_grid)
        current = grid.density()
        for name in grid.levels():
            action = size_menu.addAction(grid.label_for(name))
            if name == current:
                action.setIcon(check)
            action.triggered.connect(lambda _checked=False, n=name: self.choose_density(n))

    def choose_density(self, name: str) -> None:
        grid.set_density(name, self.gui)

    def choose(self, wants_grid: bool) -> None:
        button = getattr(self.gui, 'grid_view_button', None)
        if button is not None and button.isChecked() != wants_grid:
            button.setChecked(wants_grid)
        self.refresh()

    def refresh(self) -> None:
        grid = self.grid_shown()
        self.setText(_('Grid') if grid else _('Table'))
        self.setIcon(generate.mark_icon('dot', rewrite.chrome().muted))


class CentreToolbar(QWidget):
    def __init__(self, gui, parent=None):
        super().__init__(parent)
        self.setObjectName('zenCentreToolbar')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)
        layout.addWidget(gui.search_bar, 1)
        self.preview_toggle = PreviewToggle(self)
        layout.addWidget(self.preview_toggle, 0)
        self.switcher = ViewSwitcher(gui, self)
        layout.addWidget(self.switcher, 0)


class ZenCentre(QWidget):
    """
    preview / strip / list, with the divide between preview and list draggable
    and remembered.
    """

    def __init__(self, gui, book_list, parent=None):
        super().__init__(parent)
        self.gui = gui
        self.book_list = book_list
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.preview = PreviewPane(gui, self)
        self.toolbar = CentreToolbar(gui, self)

        # The strip belongs to the list, not to the window, so it goes below
        # the splitter handle -- dragging the preview taller must not leave the
        # search box stranded at the top of the screen.
        lower = QWidget(self)
        lower_layout = QVBoxLayout(lower)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        lower_layout.setSpacing(0)
        lower_layout.addWidget(self.toolbar)
        lower_layout.addWidget(book_list, 1)

        self.splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.preview)
        self.splitter.addWidget(lower)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        layout.addWidget(self.splitter)

        self.restore_splitter()
        self.splitter.splitterMoved.connect(self.save_splitter)
        self.preview.setVisible(preview_wanted())
        self.toolbar.preview_toggle.toggled.connect(self.set_preview_visible)

    def set_preview_visible(self, on: bool) -> None:
        """
        Show or hide the preview, and remember the choice.

        A hidden widget drops out of a QSplitter's arithmetic, so the sizes
        are put back from the saved state when it returns -- otherwise it
        comes back at whatever height the splitter felt like. While hidden the
        pane skips its own updates (see PreviewPane.show_index), so it is
        brought up to date with the current row on the way back.
        """
        gprefs[PREVIEW_KEY] = bool(on)
        self.preview.setVisible(on)
        if on:
            self.restore_splitter()
            self.preview.refresh()

    def restore_splitter(self) -> None:
        state = gprefs.get(SPLITTER_KEY)
        if state:
            try:
                self.splitter.restoreState(bytes(bytearray(state)))
                return
            except Exception:
                pass
        self.splitter.setSizes([components.PREVIEW_HEIGHT, 10 * components.PREVIEW_HEIGHT])

    def save_splitter(self, *args) -> None:
        if self.preview.isHidden():
            # The splitter has one child; its state would say the preview is
            # nothing tall, and that is not a height to come back to.
            return
        try:
            gprefs.set(SPLITTER_KEY, bytearray(self.splitter.saveState()))
        except Exception:
            pass

    def attach(self) -> None:
        self.preview.attach()
        self.toolbar.switcher.refresh()

    def refresh_palette(self) -> None:
        "The palette changed; re-ink what we drew ourselves."
        self.preview.refresh_palette()
        self.toolbar.switcher.refresh()

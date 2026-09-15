#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The centre pane: a preview above the book list, a strip between them, and the
list itself rebuilt as a modern table.

The second piece of the overlay that is not styling, and it follows the shape
`filters/` established: calibre's widget keeps its model, its signals and its
behaviour, and the overlay changes only what is drawn and where things sit.

Seven wraps, all from outside, no upstream file edited:

`CentralContainer.initialize_with_gui`
    The centre is handed to the container exactly once, as one opaque widget
    (`central.py:423`). We hand it our wrapper around that widget instead.
    `gui.stack` keeps its identity, so everything that addresses it by index
    keeps working.

`BooksView.get_old_state` / `BooksView.write_state`
    The only two methods that name the per-library column-layout pref
    (`views.py:1001, 1127`). Pointed at a key of our own, so the overlay's
    layout persists normally and the reader's own is frozen exactly as they
    left it. On the first run the arrangement is folded into the state dict
    that `apply_state` is about to apply, which is why nothing here ever calls
    `setSectionHidden` or `moveSection` itself.

`BooksView.database_changed`
    Runs `set_delegates` -> `restore_state` -> `set_ondevice_column_visibility`
    on startup and on every library switch (`views.py:1285-1291`), so it is the
    one correct place to point the cover cache and the preview at the new
    database.

`BooksView.do_row_sizing`
    Row height is the vertical header's, not the delegate's `sizeHint`
    (`views.py:1196-1210`), and the model caches it.

`TableView.set_delegates`
    Let calibre assign its delegates, then wrap each one. Editing, sorting,
    resizing and the column-header menu are untouched -- only `paint` and
    `sizeHint` are ours.

`BooksModel.headerData`
    One string: the title column's header reads "Details".

`CoverDelegate.set_dimensions`
    Wrapped -- see grid.py. Three tile densities on top of whatever size
    calibre works out, chosen from the view switcher's menu.

Off with `CALIBRE_ZEN_CENTRE=0`, which gives back calibre's centre exactly --
the search bar back in its own strip, the book list with the reader's own
columns, no preview.

**Known gaps.** The cover grid's tile size is ours (`grid.py`) but how a tile
is drawn is still calibre's, and the reference's "Add column" pill is not built
-- calibre's column-header context menu already does that job.
"""

import os

_installed = False


def enabled() -> bool:
    return os.environ.get('CALIBRE_ZEN_CENTRE', '1') not in ('0', 'false', 'no', 'off')


def install() -> bool:
    """
    Wrap the six methods above. Safe to call twice.

    Must not run before there is a QApplication, for the same reason
    `filters.install()` must not -- importing calibre's library views pulls in
    modules that evaluate `QIcon.ic()` at import time.
    """
    global _installed
    if _installed or not enabled():
        return _installed
    from qt.core import Qt

    from calibre.gui2.central import CentralContainer
    from calibre.gui2.library.models import BooksModel
    from calibre.gui2.library.views import BooksView
    from calibre.gui2.pin_columns import TableView
    from calibre_zen.centre import grid, table
    from calibre_zen.centre.layout import ZenCentre
    from calibre_zen.theme.tokens import components

    orig_initialize = CentralContainer.initialize_with_gui
    orig_get_old_state = BooksView.get_old_state
    orig_write_state = BooksView.write_state
    orig_database_changed = BooksView.database_changed
    orig_do_row_sizing = BooksView.do_row_sizing
    orig_set_delegates = TableView.set_delegates
    orig_header_data = BooksModel.headerData

    def state_key(view) -> str:
        name = str(view.objectName())
        return '' if not name else table.STATE_KEY_PREFIX + name + ' books view state'

    def initialize_with_gui(self, gui, book_list_widget):
        try:
            centre = ZenCentre(gui, book_list_widget, self)
        except Exception:
            # Losing the wrapper costs the preview and the strip. Losing the
            # centre costs the window, so fall back to calibre's own.
            import traceback

            traceback.print_exc()
            return orig_initialize(self, gui, book_list_widget)
        gui.zen_centre = centre
        return orig_initialize(self, gui, centre)

    def get_old_state(self):
        key = state_key(self)
        db = getattr(self.model(), 'db', None)
        if not key or db is None:
            return orig_get_old_state(self)
        ans = db.new_api.pref(key)
        if ans is not None:
            return ans
        # First run with the overlay on: start from whatever layout the reader
        # already had -- letting the original run also does its gprefs-to-db
        # migration and its injected-column bookkeeping -- and fold the Details
        # arrangement into it.
        return table.arrange(orig_get_old_state(self) or self.get_default_state(), self.column_map)

    def write_state(self, state):
        key = state_key(self)
        db = getattr(self.model(), 'db', None)
        if not key or db is None:
            return orig_write_state(self, state)
        db.new_api.set_pref(key, state)

    def database_changed(self, db):
        ans = orig_database_changed(self, db)
        if not self.is_library_view:
            return ans
        try:
            from calibre.gui2.ui import get_gui

            table.cover_cache().set_database(self._model.db)
            table.setup_view(self)
            gui = get_gui()
            centre = None if gui is None else getattr(gui, 'zen_centre', None)
            if centre is not None:
                centre.attach()
        except Exception:
            import traceback

            traceback.print_exc()
        return ans

    def do_row_sizing(self):
        ans = orig_do_row_sizing(self)
        views = [self, self.pin_view] if self.is_library_view else [self]
        for view in views:
            header = view.verticalHeader()
            header.setDefaultSectionSize(max(header.minimumSectionSize(), components.TABLE_ROW_HEIGHT))
        self._model.set_row_height(self.rowHeight(0))
        return ans

    def set_delegates(self):
        ans = orig_set_delegates(self)
        column_map = getattr(self, 'column_map', None)
        if not column_map:
            return ans
        # Held on the view because setItemDelegateForColumn does not take
        # ownership -- without a Python reference they are collected and every
        # cell falls back to the plain delegate.
        kept = self._zen_delegates = []
        for column, name in enumerate(column_map):
            inner = self.itemDelegateForColumn(column) or self.itemDelegate()
            if isinstance(inner, table.ZenCellDelegate):
                continue
            wrapper = table.ZenCellDelegate(inner, self, name == table.DETAILS_COLUMN)
            kept.append((inner, wrapper))
            self.setItemDelegateForColumn(column, wrapper)
        return ans

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802  (matching the Qt name is the point)
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            try:
                if self.column_map[section] == table.DETAILS_COLUMN:
                    return _('Details')
            except IndexError, AttributeError:
                pass
        return orig_header_data(self, section, orientation, role)

    grid.install()

    try:
        CentralContainer.initialize_with_gui = initialize_with_gui
        BooksView.get_old_state = get_old_state
        BooksView.write_state = write_state
        BooksView.database_changed = database_changed
        BooksView.do_row_sizing = do_row_sizing
        TableView.set_delegates = set_delegates
        BooksModel.headerData = headerData
    except AttributeError, TypeError:
        return False
    _installed = True
    return True

#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The panel: a navigation bar, the list, and Reset.

One screen at a time, with a stack of the levels behind it. The root shows no
navigation bar -- there is nothing to go back to -- and every level below it
gets "Back" and "Done", which are the same gesture at different distances:
Back pops one level, Done returns to the root. Neither of them applies
anything, because the search has already run. A filter sheet that only takes
effect when you press a button would mean choosing a value, pressing Done,
looking at the result, and going back in to change it; marking a value runs the
search there and then, the way clicking a tag in the tree always has, and Done
is just the way out.

The panel never holds a `QModelIndex`. Levels address the tag browser's model
by named path, and this file re-asks each level for its rows whenever the model
says anything changed -- coalesced into one rebuild per event loop turn,
because clearing every mark emits one `dataChanged` per node.
"""

from qt.core import QHBoxLayout, QPushButton, QSize, Qt, QTimer, QVBoxLayout, QWidget

from calibre.gui2 import qapplication_or_fail
from calibre_zen.filters.levels import Entry, MenuLevel, NodeLevel, RootLevel, display_name
from calibre_zen.theme import generate, rewrite
from calibre_zen.theme.tokens import components


class FilterPanel(QWidget):
    def __init__(self, parent, tags_view):
        super().__init__(parent)
        self.tags_view = tags_view
        self.stack = []
        self._rebuild_queued = False
        self._attached_model = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.nav = QWidget(self)
        self.nav.setObjectName('zenFilterNav')
        nav_layout = QHBoxLayout(self.nav)
        nav_layout.setContentsMargins(components.FILTER_PAD_X - 6, 6, components.FILTER_PAD_X - 6, 6)
        nav_layout.setSpacing(components.FILTER_GAP)
        self.back_button = QPushButton(_('Back'), self.nav)
        self.back_button.setObjectName('zenFilterBack')
        self.back_button.setFlat(True)
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.clicked.connect(self.back)
        self.done_button = QPushButton(_('Done'), self.nav)
        self.done_button.setObjectName('zenFilterDone')
        # QPushButton:default is already "the one thing to do here" in
        # 02-buttons.qss, and Qt sets that pseudo-state from isDefault()
        # whether or not the button is in a dialog -- so the panel's primary
        # action is the app's primary button with no rule of its own.
        self.done_button.setDefault(True)
        self.done_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.done_button.clicked.connect(self.home)
        nav_layout.addWidget(self.back_button)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.done_button)
        layout.addWidget(self.nav)

        from calibre_zen.filters.view import FilterView

        self.list = FilterView(self)
        self.list.activated_entry.connect(self.activate)
        self.list.context_requested.connect(self.show_context_menu)
        layout.addWidget(self.list, 1)

        self.reset_button = QPushButton(_('Reset all filters'), self)
        self.reset_button.setObjectName('zenFilterReset')
        self.reset_button.setFlat(True)
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.clicked.connect(self.reset)
        layout.addWidget(self.reset_button)

        self.refresh_palette()
        qapplication_or_fail().palette_changed.connect(self.refresh_palette, type=Qt.ConnectionType.QueuedConnection)

    # Wiring {{{

    def attach(self) -> None:
        """
        Start following the tag browser's model.

        Called after `TagsView.set_database`, which is the first moment the
        model has a database and the Configure menu has the action groups the
        "Sort by" and "Match" rows are read from. Safe to call again: calibre
        calls set_database on every library switch.
        """
        model = self.tags_view._model
        if model is not self._attached_model:
            if self._attached_model is not None:
                for signal in (self._attached_model.modelReset, self._attached_model.dataChanged):
                    try:
                        signal.disconnect(self.queue_rebuild)
                    except TypeError:
                        pass
            model.modelReset.connect(self.queue_rebuild)
            model.dataChanged.connect(self.queue_rebuild)
            self._attached_model = model
        self.stack = [RootLevel(self.tags_view)]
        self.rebuild()

    def queue_rebuild(self, *args) -> None:
        # A rebuild is one pass over the current level, but clearing every mark
        # emits a dataChanged per node -- so coalesce into one per turn of the
        # event loop rather than rebuilding a few hundred times.
        if self._rebuild_queued:
            return
        self._rebuild_queued = True
        QTimer.singleShot(0, self._rebuild_now)

    def _rebuild_now(self) -> None:
        self._rebuild_queued = False
        self.rebuild()

    def refresh_palette(self) -> None:
        chrome = rewrite.chrome()
        self.back_button.setIcon(generate.mark_icon('chevron-left', chrome.muted))
        self.back_button.setIconSize(QSize(components.FILTER_MARK_SIZE, components.FILTER_MARK_SIZE))
        self.list.refresh_palette()

    # }}}

    # Levels {{{

    @property
    def level(self):
        return self.stack[-1] if self.stack else None

    def rebuild(self) -> None:
        level = self.level
        if level is None:
            return
        try:
            entries = level.entries()
        except Exception:
            # A level reads a live model that another part of calibre may have
            # rebuilt underneath it. An empty screen with the nav bar still on
            # it is recoverable by pressing Back; a traceback out of a paint
            # path is not.
            import traceback

            traceback.print_exc()
            entries = []
        if level.title:
            entries.insert(0, Entry(kind='header', label=level.title))
        self.nav.setVisible(bool(level.title))
        self.list.set_entries(entries)
        self.list.verticalScrollBar().setValue(getattr(level, 'scroll', 0))

    def push(self, level) -> None:
        current = self.level
        if current is not None:
            current.scroll = self.list.verticalScrollBar().value()
        self.stack.append(level)
        self.rebuild()

    def back(self) -> None:
        if len(self.stack) > 1:
            self.stack.pop()
        self.rebuild()

    def home(self) -> None:
        del self.stack[1:]
        self.rebuild()

    def activate(self, entry, on_chevron: bool) -> None:
        level = self.level
        if level is None:
            return
        nxt = level.activate(entry, on_chevron)
        if nxt is None:
            # activate() marked something, which emits dataChanged and so
            # queues the rebuild that redraws the mark. A level with nothing
            # to mark -- the sort list -- still needs one.
            if isinstance(level, MenuLevel):
                self.queue_rebuild()
            return
        self.push(nxt)

    def reveal(self, index) -> None:
        """
        Put the row for `index` on screen, opening the levels above it.

        This is what keeps the Find box working now that the tree it used to
        scroll is hidden: calibre searches the model and calls
        `show_item_at_index`, and the wrapper in this package sends the answer
        here instead of to a `scrollTo` nobody can see.
        """
        model = self.tags_view._model
        if not index.isValid():
            return
        target = tuple(model.named_path_for_index(index))
        levels = [RootLevel(self.tags_view)]
        path = ()
        for name in reversed(target[1:]):  # every ancestor, outermost first
            path = (name, *path)
            ancestor = model.index_for_named_path(list(path))
            if not ancestor.isValid():
                break
            levels.append(NodeLevel(self.tags_view, path, display_name(model.get_node(ancestor))))
        self.stack = levels
        self.rebuild()
        self.scroll_to(target)

    def scroll_to(self, path: tuple) -> None:
        entries = self.list._model.entries
        for row, entry in enumerate(entries):
            if entry.path == path:
                self.list.scrollTo(self.list._model.index(row, 0), self.list.ScrollHint.PositionAtCenter)
                return

    def reset(self) -> None:
        view = self.tags_view
        view._model.clear_state()
        view.tags_marked.emit(view.search_string)

    # }}}

    def show_context_menu(self, entry, global_pos) -> None:
        """
        Right-click is calibre's, unchanged.

        Rename, manage, hide the category, add to a user category, edit the
        notes -- several hundred lines of `TagsView.show_context_menu` that
        have nothing to do with how a row looks, and no reason to be rewritten
        here. It wants a point in the tree's coordinates and finds the row with
        `indexAt()`, so `filters/__init__.py` lets the panel answer that one
        question and this hands over the point that maps back to where the
        pointer actually is. `mapToGlobal`/`mapFromGlobal` are inverses whether
        or not the tree is visible, which is what makes that work with the tree
        hidden behind us.
        """
        if not entry.path:
            return
        view = self.tags_view
        index = view._model.index_for_named_path(list(entry.path))
        if not index.isValid():
            return
        view.setCurrentIndex(index)
        view.zen_forced_index = index
        try:
            view.show_context_menu(view.mapFromGlobal(global_pos))
        finally:
            view.zen_forced_index = None

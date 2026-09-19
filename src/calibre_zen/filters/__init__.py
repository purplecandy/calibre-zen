#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The filter panel that stands in for the tag browser's tree.

This is the first part of the overlay that is not styling. The tree, its
delegate and its context menu draw and behave in code, not in a stylesheet, so
there was never a token or a QSS rule that could turn calibre's dense
click-to-cycle outline into the flat filter sheet this reproduces: a list of
categories, each showing what it is filtering by, and one screen per category
to choose in.

**The tree is hidden, not removed, and that is the whole trick.** `TagsView`
stays alive, keeps its model, keeps receiving recounts, database changes and
marked-book notifications, and stays the object the rest of calibre talks to --
`gui.tags_view` is referenced from a couple of dozen places and every one of
them keeps working. The panel is a second view onto the same `TagsModel`, which
is a thing Qt models are for. Nothing about search, drag and drop targets,
renaming, or the twenty signals `init_tag_browser_mixin` connects is
reimplemented or rerouted.

Three wraps, all from outside, none of them an edit to an upstream file:

`TagBrowserWidget.__init__`
    Build the panel, put it where the tree was, and hide the tree.

`TagsView.set_database`
    Tell the panel to start following the model. The first moment the model
    has a database and the Configure menu has the action groups the "Sort by"
    and "Match" rows read.

`TagsView.indexAt`
    Answers with the row the panel was right-clicked on while it is asking, so
    `show_context_menu` -- which finds its row that way and is otherwise
    untouched -- builds calibre's real context menu for our row. Outside that
    one call it is the original in full, including the `indexAt(QPoint(10, 10))`
    that `recount()` does.

`TagsView.show_item_at_index`
    Keeps the Find box working: calibre searches the model and says "show
    this", and the panel opens the levels above it rather than scrolling a tree
    nobody can see.

Off with `CALIBRE_ZEN_FILTERS=0`, which brings the tree back exactly as it was
-- the before/after of this the way `CALIBRE_ZEN_STYLE=0` is the before/after
of the sheet.

**Known gaps**, all of them things the tree did that a one-screen-at-a-time
list does not:

- Dragging books onto a category, and dragging a value into a user category.
  The rows are not drop targets. The tree's own drag and drop is intact but
  unreachable while it is hidden; the context menu's "Add to user category"
  does the same job with more clicks.
- Several categories open at once. One screen is the shape of the reference
  design, and it is a real loss for anyone who kept Authors and Tags expanded
  side by side.
- Keyboard navigation and the Tag browser shortcuts that act on "the current
  item", which is now whatever the panel last set rather than something you
  can move with the arrow keys.
"""

from calibre_zen import features

_installed = False


def enabled() -> bool:
    return features.enabled('filters')


def install() -> bool:
    """
    Wrap the four methods above. Safe to call twice.

    Must not run before there is a QApplication: importing
    `calibre.gui2.tag_browser.ui` pulls in `calibre.gui2.dialogs.tag_categories`,
    which evaluates `QIcon.ic()` in a class body at import time and raises
    without one. Checked empirically -- an eager import crashed exactly that
    way -- which is why `hooks.install()` calls this from the first
    `on_palette_change` rather than from itself.
    """
    global _installed
    if _installed or not enabled():
        return _installed
    from calibre.gui2.tag_browser.ui import TagBrowserWidget
    from calibre.gui2.tag_browser.view import TagsView
    from calibre_zen.filters.panel import FilterPanel

    orig_init = TagBrowserWidget.__init__
    orig_set_database = TagsView.set_database
    orig_index_at = TagsView.indexAt
    orig_show_item_at_index = TagsView.show_item_at_index

    def __init__(self, parent):  # noqa: N807  (it is a dunder because Qt's is)
        orig_init(self, parent)
        try:
            panel = FilterPanel(self, self.tags_view)
        except Exception:
            # Losing the panel costs the new look. Losing the tag browser
            # costs the window, so leave the tree visible and carry on.
            import traceback

            traceback.print_exc()
            return
        self.zen_filter_panel = self.tags_view.zen_filter_panel = panel
        # The tree was inserted at 0 and the Configure/Find bar added after it,
        # so the bar sits below the tree. The panel takes the tree's place.
        self._layout.insertWidget(0, panel)
        self.tags_view.setVisible(False)
        # "No more matches" is a floating child of the tree, so hiding the tree
        # would hide the one thing Find has to say when it fails. It is
        # positioned absolutely at the top left of whatever it is parented to,
        # which the panel is just as well.
        self.not_found_label.setParent(panel)

    def set_database(self, db, alter_tb):
        ans = orig_set_database(self, db, alter_tb)
        panel = getattr(self, 'zen_filter_panel', None)
        if panel is not None:
            panel.attach()
        return ans

    def indexAt(self, point):  # noqa: N802  (matching the Qt name is the point)
        forced = getattr(self, 'zen_forced_index', None)
        return orig_index_at(self, point) if forced is None else forced

    def show_item_at_index(self, idx, box=False, position=None):
        ans = orig_show_item_at_index(self, idx, box) if position is None else orig_show_item_at_index(self, idx, box, position)
        panel = getattr(self, 'zen_filter_panel', None)
        if panel is not None:
            panel.reveal(idx)
        return ans

    try:
        TagBrowserWidget.__init__ = __init__
        TagsView.set_database = set_database
        TagsView.indexAt = indexAt
        TagsView.show_item_at_index = show_item_at_index
    except AttributeError, TypeError:
        return False
    _installed = True
    return True

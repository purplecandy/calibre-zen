#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Double-click a cell in the table to edit it.

calibre opens the viewer on a double-click and edits a cell on a *slow second
click* -- click the row, wait, click again. In a table built to be read and
corrected that is the wrong way round: the edit is the thing people reach for
and the slow click is the thing they cannot find. The preview's Read button,
the toolbar and the grid still open a book in one gesture.

calibre has the choice already, as the `doubleclick_on_library_view` tweak,
and `edit_cell` is exactly this: double-click edits, and the slow click goes
away. So this changes the tweak's **default** rather than the view. The line
in calibre's default tweaks text is rewritten, which is what makes it an
honest default rather than an override:

* Preferences -> Tweaks shows `edit_cell` as the default, and anything else a
  reader picks there is saved and wins, `open_viewer` included. calibre only
  saves a tweak that differs from the default, so without this a reader who
  wanted the viewer back would have had no way to say so.
* A value in the reader's own tweaks file wins, exactly as it always has.

The cover grid and the bookshelf read the same tweak, and upstream's answer
for `edit_cell` there is the Edit metadata dialog -- a cover has no cell. The
change is for the table, so while the value is our default rather than the
reader's, a double-click on a cover still opens the book
(`double_click_action`, wrapped).

`BooksView.__init__` reads the tweak once, so this must run before the main
window is built; `centre.install()` does. Off with the rest of the centre.
"""

from calibre.utils import config_base

TWEAK = 'doubleclick_on_library_view'
UPSTREAM = 'open_viewer'
OURS = 'edit_cell'

_installed = False


def rewrite(raw: str) -> str:
    "calibre's default tweaks text, with our default for the one tweak."
    return raw.replace(f"{TWEAK} = '{UPSTREAM}'", f"{TWEAK} = '{OURS}'").replace(
        f'# Default: {UPSTREAM}.\n# Example: {TWEAK} =', f'# Default: {OURS}.\n# Example: {TWEAK} ='
    )


def install() -> bool:
    "Make `edit_cell` the default. Safe to call twice."
    global _installed
    if _installed:
        return True
    import sys

    orig = config_base.default_tweaks_raw
    if f"{TWEAK} = '{UPSTREAM}'" not in orig():
        # Upstream moved or renamed the tweak; leave calibre's behaviour be.
        return False

    def default_tweaks_raw():
        return rewrite(orig())

    config_base.default_tweaks_raw = default_tweaks_raw
    # The Tweaks page imports the name, and may have been imported already.
    page = sys.modules.get('calibre.gui2.preferences.tweaks')
    if page is not None:
        page.default_tweaks_raw = default_tweaks_raw
    # `tweaks` was read at import, from the text as it was then.
    try:
        custom = config_base.read_custom_tweaks()
    except Exception:
        custom = {}
    if TWEAK not in custom:
        config_base.tweaks[TWEAK] = OURS
        keep_covers_reading()
    _installed = True
    return True


def keep_covers_reading() -> None:
    "A double-click on a cover opens the book, as it did before the default moved."
    import sys

    from calibre.gui2.library import alternate_views

    orig = alternate_views.double_click_action

    def double_click_action(index):
        if config_base.tweaks.get(TWEAK) == OURS:
            from calibre.gui2.ui import get_gui

            gui = get_gui()
            if gui is not None:
                return gui.iactions['View'].view_triggered(index)
        return orig(index)

    alternate_views.double_click_action = double_click_action
    # The bookshelf imports the name; rebinding covers it only if it has not
    # been imported yet, so an already-imported one is rebound too.
    shelf = sys.modules.get('calibre.gui2.library.bookshelf_view')
    if shelf is not None and getattr(shelf, 'double_click_action', None) is orig:
        shelf.double_click_action = double_click_action

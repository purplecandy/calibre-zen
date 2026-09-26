#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
calibre's rich text editor, as one field with a one-line toolbar.

`comments_editor.Editor` is the editor behind Comments, every custom comments
column, and a few other places. Stock it is three boxes deep: a custom
column's QGroupBox, the QTabWidget pane that holds the Normal view and HTML
source tabs, and the text area's own field border inside that -- and its
toolbar is a `FlowToolBar` that wraps its thirty-odd buttons onto two or three
rows of 18px icons.

calibre already has a one-line toolbar: `create_flow_toolbar(...,
restrict_to_single_line=True)` builds a QToolBar, whose extension button holds
whatever does not fit. The Edit metadata dialog's `one_line_comments_toolbar`
asks for it in some layouts. The wrap asks for it always, at 16px, and marks
the editor so 17-richtext.qss can make the pane the one border, drop the text
area's, put the toolbar on a hairline above the text, and take the frame off a
group box that holds nothing but the editor.
"""

_installed = False

ICON_SIZE = 16


def install() -> bool:
    "Wrap the editor. Safe to call twice. Needs a QApplication."
    global _installed
    if _installed:
        return True
    from qt.core import QGroupBox, QWidget

    from calibre.gui2 import comments_editor

    orig_create = comments_editor.create_flow_toolbar
    orig_init = comments_editor.Editor.__init__

    def create_flow_toolbar(parent=None, icon_size=18, restrict_to_single_line=False):
        return orig_create(parent, icon_size=min(icon_size, ICON_SIZE), restrict_to_single_line=True)

    def __init__(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        self.setProperty('zenRichText', True)
        box = self.parentWidget()
        if isinstance(box, QGroupBox):
            box.setProperty('zenRichTextBox', True)
            repolish(box)
        # The children were polished while calibre built them, before the
        # marker existed, and a rule keyed on an ancestor's property is only
        # read at polish.
        for w in [self, *self.findChildren(QWidget)]:
            repolish(w)

    def repolish(w):
        style = w.style()
        style.unpolish(w)
        style.polish(w)

    # Bound by name inside comments_editor, so it is replaced there.
    comments_editor.create_flow_toolbar = create_flow_toolbar
    comments_editor.Editor.__init__ = __init__
    _installed = True
    return True

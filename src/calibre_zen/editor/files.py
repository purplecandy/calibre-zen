#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The Cover & files tab, as a grouped form.

Three groups, in the same shape as Your columns (forms/):

- **Cover**: the cover itself, large, with its actions beside it. It is the
  dialog's one `Cover` widget -- drag an image onto it, right-click it -- moved
  here from the Details tab while this tab is showing and moved back after, so
  there is never a second, stale copy. calibre's own cover buttons are the
  actions, in a two-column grid.
- **Book files**: calibre's format list, flat, with its four icon buttons
  given their names and set in a row under it.
- **Data files**: one row, calibre's button.

calibre keeps every widget and what it does; `FormatsManager` still owns the
list and its commit, it is only no longer where the list is drawn.
"""

from qt.core import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from calibre_zen import forms


def build(dialog) -> QWidget:
    from calibre_zen.theme.tokens import components

    form = forms.Form(dialog)
    form.setObjectName('zenForm')
    page = QWidget(dialog)
    page.setObjectName('zenEditorFiles')
    outer = QVBoxLayout(page)
    m = components.FORM_MARGIN
    outer.setContentsMargins(m, m, m, m)
    outer.addWidget(form)

    # Cover
    cover_block = QWidget(form)
    cl = QHBoxLayout(cover_block)
    cl.setContentsMargins(0, 0, 0, 0)
    cl.setSpacing(components.FILES_COVER_GAP)
    slot = QVBoxLayout()
    slot.setContentsMargins(0, 0, 0, 0)
    cl.addLayout(slot)
    actions = QWidget(cover_block)
    al = QVBoxLayout(actions)
    al.setContentsMargins(0, 0, 0, 0)
    al.setSpacing(8)
    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(6)
    grid.setVerticalSpacing(6)
    for i, b in enumerate(dialog.cover.buttons):
        b.setParent(actions)
        b.setObjectName('zenFilesAction')
        b.setToolButtonStyle(b.toolButtonStyle().ToolButtonTextBesideIcon)
        b.setSizePolicy(b.sizePolicy().Policy.Expanding, b.sizePolicy().Policy.Fixed)
        b.show()
        grid.addWidget(b, i // 2, i % 2)
    al.addLayout(grid)
    hint = QLabel(_('Drop an image on the cover to replace it. Right-click it for more.'), actions)
    hint.setObjectName('zenFormHint')
    hint.setWordWrap(True)
    al.addWidget(hint)
    al.addStretch()
    actions.setMaximumWidth(components.FILES_ACTIONS_MAX_W)
    cl.addWidget(actions, 1)
    cl.addStretch()
    form.group(_('Cover')).block(cover_block)
    # Three of these carry icons that mean something else in the line set:
    # arrow-down.png is the pack's chevron (it is an arrow everywhere else in
    # calibre), and default_cover.png is calibre's colour picture.
    reicon(dialog.cover.download_cover_button, 'download')
    reicon(dialog.cover.generate_cover_button, 'wand')

    # Book files
    fm = dialog.formats_manager
    files_block = QWidget(form)
    fl = QVBoxLayout(files_block)
    fl.setContentsMargins(0, 0, 0, 0)
    fl.setSpacing(8)
    fm.formats.setParent(files_block)
    fm.formats.setObjectName('zenFormatList')
    fm.formats.setMinimumHeight(components.FILES_LIST_MIN_H)
    fm.formats.show()
    fl.addWidget(fm.formats, 1)
    bar = QHBoxLayout()
    bar.setContentsMargins(0, 0, 0, 0)
    bar.setSpacing(6)
    named = (
        (fm.add_format_button, _('Add a format')),
        (fm.remove_format_button, _('Remove')),
        None,
        (fm.metadata_from_format_button, _('Metadata from file')),
        (fm.cover_from_format_button, _('Cover from file')),
    )
    for entry in named:
        if entry is None:
            bar.addStretch(1)
            continue
        b, text = entry
        b.setParent(files_block)
        b.setObjectName('zenFilesAction')
        b.setText(text)
        b.setToolButtonStyle(b.toolButtonStyle().ToolButtonTextBesideIcon)
        b.setIconSize(b.iconSize().__class__(16, 16))
        b.show()
        bar.addWidget(b)
    reicon(fm.cover_from_format_button, 'photo')
    fl.addLayout(bar)
    # The manager itself draws nothing now, but it stays on this page: it is
    # where its list and buttons belong, and a hidden widget parented to the
    # dialog would sit outside every tab.
    fm.setParent(files_block)
    fm.hide()
    form.group(_('Book files')).block(files_block)

    # Data files
    g = form.group(_('Data files'))
    dialog.data_files_button.setObjectName('zenFilesAction')
    g.row(_('Extra files kept with this book'), dialog.data_files_button, kind=forms.NATURAL)
    form.finish()

    dialog._zen_files_cover_slot = slot
    return page


def place_cover(dialog, index: int) -> None:
    """
    Put the dialog's one cover widget on whichever of Details and Cover & files
    is showing, at that tab's size.
    """
    from calibre_zen.theme.tokens import components

    cover = dialog.cover
    if index == dialog.FILES:
        target, w, h = dialog._zen_files_cover_slot, components.FILES_COVER_W, components.FILES_COVER_H
    else:
        target, w, h = dialog._zen_details_cover_slot, components.EDITOR_COVER_W, components.EDITOR_COVER_H
    if target.indexOf(cover) == -1:
        target.insertWidget(0, cover)
    cover.setFixedSize(w, h)
    cover.show()


def reicon(button, glyph: str) -> None:
    from calibre_zen.icons import registry

    icon = registry.glyph_icon(glyph)
    if icon is not None:
        button.setIcon(icon)

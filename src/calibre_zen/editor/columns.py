#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The Your columns tab, re-laid as a grouped form.

calibre builds a custom column's editor as a small object (`custom_column_widgets`)
whose `widgets` list is what `populate_metadata_page` lays into its grid: a
label and a container holding the editor and its buttons, and for a series a
second pair for the number; a comments column is one QGroupBox around its
editor. The objects stay exactly as calibre made them -- they own the value,
the commit and the tab order -- and this only takes their pieces out of
calibre's grid and hands them to `forms.Form`:

- each column is one row: its name, its editor at the width its kind calls
  for, and two trailing slots for the list editor and clear;
- a series row carries the name and a short "#" number field side by side;
- Today goes, because the calendar has it; a yes/no column's Yes and No
  buttons go, because its own list has them;
- comments columns come last, in a Notes group, each under its name and a few
  lines tall to start -- a long-text column stops being one row high.
"""

from calibre_zen import forms

NOTES_TYPES = ('comments',)


def kind_for(datatype: str) -> str:
    return {
        'int': forms.NUMBER,
        'float': forms.NUMBER,
        'datetime': forms.DATE,
        'enumeration': forms.CHOICE,
        'bool': forms.CHOICE,
        'rating': forms.NATURAL,
    }.get(datatype, forms.STRETCH)


def build(parent, column_widgets) -> forms.Form:
    """
    A Form holding every column in `column_widgets`, in calibre's order with
    the comments columns gathered at the end.
    """
    from calibre_zen.theme.tokens import components

    form = forms.Form(parent)
    m = components.FORM_MARGIN
    form.layout().setContentsMargins(m, m, m, m)
    fields = [w for w in column_widgets if w.col_metadata['datatype'] not in NOTES_TYPES]
    notes = [w for w in column_widgets if w.col_metadata['datatype'] in NOTES_TYPES]
    if fields:
        g = form.group(_('Fields'))
        for w in fields:
            try:
                add_field(g, w)
            except Exception:
                # One column that will not move keeps calibre's arrangement for
                # itself, rather than costing the tab.
                import traceback

                traceback.print_exc()
    if notes:
        g = form.group(_('Notes'))
        for w in notes:
            editor = getattr(w, '_tb', None)
            if editor is None:
                continue
            box = getattr(w, '_box', None)
            g.stacked(w.col_metadata['name'], editor)
            if box is not None:
                box.hide()
    form.finish()
    return form


def add_field(group, w) -> None:
    from qt.core import QToolButton, QWidget

    from calibre.gui2.custom_column_widgets import MultipleWidget
    from calibre_zen.theme.tokens import components

    dt = w.col_metadata['datatype']
    label, container = w.widgets[0], w.widgets[1]
    editor_button = clear = None
    if dt == 'bool':
        control = w.combobox
    elif dt == 'datetime':
        control = w.dte
    else:
        control = w.editor
    mw = control if isinstance(control, MultipleWidget) else control.parentWidget()
    if isinstance(mw, MultipleWidget):
        # The list editor button lives inside calibre's two-part widget; take
        # it out to the row's slot so the field ends where every field ends.
        editor_button = mw.editor_button
        mw.layout().removeWidget(editor_button)
        control = mw.edit_widget
    clear = getattr(w, 'clear_button', None)
    for b in container.findChildren(QToolButton):
        if b is not clear and b is not editor_button:
            b.hide()  # Today, and a yes/no column's Yes and No
    for b in (editor_button, clear):
        if b is not None:
            b.setAutoRaise(True)
    controls = [control]
    if dt == 'series' and len(w.widgets) >= 4:
        from qt.core import QLabel

        hash_label = QLabel('#', container)
        hash_label.setObjectName('zenFormHint')
        w.widgets[2].hide()
        idx = w.widgets[3]
        # Its range runs to a hundred million, which is what its size hint is
        # for; a series number is a few digits.
        idx.setFixedWidth(components.FIELD_WIDTH_SERIES_INDEX)
        controls += [hash_label, idx]
    # calibre's own label, which carries the column's tooltip, without the
    # elision and the colon populate_metadata_page gave it.
    label.setText(w.col_metadata['name'])
    group.row(label, controls, kind=kind_for(dt), slots=(editor_button, clear))
    if isinstance(mw, QWidget) and mw is not control:
        mw.hide()
    container.hide()

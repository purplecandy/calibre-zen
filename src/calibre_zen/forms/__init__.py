#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
A grouped form, laid out the same way wherever the overlay builds one.

The shape is macOS System Settings': rows in rounded groups, the label at the
start of the row and the control at its end, a hairline between rows, and a
text area stacked under its label. Every number is a token in
`tokens/components.py` (the FORM_* and FIELD_WIDTH_* block) and every colour
is in 18-forms.qss, so the Your columns tab, and whatever moves onto this next,
change together.

The form never owns a value. It is handed widgets that already work --
calibre's, usually -- and only places and sizes them: a control of a fixed
kind (a number, a date, a choice) sits at the row's end at the kind's width or
its own, whichever is wider; free text sits at the row's end too, in a control
column that is the same width on every row (FORM_CONTROL_SHARE of the row,
between FIELD_WIDTH_TEXT_MIN and _MAX); and each row keeps the same trailing slots whether it fills them or not,
so every control on every row ends at the same line.
"""

from qt.core import QFrame, QHBoxLayout, QLabel, QSizePolicy, Qt, QVBoxLayout, QWidget

# What a control is, for sizing. STRETCH fills the row; the rest sit at its end.
STRETCH, NUMBER, DATE, CHOICE, NATURAL = 'stretch', 'number', 'date', 'choice', 'natural'
SLOTS = 2  # the list editor, and clear


def width_for(kind: str) -> int:
    from calibre_zen.theme.tokens import components

    return {NUMBER: components.FIELD_WIDTH_NUMBER, DATE: components.FIELD_WIDTH_DATE, CHOICE: components.FIELD_WIDTH_CHOICE}.get(kind, 0)


class Form(QWidget):
    "Groups of rows. Build with group(), then row() and stacked() on what it returns."

    def __init__(self, parent=None, control_share: float | None = None):
        from calibre_zen.theme.tokens import components

        super().__init__(parent)
        self.setObjectName('zenForm')
        # FORM_CONTROL_SHARE unless the form says otherwise: a page whose text
        # fields are the point of it (a book's title and authors) gives them more.
        self.control_share = control_share
        self.groups = []
        self.labels = []
        self.columns = []  # the free-text rows' control columns, sized together
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(components.FORM_SECTION_GAP)
        self._layout.addStretch()

    def group(self, title: str = '') -> Group:
        g = Group(self, title)
        self._layout.insertWidget(self._layout.count() - 1, g)
        self.groups.append(g)
        return g

    def column_width(self) -> int:
        """
        The control column: FORM_CONTROL_SHARE of what a row has once its
        padding and trailing slots are taken, held between FIELD_WIDTH_TEXT_MIN
        and FIELD_WIDTH_TEXT_MAX. The label side gets the rest, so a label never
        shares its line with a field running into it.
        """
        from calibre_zen.theme.tokens import components

        m = self.layout().contentsMargins()
        inner = self.width() - m.left() - m.right() - 2 * components.FORM_ROW_PAD_X - SLOTS * components.FORM_SLOT - 2 * components.FORM_LABEL_GAP - 2
        share = int(inner * (self.control_share or components.FORM_CONTROL_SHARE))
        cap = components.FIELD_WIDTH_TEXT_MAX_PRIMARY if self.control_share else components.FIELD_WIDTH_TEXT_MAX
        return max(components.FIELD_WIDTH_TEXT_MIN, min(cap, share))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        w = self.column_width()
        for column in self.columns:
            if column.width() != w or column.minimumWidth() != w:
                column.setFixedWidth(w)

    def finish(self) -> None:
        "Call once every row is in: settles the label column's width."
        from calibre_zen.theme.tokens import components

        side = [lab for lab in self.labels if lab.property('zenFormSide')]
        if not side:
            return
        width = min(components.FORM_LABEL_MAX, max(lab.sizeHint().width() for lab in side))
        for lab in side:
            lab.setMinimumWidth(width)
            lab.setMaximumWidth(components.FORM_LABEL_MAX)


class Group(QWidget):
    def __init__(self, form: Form, title: str):
        from calibre_zen.theme.tokens import components

        super().__init__(form)
        self.form = form
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(components.FORM_GROUP_TITLE_GAP)
        if title:
            t = QLabel(title, self)
            t.setObjectName('zenFormGroupTitle')
            t.setIndent(components.FORM_ROW_PAD_X)
            outer.addWidget(t)
        self.card = QFrame(self)
        self.card.setObjectName('zenFormGroup')
        self.card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.rows = QVBoxLayout(self.card)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(0)
        outer.addWidget(self.card)

    def _row(self) -> tuple[QWidget, QHBoxLayout]:
        from calibre_zen.theme.tokens import components

        row = QWidget(self.card)
        row.setObjectName('zenFormRow')
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        row.setProperty('first', self.rows.count() == 0)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(components.FORM_ROW_PAD_X, components.FORM_ROW_PAD_Y, components.FORM_ROW_PAD_X, components.FORM_ROW_PAD_Y)
        layout.setSpacing(components.FORM_LABEL_GAP)
        self.rows.addWidget(row)
        return row, layout

    def _label(self, row, label, side: bool):
        if not isinstance(label, QLabel):
            label = QLabel(str(label), row)
        label.setParent(row)
        label.setObjectName('zenFormLabel')
        label.setProperty('zenFormSide', side)
        label.setWordWrap(False)
        label.setMinimumWidth(0)
        label.setMaximumWidth(16777215)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        label.show()
        self.form.labels.append(label)
        return label

    def row(self, label, controls, kind: str = STRETCH, slots=()) -> QWidget:
        """
        One line: `label` (a QLabel to reuse, or text), then `controls` -- a
        widget or a list of them, sized by `kind` -- then up to SLOTS trailing
        widgets, None for an empty slot.
        """
        from calibre_zen.theme.tokens import components

        row, layout = self._row()
        row.setMinimumHeight(components.FORM_ROW_HEIGHT)
        lab = self._label(row, label, True)
        layout.addWidget(lab)
        controls = controls if isinstance(controls, (list, tuple)) else [controls]
        outer = QHBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)
        if kind == STRETCH:
            # Free text sits in the control column: the same width on every
            # row, set by Form.resizeEvent, at the row's end like every other
            # control -- never from the label to the edge.
            column = QWidget(row)
            column.setObjectName('zenFormColumn')
            self.form.columns.append(column)
            box = QHBoxLayout(column)
            outer.addWidget(column)
        else:
            box = outer
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        for i, w in enumerate(controls):
            w.setParent(column if kind == STRETCH else row)
            if i == 0 and kind in (NUMBER, DATE, CHOICE):
                w.setFixedWidth(max(width_for(kind), w.sizeHint().width()))
            elif i == 0 and kind == STRETCH:
                w.setMinimumWidth(0)
                w.setSizePolicy(QSizePolicy.Policy.Expanding, w.sizePolicy().verticalPolicy())
            w.show()
            box.addWidget(w, 1 if (i == 0 and kind == STRETCH) else 0)
        layout.addLayout(outer, 1)
        slots = list(slots)[:SLOTS]
        slots += [None] * (SLOTS - len(slots))
        trail = QHBoxLayout()
        trail.setContentsMargins(0, 0, 0, 0)
        trail.setSpacing(2)
        for w in slots:
            if w is None:
                w = QWidget(row)
            else:
                w.setParent(row)
                w.show()
            w.setFixedWidth(components.FORM_SLOT)
            trail.addWidget(w)
        layout.addLayout(trail)
        lab.setBuddy(controls[0])
        return row

    def block(self, widget) -> QWidget:
        "A row that is one widget, padded like the rest and with no label: a cover and its actions."
        from calibre_zen.theme.tokens import components

        row, layout = self._row()
        p = components.FORM_ROW_PAD_X
        layout.setContentsMargins(p, p, p, p)
        widget.setParent(row)
        widget.show()
        layout.addWidget(widget, 1)
        return row

    def stacked(self, label, widget) -> QWidget:
        "A label above a widget that takes the row's whole width: a text area, whose\n        starting height is TEXTAREA_MIN_HEIGHT, set in 18-forms.qss."
        from calibre_zen.theme.tokens import components

        row, layout = self._row()
        layout.setDirection(QVBoxLayout.Direction.TopToBottom)
        layout.setSpacing(components.FORM_GROUP_TITLE_GAP)
        layout.setContentsMargins(components.FORM_ROW_PAD_X, components.FORM_ROW_PAD_X - 2, components.FORM_ROW_PAD_X, components.FORM_ROW_PAD_X)
        lab = self._label(row, label, False)
        layout.addWidget(lab)
        widget.setParent(row)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        widget.show()
        layout.addWidget(widget, 1)
        lab.setBuddy(widget)
        return row

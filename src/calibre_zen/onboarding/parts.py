#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The pieces both setup pages build their grouped forms from.

A choice (a radio with a line under it), a read-only value at a row's end, a
folder button for a row's tool slot, a checkbox, and the muted lines that sit
under a form. Named for 14-onboarding.qss; sized from `components`.
"""

from qt.core import QCheckBox, QLabel, QRadioButton, QSize, Qt, QToolButton, QVBoxLayout, QWidget

from calibre.utils.localization import _
from calibre_zen.theme.tokens import components


def note(parent) -> QLabel:
    "The line under a choice, starting under its label."
    label = QLabel(parent)
    label.setObjectName('zenImportNote')
    label.setWordWrap(True)
    label.setIndent(components.ONBOARDING_OPTION_INDENT)
    return label


def hint(parent, name: str = 'zenFormHint') -> QLabel:
    "A line under the form, lined up with the rows' labels."
    label = QLabel(parent)
    label.setObjectName(name)
    label.setWordWrap(True)
    label.setIndent(components.FORM_ROW_PAD_X)
    return label


def option(parent, button, line) -> QWidget:
    "A choice: the button, and under it one line of what it means."
    w = QWidget(parent)
    box = QVBoxLayout(w)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(components.ONBOARDING_OPTION_SPACING)
    box.addWidget(button)
    box.addWidget(line)
    return w


def choice(parent) -> tuple[QRadioButton, QLabel]:
    return QRadioButton(parent), note(parent)


def value(parent) -> QLabel:
    "A value, read-only, at the row's end as System Settings shows one."
    label = QLabel(parent)
    label.setObjectName('zenImportValue')
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def picker(parent, slot, tooltip: str) -> QToolButton:
    "A row's folder button, in the form's tool slot."
    from calibre_zen.icons import registry

    button = QToolButton(parent)
    button.setObjectName('zenImportPick')
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setIconSize(QSize(components.FORM_SLOT_ICON, components.FORM_SLOT_ICON))
    icon = registry.glyph_icon('folder-open')
    if icon is not None and not icon.isNull():
        button.setIcon(icon)
    else:
        button.setText('…')
    button.setToolTip(tooltip)
    button.clicked.connect(slot)
    return button


def check(parent, text: str = '', on: bool = True) -> QCheckBox:
    box = QCheckBox(text, parent)
    box.setChecked(on)
    return box


def choose_dir(parent, title: str) -> str:
    from calibre.gui2 import choose_dir as upstream

    return upstream(parent, 'zen setup folder', title) or ''


def apply_text() -> str:
    "The Next button's label when pressing it changes something, now."
    return _('Apply && Continue')


def next_text() -> str:
    return _('&Next >')

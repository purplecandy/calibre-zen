#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The wizard's first page when calibre is on this computer: bring its settings.

Shown only when `importer.find()` sees a calibre that has been used. Two
choices. Bringing the settings over copies them when Next is pressed and goes
straight on to the tour, because the library and the device -- the next two
pages -- came across with everything else. Starting fresh goes on to
calibre's library page, exactly as the wizard did before this page existed.

The import happens in `validatePage`, not `commit`. Upstream's `accept` calls
`commit` on the visited pages only once Finish is pressed, and by then the
pages that read the library path have already been shown. Once the import has
run the choices are locked: going Back to this page cannot undo a copy.
"""

import traceback

from qt.core import QButtonGroup, QLabel, QRadioButton, Qt, QVBoxLayout, QWidget, QWizardPage

from calibre.utils.localization import _
from calibre_zen import forms
from calibre_zen.onboarding import importer
from calibre_zen.theme.tokens import components

ID = 390  # any id upstream does not use; setStartId, not the number, makes it first


class ImportPage(QWizardPage):
    def __init__(self, found: importer.Found, rerun: bool = False):
        QWizardPage.__init__(self)
        self.setObjectName('zenImportPage')
        self.found = found
        self.rerun = rerun
        self.imported = False

        self.bring = QRadioButton(self)
        self.fresh = QRadioButton(self)
        self.group = QButtonGroup(self)
        self.group.addButton(self.bring)
        self.group.addButton(self.fresh)
        self.bring_note = self.note()
        self.fresh_note = self.note()

        # The design guide's grouped form: the choice is one card, what was
        # found is another, and the line about sharing the library sits under
        # them as the form's hint.
        form = self.form = forms.Form(self, slots=0, fill=True)
        choice = form.group()
        for button, note in ((self.bring, self.bring_note), (self.fresh, self.fresh_note)):
            choice.block(self.option(button, note))
        found_group = form.group(_('Found on this computer'))
        self.library_label, self.library_value = QLabel(self), self.value()
        self.plugins_label, self.plugins_value = QLabel(self), self.value()
        self.library_row = found_group.row(self.library_label, self.library_value)
        self.plugins_row = found_group.row(self.plugins_label, self.plugins_value)
        self.library_row.setVisible(bool(found.library))
        form.finish()

        self.shared = QLabel(self)
        self.shared.setObjectName('zenFormHint')
        self.shared.setWordWrap(True)
        self.shared.setIndent(components.FORM_ROW_PAD_X)
        self.status = QLabel(self)
        self.status.setObjectName('zenImportStatus')
        self.status.setWordWrap(True)
        self.status.setIndent(components.FORM_ROW_PAD_X)
        self.status.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setSpacing(components.FORM_GROUP_TITLE_GAP)
        layout.addWidget(form)
        layout.addWidget(self.shared)
        layout.addSpacing(components.ONBOARDING_SPACING)
        layout.addWidget(self.status)
        layout.addStretch(1)

        (self.fresh if rerun else self.bring).setChecked(True)
        self.apply_texts()

    def note(self) -> QLabel:
        label = QLabel(self)
        label.setObjectName('zenImportNote')
        label.setWordWrap(True)
        label.setIndent(components.ONBOARDING_OPTION_INDENT)
        return label

    def option(self, button, note) -> QWidget:
        "A choice: the radio, and under it one line of what it means."
        w = QWidget(self)
        box = QVBoxLayout(w)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(components.ONBOARDING_OPTION_SPACING)
        box.addWidget(button)
        box.addWidget(note)
        return w

    def value(self) -> QLabel:
        "A found value, read-only, at the row's end like System Settings shows one."
        label = QLabel(self)
        label.setObjectName('zenImportValue')
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def apply_texts(self):
        self.setTitle(_('Bring your calibre settings'))
        self.setSubTitle(_('calibre is on this computer too. Its settings can come with you.'))
        self.bring.setText(_('Bring over my calibre settings'))
        self.bring_note.setText(_('Your library, plugins, toolbar and preferences. calibre keeps its own copy.'))
        if self.rerun:
            self.fresh.setText(_('Keep my current settings'))
            self.fresh_note.setText(_('Nothing is copied. You can change the library and device next.'))
        else:
            self.fresh.setText(_('Start fresh'))
            self.fresh_note.setText(_('Choose a library and a device on the next pages.'))
        self.library_label.setText(_('Library'))
        self.library_value.setText(self.found.library)
        self.library_value.setToolTip(self.found.library)
        self.plugins_label.setText(_('Plugins'))
        self.plugins_value.setText(', '.join(self.found.plugins) or _('None'))
        self.shared.setText(_('Both apps can open the same library. Use it in one app at a time.'))
        if self.imported:
            self.status.setText(_('Your calibre settings are here now.'))

    def retranslateUi(self, page):
        self.apply_texts()

    def wants_import(self) -> bool:
        return self.bring.isChecked()

    def validatePage(self):
        if self.imported or not self.wants_import():
            return True
        try:
            importer.run(self.found.path)
        except Exception:
            from calibre.gui2 import error_dialog

            error_dialog(
                self,
                _('Could not bring the settings over'),
                _('Some settings could not be copied. You can try again, or start fresh.'),
                det_msg=traceback.format_exc(),
                show=True,
            )
            return False
        self.imported = True
        self.after_import()
        return True

    def after_import(self):
        "Lock the choice, and show the running app what came across."
        for button in (self.bring, self.fresh):
            button.setEnabled(False)
        self.status.setVisible(True)
        self.apply_texts()
        wizard = self.wizard()
        try:
            from calibre_zen.theme import appearance

            # The palette choice came across with gprefs; the window is
            # already themed from the old one.
            appearance.repaint()
        except Exception:
            traceback.print_exc()
        if wizard is not None:
            try:
                wizard.zen_after_import()
            except Exception:
                traceback.print_exc()

    def nextId(self):
        from calibre.gui2.wizard import FinishPage, LibraryPage

        return FinishPage.ID if (self.imported or self.wants_import()) else LibraryPage.ID

    def commit(self):
        pass

#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The wizard's first page: bring calibre's settings, choose them, or neither.

Shown on a first run when `importer.find()` sees a calibre that has been used,
and on every run from Preferences, when there is something here to keep and
the settings may be somewhere else. Three choices:

**Bring over my calibre settings**
    calibre's own settings folder and the library it names. Offered only when
    one was found.
**Choose the settings and library**
    Both picked with a folder button on their rows. The settings folder may be
    a calibre config directory or a folder with one called `config` inside
    (`importer.settings_folder`); the library is anything `folders` agrees to.
    Pressing either button chooses this option, so a person who sees the path
    and wants another one does not have to find the radio first.
**Start fresh**, or on a re-run **Keep my current settings**
    Nothing copied; on to calibre's library page, as before this page existed.

Either import goes straight on to the tour when Next is pressed, because the
library and the device -- the next two pages -- came across with everything
else. The copy happens in `validatePage`, not `commit`: upstream's `accept`
commits the visited pages only once Finish is pressed, after the pages that
read the library path. Once it has run the page is locked; Back cannot undo
a copy.
"""

import traceback

from qt.core import QButtonGroup, QLabel, QRadioButton, QSize, Qt, QToolButton, QVBoxLayout, QWidget, QWizardPage

from calibre.utils.localization import _
from calibre_zen import forms
from calibre_zen.onboarding import folders, importer
from calibre_zen.theme.tokens import components

ID = 390  # any id upstream does not use; setStartId, not the number, makes it first
BRING, CHOOSE, FRESH = 'bring', 'choose', 'fresh'


class ImportPage(QWizardPage):
    def __init__(self, found: importer.Found | None, rerun: bool = False):
        QWizardPage.__init__(self)
        self.setObjectName('zenImportPage')
        self.found = found
        self.rerun = rerun
        self.imported = False
        # What "Choose" would import. Starts as what was found, so choosing
        # can mean changing one of the two.
        self.settings_path = found.path if found else ''
        self.library_path = found.library if found else ''
        # The library follows the settings folder until one is picked by hand.
        self.library_picked = False

        self.buttons = {}
        self.notes = {}
        self.group = QButtonGroup(self)
        for mode in (BRING, CHOOSE, FRESH):
            button = self.buttons[mode] = QRadioButton(self)
            self.group.addButton(button)
            self.notes[mode] = self.note()
            button.toggled.connect(self.mode_changed)

        # The design guide's grouped form: the choice is one card, what would
        # come over is another, and the two lines under them are its hints.
        form = self.form = forms.Form(self, slots=1, fill=True)
        choice = form.group()
        for mode in (BRING, CHOOSE, FRESH):
            row = choice.block(self.option(self.buttons[mode], self.notes[mode]))
            if mode == BRING and found is None:
                row.setVisible(False)
        self.what = form.group()
        self.settings_label, self.settings_value = QLabel(self), self.value()
        self.library_label, self.library_value = QLabel(self), self.value()
        self.plugins_label, self.plugins_value = QLabel(self), self.value()
        self.pick_settings = self.picker(self.choose_settings)
        self.pick_library = self.picker(self.choose_library)
        self.what.row(self.settings_label, self.settings_value, slots=(self.pick_settings,))
        self.what.row(self.library_label, self.library_value, slots=(self.pick_library,))
        self.what.row(self.plugins_label, self.plugins_value)
        form.finish()

        self.problem = self.hint('zenImportProblem')
        self.problem.setVisible(False)
        self.kept = self.hint()
        self.shared = self.hint()
        self.status = self.hint('zenImportStatus')
        self.status.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setSpacing(components.FORM_GROUP_TITLE_GAP)
        layout.addWidget(form)
        for label in (self.problem, self.kept, self.shared):
            layout.addWidget(label)
        layout.addSpacing(components.ONBOARDING_SPACING)
        layout.addWidget(self.status)
        layout.addStretch(1)

        first = FRESH if rerun else (BRING if found else CHOOSE)
        self.buttons[first].setChecked(True)
        self.apply_texts()

    # ------------------------------------------------------------ the parts

    def note(self) -> QLabel:
        label = QLabel(self)
        label.setObjectName('zenImportNote')
        label.setWordWrap(True)
        label.setIndent(components.ONBOARDING_OPTION_INDENT)
        return label

    def hint(self, name: str = 'zenFormHint') -> QLabel:
        label = QLabel(self)
        label.setObjectName(name)
        label.setWordWrap(True)
        label.setIndent(components.FORM_ROW_PAD_X)
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
        "A value, read-only, at the row's end as System Settings shows one."
        label = QLabel(self)
        label.setObjectName('zenImportValue')
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def picker(self, slot) -> QToolButton:
        "A row's folder button, in the form's tool slot."
        from calibre_zen.icons import registry

        button = QToolButton(self)
        button.setObjectName('zenImportPick')
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIconSize(QSize(components.FORM_SLOT_ICON, components.FORM_SLOT_ICON))
        icon = registry.glyph_icon('folder-open')
        if icon is not None and not icon.isNull():
            button.setIcon(icon)
        else:
            button.setText('…')
        button.clicked.connect(slot)
        return button

    # ------------------------------------------------------------ state

    def mode(self) -> str:
        return next(m for m, b in self.buttons.items() if b.isChecked())

    def wants_import(self) -> bool:
        return self.mode() in (BRING, CHOOSE)

    def shown(self) -> tuple:
        "(settings folder, library) as the rows should show them now."
        if self.mode() == BRING and self.found is not None:
            return self.found.path, self.found.library
        return self.settings_path, self.library_path

    def trouble(self) -> str:
        "What stops Next, in a sentence, or ''."
        if self.imported or self.mode() != CHOOSE:
            return ''
        if not self.settings_path:
            return _('Choose the folder that holds your calibre settings.')
        if not importer.settings_folder(self.settings_path):
            if importer.own_settings(self.settings_path):
                return _('Those are the settings this app is using now. Choose another folder.')
            return _('That folder has no calibre settings in it.')
        if not self.library_path:
            return _('Choose the folder that holds your library.')
        if folders.kind(self.library_path) == folders.MISSING:
            return _('The library folder is not there any more. Choose another one.')
        return ''

    def mode_changed(self, *args):
        self.refresh()
        self.completeChanged.emit()

    def refresh(self):
        settings, library = self.shown()
        found = importer.find(settings) if settings else None
        self.settings_value.setText(settings or _('Not chosen'))
        self.settings_value.setToolTip(settings)
        self.library_value.setText(library or _('Not chosen'))
        self.library_value.setToolTip(library)
        self.plugins_value.setText(', '.join(found.plugins) if found and found.plugins else _('None'))
        self.what.setEnabled(self.mode() != FRESH or self.imported)
        problem = self.trouble()
        self.problem.setText(problem)
        self.problem.setVisible(bool(problem))

    def isComplete(self):  # noqa: N802  (matching the Qt name is the point)
        return not self.trouble()

    # ------------------------------------------------------------ choosing

    def choose(self, title: str) -> str:
        from calibre.gui2 import choose_dir

        # Picking a folder is choosing them yourself, whichever option was on.
        self.buttons[CHOOSE].setChecked(True)
        return choose_dir(self, 'zen import folder', title) or ''

    def choose_settings(self):
        path = self.choose(_('Choose the calibre settings folder'))
        if not path:
            return
        folder = self.settings_path = importer.settings_folder(path) or path
        found = importer.find(folder)
        # A settings folder names its own library; take it, unless one has
        # been picked by hand.
        if found and found.library and not self.library_picked:
            self.library_path = found.library
        self.mode_changed()

    def choose_library(self):
        path = self.choose(_('Choose your library'))
        if path and folders.confirm_library(self, path):
            self.library_path = path
            self.library_picked = True
        self.mode_changed()

    # ------------------------------------------------------------ texts

    def apply_texts(self):
        self.setTitle(_('Bring your calibre settings'))
        if self.found:
            self.setSubTitle(_('calibre is on this computer too. Its settings can come with you.'))
        else:
            self.setSubTitle(_('Bring settings from a calibre folder, or keep what is here.'))
        self.buttons[BRING].setText(_('Bring over my calibre settings'))
        self.notes[BRING].setText(_('Your library, plugins, toolbar and preferences. calibre keeps its own copy.'))
        self.buttons[CHOOSE].setText(_('Choose the settings and library'))
        self.notes[CHOOSE].setText(_('Pick a settings folder and a library yourself, with the folder buttons below.'))
        if self.rerun:
            self.buttons[FRESH].setText(_('Keep my current settings'))
            self.notes[FRESH].setText(_('Nothing is copied. You can change the library and device next.'))
        else:
            self.buttons[FRESH].setText(_('Start fresh'))
            self.notes[FRESH].setText(_('Choose a library and a device on the next pages.'))
        self.settings_label.setText(_('Settings'))
        self.library_label.setText(_('Library'))
        self.plugins_label.setText(_('Plugins'))
        self.pick_settings.setToolTip(_('Choose the settings folder'))
        self.pick_library.setToolTip(_('Choose the library'))
        self.kept.setText(_('Fonts, icon sizes, colours and the rest of Look & feel stay as they are here.'))
        self.shared.setText(_('Both apps can open the same library. Use it in one app at a time.'))
        if self.imported:
            self.status.setText(_('Your calibre settings are here now.'))
        self.refresh()

    def retranslateUi(self, page):
        self.apply_texts()

    # ------------------------------------------------------------ the import

    def validatePage(self):  # noqa: N802
        if self.imported or not self.wants_import():
            return True
        settings, library = self.shown()
        try:
            importer.run(settings, library=library if self.mode() == CHOOSE else '')
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
        for widget in (*self.buttons.values(), self.pick_settings, self.pick_library):
            widget.setEnabled(False)
        self.status.setVisible(True)
        self.apply_texts()
        try:
            from calibre_zen.theme import appearance

            # Look & feel stayed behind, but the import re-read every setting,
            # and a repaint is cheap next to a window that is out of step.
            appearance.repaint()
        except Exception:
            traceback.print_exc()
        wizard = self.wizard()
        if wizard is not None:
            try:
                wizard.zen_after_import()
            except Exception:
                traceback.print_exc()

    def nextId(self):  # noqa: N802
        from calibre.gui2.wizard import FinishPage, LibraryPage

        return FinishPage.ID if (self.imported or self.wants_import()) else LibraryPage.ID

    def commit(self):
        pass

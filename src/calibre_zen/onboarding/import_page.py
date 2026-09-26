#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The wizard's first page: how this app starts out.

It is the one setup page. calibre's library page is not in the flow any more
-- the library is picked here -- and its language box is the footer's corner
button (see onboarding/__init__.py). Three choices:

**Bring over my calibre settings**
    calibre's own settings folder and the library it names, everything but
    Look & feel (importer.py). Offered only when calibre's settings were found.
**Start fresh**
    This app's own settings, and a library picked on a row here: an existing
    one, an empty folder, or a new one. On a re-run the settings row picks
    between keeping what is here, the default, and a reset to the defaults;
    nothing is reset unless that is picked. A new start goes on to the device
    page; keeping what is here goes straight to the tour.
**Advanced**
    The next page (advanced_page.py) picks the folders, the settings groups
    and the plugins.

Whatever replaces settings that are already here offers a backup first, on
by default (`importer.backup`).

The work happens when Next is pressed, in `validatePage` -- upstream commits
pages only on Finish, after the pages that read the library path -- so the
button says so: Apply & Continue whenever pressing it changes something.
Once it has run the page is locked; Back cannot undo a copy.
"""

import os
import traceback

from qt.core import QButtonGroup, QComboBox, QLabel, QVBoxLayout, QWizard, QWizardPage

from calibre.utils.localization import _
from calibre_zen import forms
from calibre_zen.onboarding import folders, importer, parts
from calibre_zen.theme.tokens import components

ID = 390  # any id upstream does not use; setStartId, not the number, makes it first
BRING, FRESH, ADVANCED = 'bring', 'fresh', 'advanced'
KEEP, RESET = 'keep', 'reset'


def default_library() -> str:
    "Where a fresh start's library goes: the one in use, else calibre's usual folder."
    from calibre.utils.config import prefs

    return prefs['library_path'] or os.path.join(os.path.expanduser('~'), _('Calibre Library'))


class ImportPage(QWizardPage):
    def __init__(self, found: importer.Found | None, rerun: bool = False):
        QWizardPage.__init__(self)
        self.setObjectName('zenImportPage')
        self.found = found
        self.rerun = rerun
        self.done = ''  # BRING, RESET or FRESH once applied
        self.backup_path = ''
        self.library_path = self.current_library = default_library()

        self.buttons, self.notes = {}, {}
        self.group = QButtonGroup(self)
        for mode in (BRING, FRESH, ADVANCED):
            self.buttons[mode], self.notes[mode] = parts.choice(self)
            self.group.addButton(self.buttons[mode])
            self.buttons[mode].toggled.connect(self.changed)

        # The design guide's grouped form: the choice is one card, and under
        # it the card for whichever option is picked.
        form = self.form = forms.Form(self, slots=1, fill=True)
        options = form.group()
        for mode in (BRING, FRESH, ADVANCED):
            row = options.block(parts.option(self, self.buttons[mode], self.notes[mode]))
            row.setVisible(mode != BRING or found is not None)

        self.bring_card = form.group()
        self.bring_settings_label, self.bring_settings = QLabel(self), parts.value(self)
        self.bring_library_label, self.bring_library = QLabel(self), parts.value(self)
        self.bring_plugins_label, self.bring_plugins = QLabel(self), parts.value(self)
        self.bring_card.row(self.bring_settings_label, self.bring_settings)
        self.bring_card.row(self.bring_library_label, self.bring_library)
        self.bring_card.row(self.bring_plugins_label, self.bring_plugins)

        self.fresh_card = form.group()
        self.fresh_library_label, self.fresh_library = QLabel(self), parts.value(self)
        self.pick_library = parts.picker(self, self.choose_library, '')
        self.fresh_card.row(self.fresh_library_label, self.fresh_library, slots=(self.pick_library,))
        self.settings_label, self.settings_choice = QLabel(self), QComboBox(self)
        self.settings_choice.addItem('', KEEP)
        self.settings_choice.addItem('', RESET)
        self.settings_choice.currentIndexChanged.connect(self.changed)
        self.settings_row = self.fresh_card.row(self.settings_label, self.settings_choice, kind=forms.CHOICE)
        self.settings_row.setVisible(rerun)

        self.backup_card = form.group()
        self.backup = parts.check(self)
        self.backup.toggled.connect(self.changed)
        self.backup_card.block(self.backup)
        form.finish()

        self.problem = parts.hint(self, 'zenImportProblem')
        self.kept = parts.hint(self)
        self.shared = parts.hint(self)
        self.advanced_hint = parts.hint(self)
        self.status = parts.hint(self, 'zenImportStatus')

        layout = QVBoxLayout(self)
        layout.setSpacing(components.FORM_GROUP_TITLE_GAP)
        layout.addWidget(form)
        for label in (self.problem, self.kept, self.shared, self.advanced_hint):
            layout.addWidget(label)
        layout.addSpacing(components.ONBOARDING_SPACING)
        layout.addWidget(self.status)
        layout.addStretch(1)

        first = BRING if (found is not None and not rerun) else FRESH
        self.buttons[first].setChecked(True)
        self.apply_texts()

    # ------------------------------------------------------------ state

    def mode(self) -> str:
        return next(m for m, b in self.buttons.items() if b.isChecked())

    def settings_action(self) -> str:
        "KEEP or RESET. A first run has nothing to keep."
        return self.settings_choice.currentData() if self.rerun else RESET

    def replaces_settings(self) -> bool:
        "Whether Next would replace settings that someone made here."
        if not self.rerun:
            return False
        return self.mode() == BRING or (self.mode() == FRESH and self.settings_action() == RESET)

    def will_apply(self) -> bool:
        "Whether pressing Next changes anything, now."
        if self.done:
            return False
        mode = self.mode()
        if mode == BRING:
            return True
        if mode == FRESH:
            return self.settings_action() == RESET or self.library_path != self.current_library
        return False

    def trouble(self) -> str:
        if self.done or self.mode() != FRESH:
            return ''
        if not self.library_path:
            return _('Choose where your books go.')
        return ''

    def changed(self, *args):
        self.refresh()
        self.completeChanged.emit()

    def refresh(self):
        mode = self.mode()
        self.bring_card.setVisible(mode == BRING)
        self.fresh_card.setVisible(mode == FRESH)
        self.backup_card.setVisible(self.replaces_settings() and not self.done)
        self.kept.setVisible(mode == BRING)
        self.shared.setVisible(mode == BRING)
        self.advanced_hint.setVisible(mode == ADVANCED and not self.done)
        if self.found is not None:
            self.bring_settings.setText(self.found.path)
            self.bring_library.setText(self.found.library or _('None'))
            self.bring_plugins.setText(', '.join(self.found.plugins) or _('None'))
        self.fresh_library.setText(self.library_path)
        self.fresh_library.setToolTip(self.library_path)
        problem = self.trouble()
        self.problem.setText(problem)
        self.problem.setVisible(bool(problem))
        self.status.setVisible(bool(self.done))
        self.setButtonText(QWizard.WizardButton.NextButton, parts.apply_text() if self.will_apply() else parts.next_text())

    def isComplete(self):  # noqa: N802  (matching the Qt name is the point)
        return not self.trouble()

    def choose_library(self):
        path = parts.choose_dir(self, _('Choose where your books go'))
        if path and folders.confirm_library(self, path):
            self.library_path = path
        self.changed()

    # ------------------------------------------------------------ texts

    def apply_texts(self):
        self.setTitle(_('Set up Calibre Zen'))
        if self.found is not None:
            self.setSubTitle(_('calibre is on this computer too. Its settings can come with you.'))
        else:
            self.setSubTitle(_('Pick where your books go, and you are ready to start.'))
        self.buttons[BRING].setText(_('Bring over my calibre settings'))
        self.notes[BRING].setText(_('Your library, plugins and preferences. The look stays Calibre Zen’s own.'))
        self.buttons[FRESH].setText(_('Start fresh'))
        if self.rerun:
            self.notes[FRESH].setText(_('Keep what is here or reset it, and pick your library.'))
        else:
            self.notes[FRESH].setText(_('Calibre Zen’s own settings, with a library you pick.'))
        self.buttons[ADVANCED].setText(_('Advanced'))
        self.notes[ADVANCED].setText(_('Choose the settings folder, the library, the plugins and which settings come over.'))
        self.bring_settings_label.setText(_('Settings'))
        self.bring_library_label.setText(_('Library'))
        self.bring_plugins_label.setText(_('Plugins'))
        self.fresh_library_label.setText(_('Library'))
        self.pick_library.setToolTip(_('Choose where your books go'))
        self.settings_label.setText(_('Settings'))
        self.settings_choice.setItemText(0, _('Keep what is here'))
        self.settings_choice.setItemText(1, _('Reset to the defaults'))
        self.backup.setText(_('Back up my current settings first'))
        self.kept.setText(_('Fonts, icon sizes, colours and the rest of Look & feel stay as they are here.'))
        self.shared.setText(_('Both apps can open the same library. Use it in one app at a time.'))
        self.advanced_hint.setText(_('Next, choose what comes over.'))
        self.status.setText(self.status_text())
        self.refresh()

    def status_text(self) -> str:
        lines = {
            BRING: _('Your calibre settings are here now.'),
            RESET: _('Your settings are back to the defaults.'),
            FRESH: _('Your library is set.'),
        }
        text = lines.get(self.done, '')
        if text and self.backup_path:
            text += '\n' + _('Your old settings are saved in %s') % self.backup_path
        return text

    def retranslateUi(self, page):
        self.apply_texts()

    # ------------------------------------------------------------ applying

    def validatePage(self):  # noqa: N802
        if not self.will_apply():
            return True
        try:
            if self.replaces_settings() and self.backup.isChecked():
                self.backup_path = importer.backup()
            if self.mode() == BRING:
                importer.run(self.found.path)
                self.done = BRING
            else:
                if self.rerun and self.settings_action() == RESET:
                    importer.reset()
                    self.done = RESET
                else:
                    self.done = FRESH
                importer.use_library(self.library_path)
        except Exception:
            from calibre.gui2 import error_dialog

            self.done = ''
            error_dialog(
                self,
                _('Could not finish setting up'),
                _('Something could not be written. You can try again, or pick another option.'),
                det_msg=traceback.format_exc(),
                show=True,
            )
            return False
        for widget in (*self.buttons.values(), self.pick_library, self.settings_choice):
            widget.setEnabled(False)
        self.apply_texts()
        settled(self)
        return True

    def nextId(self):  # noqa: N802
        from calibre.gui2.wizard import DevicePage, FinishPage
        from calibre_zen.onboarding import advanced_page

        mode = self.mode()
        if mode == ADVANCED:
            return advanced_page.ID
        if mode == BRING:
            return FinishPage.ID  # the library and the device came across
        # A new start chooses a device next; keeping what is here already has one.
        return DevicePage.ID if self.settings_action() == RESET else FinishPage.ID

    def commit(self):
        pass


def settled(page) -> None:
    "What either page does once settings have changed under the running app."
    try:
        from calibre_zen.theme import appearance

        appearance.repaint()
    except Exception:
        traceback.print_exc()
    wizard = page.wizard()
    if wizard is not None:
        try:
            wizard.zen_after_import()
        except Exception:
            traceback.print_exc()

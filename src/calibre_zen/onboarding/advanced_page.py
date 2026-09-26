#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Advanced setup: choose exactly what comes over, and from where.

Reached from the first page's Advanced choice. One grouped form, in a scroll
area because a settings folder can hold a lot of plugins:

**Folders**
    The settings folder and the library, each with a folder button. They
    start as calibre's own when those were found. Picking a settings folder
    takes the library it names, until a library is picked by hand.
**Settings**
    A switch per group in `importer.GROUPS`, all on. Look & feel is not a
    group and never comes over, whatever is ticked.
**Plugins**
    A switch per entry in the settings folder's `plugins/` -- zips, folders,
    settings files -- shown by name, as they are on disk. Matching a settings
    file to its plugin is left to the person, who knows their plugins.
**Backup**
    On a re-run, a copy of the current settings first, on by default.

The form is built again whenever the settings folder changes, because the
plugin rows are that folder's. The switches remember their state across a
rebuild. The copy happens when Apply & Continue is pressed; after it the
page is locked, as the first page is.
"""

import traceback

from qt.core import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget, QWizard, QWizardPage

from calibre.utils.localization import _
from calibre_zen import forms
from calibre_zen.onboarding import folders, importer, parts
from calibre_zen.theme.tokens import components

ID = 391


class AdvancedPage(QWizardPage):
    def __init__(self, found: importer.Found | None, rerun: bool = False):
        QWizardPage.__init__(self)
        self.setObjectName('zenAdvancedPage')
        self.rerun = rerun
        self.done = False
        self.backup_path = ''
        self.settings_path = found.path if found else ''
        self.library_path = found.library if found else ''
        self.library_picked = False  # the library follows the settings folder until then
        self.groups_on = {g.key: True for g in importer.GROUPS}
        self.plugins_on = {}
        self.backup_on = True
        self.body = None

        self.scroll = QScrollArea(self)
        self.scroll.setObjectName('zenAdvancedScroll')
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.viewport().setAutoFillBackground(False)
        # The page keeps the wizard's own margins, so the form lines up with
        # the first page's and with the header above it.
        layout = QVBoxLayout(self)
        layout.addWidget(self.scroll)
        self.build()

    # ------------------------------------------------------------ the form

    def build(self):
        "The whole body, from the current state. Called again when the settings folder changes."
        self.remember()
        body = QWidget()
        body.setObjectName('zenAdvancedBody')
        form = self.form = forms.Form(body, slots=1, fill=True)

        where = form.group(_('Folders'))
        self.settings_value, self.library_value = parts.value(body), parts.value(body)
        self.pick_settings = parts.picker(body, self.choose_settings, _('Choose the settings folder'))
        self.pick_library = parts.picker(body, self.choose_library, _('Choose the library'))
        where.row(_('Settings'), self.settings_value, slots=(self.pick_settings,))
        where.row(_('Library'), self.library_value, slots=(self.pick_library,))

        self.group_checks = {}
        settings = form.group(_('Settings'))
        for group in importer.GROUPS:
            box = self.group_checks[group.key] = parts.check(body, on=self.groups_on[group.key])
            box.toggled.connect(self.changed)
            label = QLabel(_(group.title), body)
            label.setToolTip(_(group.note) if group.note else '')
            settings.row(label, box, kind=forms.NATURAL)

        self.plugin_checks = {}
        plugins = form.group(_('Plugins'))
        entries = importer.plugin_entries(self.settings_path) if importer.settings_folder(self.settings_path) else []
        for entry in entries:
            box = self.plugin_checks[entry] = parts.check(body, on=self.plugins_on.get(entry, True))
            box.toggled.connect(self.changed)
            plugins.row(QLabel(entry, body), box, kind=forms.NATURAL)
        if not entries:
            none = QLabel(_('No plugins in this settings folder.'), body)
            none.setObjectName('zenImportNote')
            plugins.block(none)

        # A first run has nothing to back up.
        self.backup = parts.check(body, _('Back up my current settings first'), self.backup_on and self.rerun)
        if self.rerun:
            form.group().block(self.backup)
        else:
            self.backup.hide()
        self.backup.toggled.connect(self.changed)
        form.finish()

        self.problem = parts.hint(body, 'zenImportProblem')
        kept = parts.hint(body)
        kept.setText(_('Fonts, icon sizes, colours and the rest of Look & feel always stay as they are here.'))
        self.status = parts.hint(body, 'zenImportStatus')
        box = QVBoxLayout(body)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(components.FORM_GROUP_TITLE_GAP)
        box.addWidget(form)
        box.addWidget(self.problem)
        box.addWidget(kept)
        box.addSpacing(components.ONBOARDING_SPACING)
        box.addWidget(self.status)
        box.addStretch(1)

        # setWidget deletes the body it replaces.
        self.body = body
        self.scroll.setWidget(body)
        self.refresh()

    def remember(self):
        "Keep the switches' state before the form they live in is replaced."
        if self.body is None:
            return
        self.groups_on.update({k: b.isChecked() for k, b in self.group_checks.items()})
        self.plugins_on.update({k: b.isChecked() for k, b in self.plugin_checks.items()})
        self.backup_on = self.backup.isChecked()

    # ------------------------------------------------------------ state

    def groups(self) -> frozenset:
        return frozenset(k for k, b in self.group_checks.items() if b.isChecked())

    def plugins(self) -> frozenset:
        return frozenset(k for k, b in self.plugin_checks.items() if b.isChecked())

    def trouble(self) -> str:
        if self.done:
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

    def changed(self, *args):
        self.refresh()
        self.completeChanged.emit()

    def refresh(self):
        self.setTitle(_('Choose what comes over'))
        self.setSubTitle(_('Pick the folders, the settings and the plugins to bring.'))
        self.settings_value.setText(self.settings_path or _('Not chosen'))
        self.settings_value.setToolTip(self.settings_path)
        self.library_value.setText(self.library_path or _('Not chosen'))
        self.library_value.setToolTip(self.library_path)
        problem = self.trouble()
        self.problem.setText(problem)
        self.problem.setVisible(bool(problem))
        self.status.setText(self.status_text())
        self.status.setVisible(self.done)
        self.setButtonText(QWizard.WizardButton.NextButton, parts.next_text() if self.done else parts.apply_text())

    def isComplete(self):  # noqa: N802  (matching the Qt name is the point)
        return not self.trouble()

    def status_text(self) -> str:
        if not self.done:
            return ''
        text = _('Your chosen settings are here now.')
        if self.backup_path:
            text += '\n' + _('Your old settings are saved in %s') % self.backup_path
        return text

    # ------------------------------------------------------------ choosing

    def choose_settings(self):
        path = parts.choose_dir(self, _('Choose the calibre settings folder'))
        if not path:
            return
        self.settings_path = importer.settings_folder(path) or path
        found = importer.find(self.settings_path)
        if found and found.library and not self.library_picked:
            self.library_path = found.library
        self.build()
        self.completeChanged.emit()

    def choose_library(self):
        path = parts.choose_dir(self, _('Choose the library'))
        if path and folders.confirm_library(self, path):
            self.library_path = path
            self.library_picked = True
        self.changed()

    def initializePage(self):  # noqa: N802
        # Shown with the wizard's language as it is now, which the first page
        # may have just changed.
        if not self.done:
            self.build()

    def retranslateUi(self, page):
        if not self.done:
            self.build()

    # ------------------------------------------------------------ applying

    def validatePage(self):  # noqa: N802
        if self.done:
            return True
        try:
            if self.rerun and self.backup.isChecked():
                self.backup_path = importer.backup()
            importer.run(self.settings_path, library=self.library_path, groups=self.groups(), plugins=self.plugins())
        except Exception:
            from calibre.gui2 import error_dialog

            error_dialog(
                self,
                _('Could not bring the settings over'),
                _('Some settings could not be copied. You can try again, or go back and pick another option.'),
                det_msg=traceback.format_exc(),
                show=True,
            )
            return False
        self.done = True
        for widget in (self.pick_settings, self.pick_library, self.backup, *self.group_checks.values(), *self.plugin_checks.values()):
            widget.setEnabled(False)
        self.refresh()
        from calibre_zen.onboarding import import_page

        import_page.settled(self)
        return True

    def nextId(self):  # noqa: N802
        from calibre.gui2.wizard import FinishPage

        return FinishPage.ID

    def commit(self):
        pass

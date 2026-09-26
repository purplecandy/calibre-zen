#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The language picker, in the corner of the wizard's footer.

calibre asks for the interface language on its library page, which our
setup page has replaced. The language box is still there -- the wizard builds
that page whether or not it is shown -- and it is the part that knows how to
switch a running process over: translators, field names, every page's text,
the wizard's own buttons. So the corner button drives that box and nothing
else: its menu lists the box's entries, and choosing one sets the box's
index, which runs upstream's `change_language` exactly as a click there did.

QWizard puts a custom button in the footer's layout for us; it is shown only
while the setup page is, since the pages after it are in the language picked.
"""

from qt.core import QMenu, QPushButton, Qt, QWizard

from calibre.utils.localization import _


class LanguageButton(QPushButton):
    def __init__(self, wizard):
        super().__init__(wizard)
        self.setObjectName('zenLanguageButton')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.wizard_ = wizard
        self.menu_ = QMenu(self)
        self.menu_.aboutToShow.connect(self.build_menu)
        self.setMenu(self.menu_)
        from calibre_zen.icons import registry

        icon = registry.glyph_icon('language')
        if icon is not None and not icon.isNull():
            self.setIcon(icon)
        self.box().currentIndexChanged.connect(self.sync)
        self.sync()

    def box(self):
        return self.wizard_.library_page.language

    def sync(self, *args):
        box = self.box()
        self.setText(box.currentText())
        self.setToolTip(_('The language Calibre Zen speaks'))

    def build_menu(self):
        self.menu_.clear()
        box = self.box()
        for i in range(box.count()):
            action = self.menu_.addAction(box.itemText(i))
            action.setCheckable(True)
            action.setChecked(i == box.currentIndex())
            action.triggered.connect(lambda _checked=False, i=i: self.choose(i))

    def choose(self, index: int):
        box = self.box()
        if index != box.currentIndex():
            # Upstream rebuilds the box after switching, with the new language
            # first; sync() runs from its signal then and after.
            box.setCurrentIndex(index)
        self.sync()


def install(wizard, page_id: int) -> LanguageButton:
    "Put the button in the footer's first slot, shown while `page_id` is."
    button = LanguageButton(wizard)
    wizard.setButton(QWizard.WizardButton.CustomButton1, button)
    layout = [
        QWizard.WizardButton.CustomButton1,
        QWizard.WizardButton.Stretch,
        QWizard.WizardButton.BackButton,
        QWizard.WizardButton.NextButton,
        QWizard.WizardButton.CommitButton,
        QWizard.WizardButton.FinishButton,
        QWizard.WizardButton.CancelButton,
    ]
    wizard.setButtonLayout(layout)

    def shown(current_id: int):
        # The option alone keeps a button that is in the layout on screen; it
        # is hidden by hand as well.
        on = current_id == page_id
        wizard.setOption(QWizard.WizardOption.HaveCustomButton1, on)
        button.setVisible(on)

    wizard.currentIdChanged.connect(shown)
    shown(page_id if wizard.startId() == page_id else -1)
    wizard.zen_language_button = button
    return button

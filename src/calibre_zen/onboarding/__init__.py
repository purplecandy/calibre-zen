#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The welcome wizard's last pages, replaced.

calibre's wizard ends on a page of three paragraphs: congratulations, a link to
calibre's demo videos, a link to the manual. A person arriving here has just
installed a calibre whose window is not laid out like calibre's, and the pages
that greet them should show what moved. Ours are one page per change -- a
title, one line, and a recording of the window -- and the last of them keeps
the one line that matters from upstream's: which button applies the settings.

One replacement and two wraps, no upstream file edited, and one page added in
front when calibre is on the same computer (see importer.py and
import_page.py):

`calibre.gui2.wizard.FinishPage`
    `Wizard.__init__` builds its pages from module-level names looked up at
    call time, so rebinding the name is enough for the wizard to construct
    ours. The other pages' `nextId` return `FinishPage.ID`, which ours keeps.
    Subclassing rather than replacing keeps every attribute upstream reaches
    into afterwards -- `finish_text` for `set_finish_text`, `retranslateUi`
    and `commit` for the `_WizardPageWithMethods` protocol.

`Wizard.__init__`
    Adds the offer to bring calibre's settings over and starts there, when
    there are settings to bring; registers the steps after the first, which
    upstream knows nothing about;
    opens the wizard at `components.ONBOARDING_WIZARD_*` rather than the
    600x520 upstream chose for three paragraphs; titles the window with the
    display name, as the main window is; drops the library icon upstream puts
    in the header's corner; and lines the header's subtitle up under its
    title (see `_align_header`).

`Wizard.set_finish_text`
    Upstream writes the Finish button's real label into the first step's
    footer, because that page used to be the last. The text is copied on to
    the page that is now last.

CALIBRE_ZEN_ONBOARDING=0 leaves the page as calibre wrote it.
"""

import os

_installed = False


def enabled() -> bool:
    return os.environ.get('CALIBRE_ZEN_ONBOARDING', '1') not in ('0', 'false', 'no', 'off')


def install() -> bool:
    "Rebind the page and wrap the wizard. Safe to call twice."
    global _installed
    if _installed or not enabled():
        return _installed
    from qt.core import QPixmap, QWizard

    from calibre.constants import __appname__, zen_display_name
    from calibre.gui2 import wizard as wizard_mod
    from calibre_zen.onboarding import page

    wizard_mod.FinishPage = page.ZenFinishPage

    orig_init = wizard_mod.Wizard.__init__
    orig_set_finish_text = wizard_mod.Wizard.set_finish_text

    def __init__(self, parent):
        orig_init(self, parent)
        add_import_page(self)
        self.zen_steps = [self.finish_page]
        for index in range(1, len(page.STEPS)):
            step = page.StepPage(index)
            self.setPage(page.step_id(index), step)
            self.zen_steps.append(step)
        self.set_finish_text()
        title = self.windowTitle()
        if title.startswith(__appname__):
            self.setWindowTitle(zen_display_name + title[len(__appname__) :])
        # The header's corner icon is calibre's library glyph; a recording of
        # the window is the picture on these pages, and one is enough.
        self.setPixmap(QWizard.WizardPixmap.LogoPixmap, QPixmap())
        self.zen_header = HeaderAligner(self)
        from calibre_zen.theme.tokens import components

        # Only ever grow: a wizard that comes up smaller than upstream's would
        # be a regression on the pages we did not touch. Not from sizeHint():
        # QWizard's hint is taken before the pages have been laid out and came
        # back under 600x520 with a page that plainly needs more.
        self.resize(max(components.ONBOARDING_WIZARD_WIDTH, self.width()), max(components.ONBOARDING_WIZARD_HEIGHT, self.height()))

    def set_finish_text(self, *args):
        orig_set_finish_text(self, *args)
        steps = getattr(self, 'zen_steps', None)
        if steps and steps[-1] is not self.finish_page:
            steps[-1].footer.setText(self.finish_page.finish_text.text())

    wizard_mod.Wizard.__init__ = __init__
    wizard_mod.Wizard.set_finish_text = set_finish_text
    wizard_mod.Wizard.zen_after_import = after_import
    _installed = True
    return True


def add_import_page(wizard) -> None:
    """
    Open on the offer to bring calibre's settings, when there are any.

    A first run offers the import; a run from Preferences offers it too, but
    starts on keeping what is here, because by then there is something here.
    """
    from calibre.utils.config import dynamic
    from calibre_zen.onboarding import import_page, importer

    try:
        found = importer.find()
    except Exception:
        import traceback

        traceback.print_exc()
        found = None
    if found is None:
        return
    page = import_page.ImportPage(found, rerun=bool(dynamic.get('welcome_wizard_was_run', False)))
    wizard.setPage(import_page.ID, page)
    wizard.setStartId(import_page.ID)
    wizard.zen_import_page = page


def after_import(wizard) -> None:
    """
    Show the imported language, if it is not the one on screen.

    The wizard's language box already knows how to switch the whole process
    over -- translators, field names, every page's text -- so the imported
    choice is put into it rather than repeated here.
    """
    from calibre.utils.config import prefs

    box = wizard.library_page.language
    lang = prefs['language'] or ''
    current = str(box.itemData(box.currentIndex()) or '')
    if not lang or lang == current:
        return
    index = box.findData(lang)
    if index >= 0:
        box.setCurrentIndex(index)


def _header_labels(wizard):
    """
    The header's title and subtitle labels, or (None, None).

    QWizard's header is a private class PyQt sees as a plain QWidget, so its
    labels are found by what they say: the ones showing the current page's
    title and subtitle that are not on the page itself.
    """
    from qt.core import QLabel

    current = wizard.currentPage()
    if current is None:
        return None, None
    title = subtitle = None
    for label in wizard.findChildren(QLabel):
        if current.isAncestorOf(label):
            continue
        text = label.text()
        if text and text == current.title():
            title = label
        elif text and text == current.subTitle():
            subtitle = label
    return title, subtitle


def _align_header(wizard) -> None:
    """
    Put the subtitle's left edge under the title's.

    QWizard's modern header lays the title across two grid columns and the
    subtitle in the second alone, so the subtitle sits 23px in from the title
    and from everything on the page beneath. It is not a preference anywhere:
    the column widths are set again in the header's setup(), which runs on
    every page change and layout pass. Zeroing the columns between the two
    labels, whenever that has happened, is the whole fix.
    """
    from qt.core import QGridLayout

    title, subtitle = _header_labels(wizard)
    if title is None or subtitle is None or title.parent() is not subtitle.parent():
        return
    grid = title.parent().layout()
    if not isinstance(grid, QGridLayout):
        return
    _, title_col, _, _ = grid.getItemPosition(grid.indexOf(title))
    _, subtitle_col, _, _ = grid.getItemPosition(grid.indexOf(subtitle))
    for col in range(title_col, subtitle_col):
        if grid.columnMinimumWidth(col):
            grid.setColumnMinimumWidth(col, 0)


class HeaderAligner:
    """
    Keeps `_align_header` applied.

    The header re-lays itself on every page change and on every layout pass
    over the wizard, so the alignment is re-applied on `currentIdChanged` and
    from an event filter on the header for the layout requests and resizes
    that follow. The filter is installed once the header exists, which is
    after the first page has been shown.
    """

    def __init__(self, wizard):
        from qt.core import QEvent, QObject

        self.wizard = wizard
        self.header = None
        aligner = self

        class Filter(QObject):
            def eventFilter(self, obj, ev):
                if ev.type() in (QEvent.Type.LayoutRequest, QEvent.Type.Resize, QEvent.Type.Show):
                    aligner.apply()
                return False

        self.filter = Filter(wizard)
        wizard.currentIdChanged.connect(self.apply)

    def apply(self, *args):
        title, _subtitle = _header_labels(self.wizard)
        if title is not None and self.header is None:
            self.header = title.parent()
            self.header.installEventFilter(self.filter)
        _align_header(self.wizard)

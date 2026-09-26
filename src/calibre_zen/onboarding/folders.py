#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Whether a folder can be a library, asked the same way on both wizard pages.

calibre's library page takes a folder that already holds a library or one
that is empty, and turns anything else away with "not empty". That is right
for its one job, making a new library, and a dead end for everyone else: a
folder of someone's own files, or a settings folder picked by mistake. So a
folder that is neither gets a question or a pointer instead:

* **A settings folder** is not a library. The answer says where settings are
  brought from, and the folder is not taken.
* **Any other folder with files in it** can hold a new library beside them.
  calibre adds `metadata.db` and one folder per author, and moves or removes
  nothing that is there, so the person is asked and the choice is theirs.

Nothing here writes. The path is only recorded, by whoever asked.
"""

import os

from calibre.utils.localization import _
from calibre_zen.onboarding import importer

LIBRARY, EMPTY, SETTINGS, FILES, MISSING = 'library', 'empty', 'settings', 'files', 'missing'


def kind(path: str) -> str:
    "What `path` is, as far as choosing a library goes."
    if not path or not os.path.isdir(path):
        return MISSING
    if importer.is_library(path):
        return LIBRARY
    try:
        if not os.listdir(path):
            return EMPTY
    except OSError:
        return MISSING
    if importer.settings_folder(path) or importer.own_settings(path):
        return SETTINGS
    return FILES


def confirm_library(parent, path: str) -> bool:
    """
    True when `path` may be used as a library, asking when it is not obvious.

    A library or an empty folder is simply yes; a missing one simply no, since
    the pickers only offer folders that exist.
    """
    from calibre.gui2 import error_dialog, question_dialog

    what = kind(path)
    if what in (LIBRARY, EMPTY):
        return True
    if what == SETTINGS:
        error_dialog(
            parent,
            _('This is a settings folder'),
            _('This folder holds calibre settings, not books. Go back to the first page and choose the settings and library there.'),
            show=True,
        )
        return False
    if what == FILES:
        return question_dialog(
            parent,
            _('Start a library here?'),
            _('This folder has files in it but no calibre library. A new library can start here, next to them. Nothing in the folder is moved or removed.'),
            yes_text=_('Use this folder'),
            no_text=_('Choose another'),
        )
    return False


def install_library_page(wizard_mod) -> None:
    """
    Ask instead of refusing on calibre's own library page.

    `is_library_dir_suitable` is the one question `change()` and
    `validatePage()` both put, so it is the one wrapped. The answer is kept
    per path, so a folder agreed to when it was picked is not asked about
    again when Next is pressed; and a folder the person has just said no to
    does not also get upstream's "not empty" error on top.
    """
    page_cls = wizard_mod.LibraryPage
    orig_suitable = page_cls.is_library_dir_suitable
    orig_error = page_cls.show_library_dir_error

    def is_library_dir_suitable(self, x):
        if orig_suitable(self, x):
            return True
        agreed = self.__dict__.setdefault('zen_agreed', set())
        if x in agreed:
            return True
        if kind(x) in (SETTINGS, FILES):
            self.zen_answered = x
            if confirm_library(self, x):
                agreed.add(x)
                return True
        return False

    def show_library_dir_error(self, x):
        if getattr(self, 'zen_answered', None) == x:
            # The question was the message; it has had its answer.
            self.zen_answered = None
            return
        return orig_error(self, x)

    page_cls.is_library_dir_suitable = is_library_dir_suitable
    page_cls.show_library_dir_error = show_library_dir_error

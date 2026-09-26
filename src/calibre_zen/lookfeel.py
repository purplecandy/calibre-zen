#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Preferences -> Look & feel: a word about this app's own look, and a way back
to it.

Every setting on calibre's Look & feel pages still works here, and most of
them now pull against the overlay: a font or an icon size of calibre's sits on
top of this app's, and fonts, icons and spacing stop lining up in small ways
everywhere. So the page opens on a notice that says so, with one button,
**Reset to Calibre Zen's defaults**, that takes every Look & feel setting out
of the stored preferences -- the same rules the welcome wizard's import uses
(configdir.py) -- so this app's defaults apply again.

One wrap, no upstream file edited:

`look_feel.ConfigWidget.genesis`
    Runs once, after the page's form is built. The page is one grid, the
    section list and the tabs side by side on row 0; both move down a row and
    the notice takes row 0 across the grid.

The reset offers a backup first, on by default, as the wizard does. Then it
asks for a restart, because what is on screen was drawn with the old look.
Either answer leaves the page without committing it: the page's widgets still
show the old values, and calibre's commit writes back every widget that
differs from the stored setting -- which, after a reset, is all of them. So
"Restart now" does what the page's own `restart_now` does, minus the commit,
and "Later" closes the page and notes that a restart is owed, which is how
calibre itself keeps Preferences shut until one has happened.

Off with CALIBRE_ZEN_LOOKFEEL=0.
"""

import traceback

from qt.core import QCheckBox, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSizePolicy, Qt

from calibre.utils.localization import _

_installed = False


def enabled() -> bool:
    import os

    return os.environ.get('CALIBRE_ZEN_LOOKFEEL', '1').lower() not in ('0', 'false', 'no', 'off')


def install() -> bool:
    "Wrap the page's genesis. Safe to call twice."
    global _installed
    if _installed or not enabled():
        return _installed
    from calibre.gui2.preferences import look_feel

    orig_genesis = look_feel.ConfigWidget.genesis

    def genesis(self, gui):
        ans = orig_genesis(self, gui)
        try:
            add_notice(self)
        except Exception:
            # The page without our notice is still calibre's whole page.
            traceback.print_exc()
        return ans

    look_feel.ConfigWidget.genesis = genesis
    _installed = True
    return True


class Notice(QFrame):
    "The card across the top of the page: a line of text and the reset button."

    def __init__(self, page):
        from calibre_zen.theme.tokens import components

        super().__init__(page)
        self.page = page
        self.setObjectName('zenLookFeelNotice')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        layout = QHBoxLayout(self)
        pad = components.LOOKFEEL_NOTICE_PAD
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(components.LOOKFEEL_NOTICE_GAP)

        self.glyph = QLabel(self)
        self.glyph.setObjectName('zenLookFeelGlyph')
        try:
            from calibre_zen.icons import registry

            icon = registry.glyph_icon('info-circle', 'text')
            if icon is not None and not icon.isNull():
                size = components.LOOKFEEL_NOTICE_ICON
                self.glyph.setPixmap(icon.pixmap(size, size))
        except Exception:
            traceback.print_exc()
        layout.addWidget(self.glyph, 0, Qt.AlignmentFlag.AlignVCenter)

        self.text = QLabel(self)
        self.text.setObjectName('zenLookFeelText')
        self.text.setWordWrap(True)
        self.text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.text.setText(_('Calibre Zen has its own look. Changing these settings can make fonts, icon sizes and spacing clash with it.'))
        layout.addWidget(self.text, 1)

        self.reset = QPushButton(_('Reset to Calibre Zen’s defaults'), self)
        self.reset.setObjectName('zenLookFeelReset')
        self.reset.clicked.connect(self.ask)
        layout.addWidget(self.reset, 0, Qt.AlignmentFlag.AlignVCenter)

    def ask(self):
        "Confirm, with the backup offer; reset; then ask about the restart."
        box = QMessageBox(self.page)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(_('Reset Look & feel?'))
        box.setText(_('Reset Look & feel to Calibre Zen’s defaults?'))
        box.setInformativeText(_('Fonts, icon sizes, colours and the rest of Look & feel go back to the defaults. Your other settings stay as they are.'))
        backup = QCheckBox(_('Back up my current settings first'), box)
        backup.setChecked(True)
        box.setCheckBox(backup)
        yes = box.addButton(_('Reset'), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(yes)
        box.exec()
        if box.clickedButton() is not yes:
            return
        try:
            saved = reset(backup.isChecked())
        except Exception:
            from calibre.gui2 import error_dialog

            error_dialog(
                self.page,
                _('Could not reset Look & feel'),
                _('Some settings could not be changed. Nothing else was touched.'),
                det_msg=traceback.format_exc(),
                show=True,
            )
            return
        self.ask_restart(saved)

    def ask_restart(self, saved: str):
        box = QMessageBox(self.page)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(_('Restart to finish'))
        box.setText(_('Calibre Zen’s look comes back after a restart.'))
        if saved:
            box.setInformativeText(_('Your old settings are saved in %s') % saved)
        now = box.addButton(_('Restart now'), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(_('Later'), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(now)
        box.exec()
        leave(self.page, restart=box.clickedButton() is now)


def add_notice(page) -> Notice:
    """
    Put the notice at the top of the page, across the grid's columns.

    The grid is taken apart and put back a row lower rather than wrapped in a
    new layout: a widget cannot be given a second top-level layout, and the
    grid's own margins and spacing are what the page is spaced by.
    """
    from qt.core import QGridLayout

    existing = getattr(page, 'zen_notice', None)
    if existing is not None:
        return existing
    notice = Notice(page)
    grid = page.layout()
    if isinstance(grid, QGridLayout):
        items = []
        while grid.count():
            index = grid.count() - 1
            row, column, rows, columns = grid.getItemPosition(index)
            items.append((grid.takeAt(index), row, column, rows, columns))
        span = max((c + cs for _i, _r, c, _rs, cs in items), default=1)
        grid.addWidget(notice, 0, 0, 1, span)
        for item, row, column, rows, columns in reversed(items):
            grid.addItem(item, row + 1, column, rows, columns)
    elif grid is not None:
        grid.insertWidget(0, notice)
    page.zen_notice = notice
    return notice


def reset(with_backup: bool) -> str:
    "Back up (when asked) and reset. Returns the backup's path, or ''."
    from calibre_zen import configdir

    saved = configdir.backup() if with_backup else ''
    configdir.reset_look_and_feel()
    return saved


def preferences_dialog(page):
    "The Preferences window showing `page`, or None when it is shown on its own."
    w = page.parentWidget()
    while w is not None:
        if hasattr(w, 'hide_plugin') and hasattr(w, 'do_restart'):
            return w
        w = w.parentWidget()
    return None


def leave(page, restart: bool) -> None:
    """
    Close the page without committing it, and restart or note that one is owed.

    Mirrors Preferences.restart_now without its commit (see the module's
    docstring for why). Later sets the main window's
    `must_restart_before_config` itself: the dialog only hands its own flag on
    when it has committed, and this page never does.
    """
    from qt.core import QDialog

    dialog = preferences_dialog(page)
    if dialog is None:
        return
    dialog.hide_plugin()
    if restart:
        dialog.do_restart = True
        dialog.on_shutdown()
        QDialog.accept(dialog)
    else:
        dialog.must_restart = True
        gui = getattr(dialog, 'gui', None)
        if gui is not None:
            gui.must_restart_before_config = True

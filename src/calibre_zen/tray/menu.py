#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The icon in the menubar or tray, and its menu. Everything it shows comes
from the Keeper; everything it changes goes through `settings` and then a
restart of the host.

    Sharing at 192.168.1.18:8080        state; disabled, it is a label
    (the reason, when stopped)
    Calibre Library, 2,000 books        disabled
    Try again                           only when stopped
    ---
    Open in browser
    Copy address
    ---
    Open Calibre Zen
    ---
    [x] Share on this network
    [ ] Allow changes from this computer
    [ ] Add books from a folder…
    ---
    Quit

The settings toggles are greyed out while the full app is open: it owns the
same files then, and would write its own copy back over the tray's.
A toggle is also greyed out when the tray was started with the matching
calibre-server flag, which would win over the setting anyway.
"""

import os
import sys

from qt.core import QAction, QApplication, QCursor, QDesktopServices, QFileDialog, QMenu, QObject, QPalette, QSystemTrayIcon, QUrl

from calibre_zen.reader import activation
from calibre_zen.tray import keeper as k
from calibre_zen.tray import settings as default_settings
from calibre_zen.tray.icon import Icons

# calibre-server flags that override each toggle's setting.
OVERRIDES = {
    'share': ('--listen-on',),
    'write': ('--enable-local-write', '--disable-local-write'),
    'auto_add': ('--auto-add', '--no-auto-add'),
}


def bare_address(url: str) -> str:
    "http://192.168.1.18:8080/ -> 192.168.1.18:8080"
    a = url.split('://', 1)[-1]
    return a[:-1] if a.endswith('/') and a.count('/') == 1 else a


def open_url(url: str) -> None:
    QDesktopServices.openUrl(QUrl(url))


def choose_folder(title: str, start: str) -> str:
    activation.accessory(activate=True)  # the dialog comes to the front, with the keyboard
    return QFileDialog.getExistingDirectory(None, title, start)


class Tray(QObject):
    def __init__(self, keeper, settings=None, open_url=open_url, choose_folder=choose_folder, quit_app=None, mask=None, parent=None):
        super().__init__(parent)
        from calibre.constants import zen_display_name
        from calibre.utils.localization import _

        self.keeper = keeper
        self.settings = settings or default_settings
        self.open_url = open_url
        self.choose_folder = choose_folder
        self.quit_app = quit_app or QApplication.instance().quit
        self.app_name = zen_display_name
        mask = sys.platform == 'darwin' if mask is None else mask
        color = '#000000' if mask else QApplication.instance().palette().color(QPalette.ColorRole.WindowText).name()
        self.icons = Icons(color, mask)

        self.menu = m = QMenu()

        def item(text, slot=None, checkable=False):
            ac = QAction(text, m)
            if slot is None:
                ac.setEnabled(False)
            else:
                ac.triggered.connect(slot)
            ac.setCheckable(checkable)
            m.addAction(ac)
            return ac

        self.state_action = item('')
        self.reason_action = item('')
        self.library_action = item('')
        self.retry_action = item(_('Try again'), self.keeper.try_again)
        m.addSeparator()
        self.browser_action = item(_('Open in browser'), self.open_in_browser)
        self.copy_action = item(_('Copy address'), self.copy_address)
        m.addSeparator()
        self.gui_action = item(_('Open {}').format(self.app_name), self.keeper.open_gui)
        m.addSeparator()
        self.share_action = item(_('Share on this network'), self.toggle_share, checkable=True)
        self.write_action = item(_('Allow changes from this computer'), self.toggle_write, checkable=True)
        self.auto_add_action = item(_('Add books from a folder…'), self.toggle_auto_add, checkable=True)
        m.addSeparator()
        self.quit_action = item(_('Quit'), self.quit)

        self.icon = QSystemTrayIcon(self.icons.get(faded=True), self)
        self.icon.setContextMenu(m)
        self.icon.activated.connect(self.activated)
        # A refresh on every open as well as on every change: the full app
        # may have changed a setting since the last one.
        m.aboutToShow.connect(self.refresh)
        keeper.changed.connect(self.refresh)
        self.refresh()

    def show(self) -> None:
        self.icon.show()

    def activated(self, reason) -> None:
        # macOS opens the menu on any click. Windows and most Linux trays open
        # it on a right click only, and a left click on a tray app that only
        # has a menu should open it too.
        if reason == QSystemTrayIcon.ActivationReason.Trigger and sys.platform != 'darwin':
            self.menu.popup(QCursor.pos())

    # What the menu says {{{

    def state_text(self) -> str:
        from calibre.utils.localization import _

        s = self.keeper.state
        if s == k.SHARING:
            return _('Sharing at {}').format(bare_address(self.keeper.address()))
        if s == k.PAUSED:
            return _('Paused while {} is open').format(self.app_name)
        if s == k.STOPPED:
            return _('Sharing stopped')
        if s == k.OPENING:
            return _('Opening {}…').format(self.app_name)
        return _('Starting…')

    def library(self) -> dict:
        "The library this tray serves, from the last status, matched by path when one was given."
        libs = (self.keeper.status or {}).get('libraries') or []
        want = self.keeper.library
        if want:
            for lib in libs:
                if lib.get('path') and os.path.normcase(os.path.abspath(lib['path'])) == os.path.normcase(os.path.abspath(want)):
                    return lib
            return {'name': os.path.basename(os.path.normpath(want)), 'path': want, 'books': None}
        return libs[0] if libs else {}

    def library_text(self) -> str:
        from calibre.utils.localization import ngettext

        lib = self.library()
        name = lib.get('name') or ''
        books = lib.get('books')
        if books is None or self.keeper.state != k.SHARING:
            return name
        count = ngettext('{} book', '{} books', books).format(f'{books:,}')
        return f'{name}, {count}' if name else count

    def overridden(self, which: str) -> bool:
        flags = OVERRIDES[which]
        return any(a == f or a.startswith(f + '=') for a in self.keeper.args for f in flags)

    def refresh(self) -> None:
        from calibre.utils.localization import _

        kp = self.keeper
        state = kp.state
        sharing = state == k.SHARING
        self.state_action.setText(self.state_text())
        self.reason_action.setText(kp.reason)
        self.reason_action.setVisible(state == k.STOPPED and bool(kp.reason))
        lib = self.library_text()
        self.library_action.setText(lib)
        self.library_action.setVisible(bool(lib))
        self.retry_action.setVisible(state == k.STOPPED)
        self.browser_action.setEnabled(sharing)
        self.copy_action.setEnabled(sharing)
        self.gui_action.setEnabled(state != k.OPENING)

        # The full app owns the settings while it is open.
        free = state not in (k.PAUSED, k.OPENING)
        try:
            share, write, folder = self.settings.share_on_network(), self.settings.allow_local_write(), self.settings.auto_add_folder()
        except Exception:
            import traceback

            traceback.print_exc()
            share = write = False
            folder = None
            free = False
        self.share_action.setChecked(share)
        self.share_action.setEnabled(free and not self.overridden('share'))
        self.write_action.setChecked(write)
        self.write_action.setEnabled(free and not self.overridden('write'))
        self.auto_add_action.setChecked(bool(folder))
        self.auto_add_action.setText(_('Add books from {}').format(os.path.basename(os.path.normpath(folder))) if folder else _('Add books from a folder…'))
        self.auto_add_action.setEnabled(free and not self.overridden('auto_add'))

        self.icon.setIcon(self.icons.get(faded=state in (k.STARTING, k.PAUSED, k.OPENING), dot=state == k.STOPPED))
        tip = self.state_text()
        if state == k.STOPPED and kp.reason:
            tip += '\n' + kp.reason
        self.icon.setToolTip(f'{self.app_name}\n{tip}')

    # }}}

    # What the menu does {{{

    def open_in_browser(self) -> None:
        # This computer's own address: it works whether or not the network does.
        if self.keeper.url:
            self.open_url(self.keeper.url)

    def copy_address(self) -> None:
        a = self.keeper.address()
        if a:
            QApplication.clipboard().setText(a)

    def toggle_share(self, on: bool) -> None:
        self.settings.set_share_on_network(on)
        self.keeper.restart()
        self.refresh()

    def toggle_write(self, on: bool) -> None:
        self.settings.set_allow_local_write(on)
        self.keeper.restart()
        self.refresh()

    def toggle_auto_add(self, on: bool) -> None:
        from calibre.utils.localization import _

        if not on:
            self.settings.set_auto_add_folder(None)
            self.keeper.restart()
            self.refresh()
            return
        path = self.choose_folder(_('Choose a folder to add books from'), os.path.expanduser('~'))
        if not path:
            self.refresh()  # cancelled: put the check mark back the way it was
            return
        libraries = [lib.get('path') for lib in (self.keeper.status or {}).get('libraries') or []]
        if self.keeper.library:
            libraries.append(self.keeper.library)
        problem = self.settings.folder_problem(path, libraries)
        if problem:
            self.icon.showMessage(self.app_name, problem, QSystemTrayIcon.MessageIcon.Warning)
            self.refresh()
            return
        self.settings.set_auto_add_folder(path)
        self.icon.showMessage(self.app_name, _('Books you put in {} will move into your library.').format(os.path.basename(os.path.normpath(path))))
        self.keeper.restart()
        self.refresh()

    def quit(self) -> None:
        self.icon.hide()
        self.keeper.shutdown()
        self.quit_app()

    # }}}

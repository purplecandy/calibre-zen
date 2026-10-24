#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Preferences -> Sharing over the net: one checkbox for what the server's
address opens, the new web app or calibre's (switch.py).

It sits on the Main tab under "Run server automatically", because that page
is where the server is set up and its note already says a change waits for a
restart, which is when switch.py reads the setting. The choice goes in
gui.json as `zen_web_home`, where the host reads it too. It is written only
when the box is changed, so a page saved for some other reason never pins a
choice the reader did not make, and a later change of switch.DEFAULT still
reaches them. With CALIBRE_ZEN_WEB_HOME set the box shows that and is
disabled: the environment has the last word.

Three wraps, no upstream file edited, all on `server.ConfigWidget`:

    genesis           the page's settings are loaded: add the box
    save_changes      the page is saved, from OK or Restart server: store it
    restore_defaults  Restore defaults: switch.DEFAULT

Off with CALIBRE_ZEN_WEB=0, with the rest of the web app.
"""

import traceback

from calibre.utils.localization import _

_installed = False

TITLE = 'Open the new web app at the server’s address'
NOTE = 'Off: the server’s address opens calibre’s web app. Each app links to the other.'


def install() -> bool:
    "Wrap the Sharing page. Safe to call twice."
    global _installed
    from calibre_zen.web import serve

    if _installed or not serve.enabled():
        return _installed
    from calibre.gui2.preferences import server

    cls = server.ConfigWidget
    orig_genesis, orig_save, orig_restore = cls.genesis, cls.save_changes, cls.restore_defaults

    def genesis(self, gui):
        ans = orig_genesis(self, gui)
        try:
            add_checkbox(self)
        except Exception:
            # The page without our box is still calibre's whole page.
            traceback.print_exc()
        return ans

    def save_changes(self):
        ok = orig_save(self)
        if ok:
            try:
                store(self)
            except Exception:
                traceback.print_exc()
        return ok

    def restore_defaults(self, *args):
        orig_restore(self, *args)
        box = getattr(self, 'zen_web_home', None)
        if box is not None and box.isEnabled():
            from calibre_zen.web import switch

            box.setChecked(switch.DEFAULT == switch.APP)

    cls.genesis, cls.save_changes, cls.restore_defaults = genesis, save_changes, restore_defaults
    _installed = True
    return True


def add_checkbox(page):
    "The box on the Main tab, under Run server automatically, showing what the next start will use."
    from qt.core import QCheckBox

    from calibre_zen.web import switch

    existing = getattr(page, 'zen_web_home', None)
    if existing is not None:
        return existing
    tab = page.main_tab
    box = QCheckBox(_(TITLE), tab)
    box.setObjectName('zenWebHome')
    box.setChecked(switch.home() == switch.APP)
    pinned = switch.from_env()
    if pinned:
        box.setEnabled(False)
        box.setToolTip(_('Set by {0}={1}').format(switch.ENV_VAR, pinned))
    else:
        box.setToolTip(_(NOTE))
    page.zen_web_home_shown = box.isChecked()
    box.stateChanged.connect(page.changed_signal.emit)
    layout = tab.layout()
    at = layout.indexOf(tab.opt_autolaunch_server)
    layout.insertWidget(at + 1 if at > -1 else layout.count(), box)
    page.zen_web_home = box
    return box


def store(page) -> None:
    "Write the box's choice to gui.json, if it was changed."
    from calibre.gui2 import gprefs
    from calibre_zen.web import switch

    box = getattr(page, 'zen_web_home', None)
    if box is None or not box.isEnabled() or box.isChecked() == page.zen_web_home_shown:
        return
    gprefs[switch.PREF_KEY] = switch.APP if box.isChecked() else switch.CALIBRE
    page.zen_web_home_shown = box.isChecked()

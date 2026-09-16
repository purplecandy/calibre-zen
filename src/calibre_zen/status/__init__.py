#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The status bar, rebuilt around what is going on behind the window.

calibre's bar spends its widest column on the version number and the author's
name, and its right-hand end on four widgets put there by four unrelated pieces
of code. Neither is what a status bar is for. The job it should be doing --
what is this window actually showing, and what is the application doing while
you are not looking -- is done here instead:

    library       which library is open; the menu that switches it
    sort          what the list is ordered by, which in Grid mode is written
                  down nowhere else; the menu that changes it
    counts        how many books, how many of them you can see, how many are
                  selected
    device        a connected reader, while there is one
    message       whatever calibre wanted to say, for as long as it asked

    layout        calibre's own toggles and Layout button, moved, not rebuilt
    server        whether the content server is up, and the switch for it
    jobs          how many background jobs, and how far through they are

Every one of those is either a reading or a control calibre already had. The
version and the attribution are not dropped -- they are in Help -> About, which
is where a version number is looked for.

Six wraps, all from outside, no upstream file edited:

`LayoutMixin.finalize_layout`
    Runs after `read_settings` has placed the layout buttons and before the
    window is shown (`ui.py:457`), which makes it the first moment the bar is
    complete enough to take over.

`LayoutMixin.place_layout_buttons`
    Rebuilds the layout-toggle run whenever the window changes shape
    (`init.py:602`), putting the buttons back into the status bar. Adoption
    simply runs again afterwards.

`StatusBar._set_label`
    The single place upstream composes the bar's text (`init.py:228`), so it
    is the single place to intercept: the counts go to our reading and the
    version label is emptied.

`StatusBar.showMessage` / `StatusBar.clearMessage`
    `QStatusBar` shows a transient message by hiding every non-permanent
    widget it holds. With one widget holding the whole bar that would blank
    it, so messages are routed to a label of our own instead. Wrapping the Qt
    methods rather than calibre's `show_message` leaves the tray-notification
    half of that function untouched.

`Main.set_window_title`
    Called whenever the library or its restrictions change
    (`ui.py:1175`), which is exactly when the library name and the sort order
    need re-reading.

`ConnectShareAction.content_server_state_changed`
    The callback the server itself drives (`ui.py:583`), so the segment
    follows a server started from anywhere -- the menu, the command line, or
    `autolaunch_server` at startup.

Off with `CALIBRE_ZEN_STATUS=0`, which gives calibre's bar back exactly.
"""

import os

_installed = False


def enabled() -> bool:
    return os.environ.get('CALIBRE_ZEN_STATUS', '1') not in ('0', 'false', 'no', 'off')


def install() -> bool:
    """
    Wrap the six above. Safe to call twice.

    Nothing is built here: the bar is built in `finalize_layout`, because
    before that the widgets it adopts do not exist.
    """
    global _installed
    if _installed or not enabled():
        return _installed
    import traceback

    from calibre.gui2.actions.device import ConnectShareAction
    from calibre.gui2.init import LayoutMixin, StatusBar
    from calibre.gui2.ui import Main
    from calibre_zen.status.bar import ZenStatusBar

    orig_finalize = LayoutMixin.finalize_layout
    orig_place = LayoutMixin.place_layout_buttons
    orig_set_label = StatusBar._set_label
    orig_show_message = StatusBar.showMessage
    orig_clear_message = StatusBar.clearMessage
    orig_title = Main.set_window_title
    orig_server_state = ConnectShareAction.content_server_state_changed

    def ours(obj):
        "Our widget, reachable from the main window or from the status bar."
        return getattr(obj, 'zen_status', None)

    def finalize_layout(self):
        ans = orig_finalize(self)
        try:
            bar = ZenStatusBar(self)
            self.zen_status = bar
            self.status_bar.zen_status = bar
            # The version label stays -- it is what `_set_label` writes to, and
            # removing it would mean patching that too -- but it says nothing.
            self.status_bar.defmsg.setVisible(False)
            self.status_bar.addPermanentWidget(bar, 1)
            bar.attach()
        except Exception:
            # A window with calibre's own status bar is a working window. A
            # window with no status bar is not.
            traceback.print_exc()
        return ans

    def place_layout_buttons(self):
        ans = orig_place(self)
        bar = ours(self)
        if bar is not None:
            try:
                bar.adopt_tools()
            except Exception:
                traceback.print_exc()
        return ans

    def _set_label(self):
        bar = ours(self)
        if bar is None:
            return orig_set_label(self)
        self.defmsg.setText('')
        bar.update_state(self.library_total, self.total, self.current, self.selected, self.device_string)
        # Upstream clears the transient message here too: a count that has
        # moved means whatever was being announced is no longer the news.
        self.clearMessage()

    def showMessage(self, msg, timeout=0):  # noqa: N802  (matching the Qt name is the point)
        bar = ours(self)
        if bar is None:
            return orig_show_message(self, msg, timeout)
        bar.show_message(msg, timeout)

    def clearMessage(self):  # noqa: N802  (matching the Qt name is the point)
        bar = ours(self)
        if bar is None:
            return orig_clear_message(self)
        bar.clear_message()

    def set_window_title(self):
        ans = orig_title(self)
        bar = ours(self)
        if bar is not None:
            try:
                bar.library.refresh()
                bar.sort.refresh()
            except Exception:
                traceback.print_exc()
        return ans

    def content_server_state_changed(self, running):
        ans = orig_server_state(self, running)
        bar = ours(getattr(self, 'gui', None))
        if bar is not None:
            try:
                bar.server.refresh()
            except Exception:
                traceback.print_exc()
        return ans

    try:
        LayoutMixin.finalize_layout = finalize_layout
        LayoutMixin.place_layout_buttons = place_layout_buttons
        StatusBar._set_label = _set_label
        StatusBar.showMessage = showMessage
        StatusBar.clearMessage = clearMessage
        Main.set_window_title = set_window_title
        ConnectShareAction.content_server_state_changed = content_server_state_changed
    except AttributeError, TypeError:
        return False
    _installed = True
    return True

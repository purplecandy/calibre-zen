#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Which parts of the overlay are on, and the toolbar menu that says so.

Every replaceable part of the overlay -- the filter panel, the centre, the
status bar, the icons, the split buttons, the rounded popups -- has had an
environment variable since it was written, because the way to judge a change
is to run it beside the stock behaviour. A reader does not have an
environment; they have a toolbar. This is the same set of switches as a menu
under the application's own mark, sitting before Preferences: a tick per part,
and a Restart entry once anything has been changed.

The rule for what wins is the one the scheme and the grid density already
use: the environment first, then the stored choice, then on. A variable that
is set pins its entry in the menu, because a setting the menu cannot actually
change should not look like one it can.

None of these parts can be turned off in a running window -- each installs
by wrapping methods once, at startup -- so a change here is a promise about
the next start. The menu says so, and offers the restart.
"""

import os
from typing import NamedTuple

from qt.core import QIcon, QMenu, Qt, QToolButton

PREF_KEY = 'zen_features'
OFF_VALUES = frozenset({'0', 'false', 'no', 'off'})


class Feature(NamedTuple):
    key: str  # the module's name, as hooks.py and report/guard.py know it
    env: str  # the variable that has always switched it
    title: str  # the menu entry
    note: str  # its tooltip: what turning it off gives back


# Menu order: top of the window to the bottom, then the two that are
# everywhere at once.
FEATURES = (
    Feature('icons', 'CALIBRE_ZEN_ICONS', 'Line icons', "One line-drawn icon set. Off: calibre's own colour icons."),
    Feature('filters', 'CALIBRE_ZEN_FILTERS', 'Filter panel', "Flat filter lists you drill into. Off: the Tag browser's tree."),
    Feature('centre', 'CALIBRE_ZEN_CENTRE', 'Preview and table', "A preview above the book list, and the list as a table. Off: calibre's book list."),
    Feature('status', 'CALIBRE_ZEN_STATUS', 'Status bar', "Library, sort, counts, server and jobs in the bar. Off: calibre's status bar."),
    Feature('editor', 'CALIBRE_ZEN_EDITOR', 'Compact editor', "Edit metadata in a smaller window with tabs. Off: calibre's own layouts."),
    Feature('rating', 'CALIBRE_ZEN_RATING', 'Star ratings', "Ratings as five stars you click. Off: calibre's drop-down of stars."),
    Feature('splits', 'CALIBRE_ZEN_SPLIT', 'Split buttons', 'A split tool button lights only the half under the pointer. Off: the whole button lights.'),
    Feature('popups', 'CALIBRE_ZEN_ROUND_POPUPS', 'Rounded menus', 'Menus, tooltips and lists with rounded corners. Off: square windows behind them.'),
)
BY_KEY = {f.key: f for f in FEATURES}

# What this run answered, the first time each part asked. A part reads its
# switch once, at install, and the menu measures the stored choice against
# this to know whether a restart is owed.
_at_start: dict[str, bool] = {}


def from_env(env: str) -> bool | None:
    "The environment's answer, or None when the variable is not set."
    value = os.environ.get(env)
    if not value:
        return None
    return value.lower() not in OFF_VALUES


def stored() -> dict:
    "The reader's choices, {key: bool}. Never raises -- gprefs may not exist yet."
    try:
        from calibre.gui2 import gprefs

        value = gprefs.get(PREF_KEY)
    except Exception:
        return {}
    return dict(value) if isinstance(value, dict) else {}


def wanted(key: str) -> bool:
    "What the next start will use: the environment first, then the stored choice, then on."
    env = from_env(BY_KEY[key].env)
    if env is not None:
        return env
    return bool(stored().get(key, True))


def enabled(key: str) -> bool:
    "What this run uses. Decided once per part, the first time it is asked."
    ans = _at_start.get(key)
    if ans is None:
        ans = _at_start[key] = wanted(key)
    return ans


def pinned(key: str) -> bool:
    "Whether the environment has the last word, so the menu cannot."
    return from_env(BY_KEY[key].env) is not None


def set_wanted(key: str, on: bool) -> None:
    "Store a choice for the next start. On is the default, so on is stored as absence."
    from calibre.gui2 import gprefs

    choices = stored()
    if on:
        choices.pop(key, None)
    else:
        choices[key] = False
    gprefs[PREF_KEY] = choices


def pending() -> list[str]:
    "The parts whose stored choice differs from what this run is doing."
    return [f.key for f in FEATURES if f.key in _at_start and wanted(f.key) != _at_start[f.key]]


class FeaturesButton(QToolButton):
    """
    The application's mark on the toolbar, opening the switches.

    Built the same way as the appearance button beside it: a QToolButton with
    an instant-popup menu, re-synced each time the menu is about to show so
    the ticks are never stale.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('zenFeaturesButton')
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        from calibre.constants import zen_display_name

        self.setText(zen_display_name)
        self.setToolTip(_('%s: which parts are on') % zen_display_name)
        icon = QIcon.ic('lt.png')
        if icon.isNull():
            self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        else:
            self.setIcon(icon)

        self.menu_ = QMenu(self)
        self.menu_.setToolTipsVisible(True)
        self.actions_ = {}
        for feature in FEATURES:
            action = self.menu_.addAction(_(feature.title))
            action.setCheckable(True)
            action.setData(feature.key)
            action.triggered.connect(lambda checked=False, k=feature.key: self.toggle(k, checked))
            self.actions_[feature.key] = action
        self.menu_.addSeparator()
        self.restart_action = self.menu_.addAction(_('Restart to apply'))
        self.restart_action.triggered.connect(self.restart)
        self.setMenu(self.menu_)
        self.menu_.aboutToShow.connect(self.sync)
        self.sync()

    def sync(self) -> None:
        "Ticks from the stored choices, pins from the environment, Restart from the difference."
        for key, action in self.actions_.items():
            feature = BY_KEY[key]
            action.setChecked(wanted(key))
            if pinned(key):
                action.setEnabled(False)
                action.setToolTip(_('Set by %s in the environment') % feature.env)
            else:
                action.setEnabled(True)
                action.setToolTip(_(feature.note))
        owed = pending()
        self.restart_action.setEnabled(bool(owed))
        if owed:
            names = ', '.join(_(BY_KEY[k].title) for k in owed)
            self.restart_action.setText(_('Restart to apply: %s') % names)
        else:
            self.restart_action.setText(_('Restart to apply'))

    def toggle(self, key: str, on: bool) -> None:
        set_wanted(key, on)
        self.sync()
        try:
            from calibre.gui2.ui import get_gui

            gui = get_gui()
            if gui is not None:
                title = _(BY_KEY[key].title)
                msg = _('%s will be on after a restart') if wanted(key) else _('%s will be off after a restart')
                gui.status_bar.show_message(msg % title, 5000)
        except Exception:
            # A missing message is not worth more than the toggle it reports.
            pass

    def restart(self) -> None:
        from calibre.gui2.ui import get_gui

        gui = get_gui()
        if gui is not None:
            gui.quit(restart=True)

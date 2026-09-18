#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Light, dark, or whatever the system is doing -- and which set of colours to be
light or dark in -- on the toolbar.

calibre has had the setting all along: `gprefs['color_palette']` is
`'system'`, `'light'` or `'dark'`, and `PaletteManager.refresh_palette()`
re-reads it and applies it to a running window. What it has not had is a way to
reach it without opening Preferences, choosing a category and finding a combo
box, which is three screens away from a thing people flip when the sun goes
down. This is that setting, one click from the toolbar; nothing about how the
palette is chosen or applied is reimplemented.

The switch is genuinely live because `refresh_palette()` ends in
`on_palette_change()`, which the overlay already wraps to re-render its
stylesheet for whatever palette is now installed.

The same menu carries the colour schemes (`tokens/schemes.py`). That half is
ours rather than calibre's, but it applies through the identical path:
`refresh_palette()` rebuilds the palette from the functions the overlay
installed as `default_{dark,light}_palette`, so choosing a scheme and choosing
a mode are the same operation with a different input.

Icons were the one thing that did not survive it, and the fix is in
`icons/render.py` rather than here: an icon used to be a photograph taken in
the colour of the theme that was on when a QAction first asked for it, so after
a switch the whole toolbar was inked for the theme you just left. Measured, not
guessed -- a held icon stayed (31, 35, 40) against a #24262a window.
"""

from qt.core import QActionGroup, QMenu, QSizePolicy, Qt, QToolButton, QWidget

from calibre_zen.theme.tokens import schemes

_installed = False

# Value in gprefs, what the menu calls it, and the glyph. 'system' first
# because it is the default and the one that needs no thought.
# Lightest to darkest after the default. 'dim' is not a value calibre's
# preference takes -- see apply().
MODES = (
    ('system', 'Match system', 'device-desktop'),
    ('light', 'Light', 'sun'),
    ('dim', 'Dim', 'brightness-half'),
    ('dark', 'Dark', 'moon'),
)


def current() -> str:
    from calibre.gui2 import gprefs

    value = gprefs['color_palette']
    if value == 'dark':
        return 'dim' if schemes.darkness() == 'dim' else 'dark'
    return value if value in ('system', 'light') else 'system'


def _devtools_enabled() -> bool:
    "CALIBRE_ZEN_DEVTOOLS=1: a Developer submenu that crashes on purpose, see report/devmenu.py."
    import os

    return os.environ.get('CALIBRE_ZEN_DEVTOOLS', '') in ('1', 'true', 'yes', 'on')


def glyph_for(mode: str) -> str:
    return next((g for m, _label, g in MODES if m == mode), 'device-desktop')


def repaint() -> None:
    """
    Re-theme the running window.

    `refresh_palette()` re-reads the mode, rebuilds the palette from
    `default_{dark,light}_palette` -- which are ours -- and ends in
    `on_palette_change()`, which the overlay wraps to re-render its sheet. So
    it is the whole of applying either choice, and there is nothing here that
    knows how a colour reaches a widget.
    """
    from calibre.gui2 import qapplication_or_fail

    qapplication_or_fail().palette_manager.refresh_palette()


def apply(mode: str) -> None:
    """
    Store the light/dark/dim choice and re-theme the running window.

    Dim is ours, and it is still `color_palette = 'dark'` as far as calibre is
    concerned -- which is the point. `is_dark_theme`, the palette editor and
    everything downstream of them keep working, and the only thing that changes
    is which dark palette `default_dark_palette` hands back.
    """
    from calibre.gui2 import gprefs

    if mode not in {m[0] for m in MODES} or mode == current():
        return
    if mode in schemes.DARKNESS:
        schemes.set_darkness(mode)
        gprefs['color_palette'] = 'dark'
    else:
        gprefs['color_palette'] = mode
    repaint()


def apply_scheme(name: str) -> None:
    "Store the colour-scheme choice and re-theme the running window."
    if schemes.set_active(name):
        repaint()


class ThemeButton(QToolButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('zenThemeButton')
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_ = QMenu(self)
        self.group = QActionGroup(self)
        self.group.setExclusive(True)
        for mode, label, _glyph in MODES:
            action = self.menu_.addAction(_(label))
            action.setCheckable(True)
            action.setData(mode)
            self.group.addAction(action)
            action.triggered.connect(lambda _checked=False, m=mode: apply(m))

        # The schemes go one level down. The job this menu is opened for is
        # flipping light and dark; a scheme is chosen once and then left, and
        # six of them inline would bury the three that are not.
        self.menu_.addSeparator()
        self.scheme_menu = self.menu_.addMenu(_('Colour scheme'))
        self.scheme_group = QActionGroup(self)
        self.scheme_group.setExclusive(True)
        for scheme in schemes.SCHEMES.values():
            action = self.scheme_menu.addAction(_(scheme.title))
            action.setCheckable(True)
            action.setData(scheme.name)
            action.setToolTip(_(scheme.note))
            self.scheme_group.addAction(action)
            action.triggered.connect(lambda _checked=False, n=scheme.name: apply_scheme(n))
        if _devtools_enabled():
            from calibre_zen.report import devmenu

            self.menu_.addSeparator()
            devmenu.attach(self.menu_)
        self.setMenu(self.menu_)
        self.menu_.aboutToShow.connect(self.sync)
        self.scheme_menu.aboutToShow.connect(self.sync)
        self.sync()

        from calibre.gui2 import qapplication_or_fail

        qapplication_or_fail().palette_changed.connect(self.sync, type=Qt.ConnectionType.QueuedConnection)

    def sync(self) -> None:
        "Point the button and both ticks at whatever the settings say now."
        mode = current()
        for action in self.group.actions():
            action.setChecked(action.data() == mode)
        scheme = schemes.active().name
        for action in self.scheme_group.actions():
            action.setChecked(action.data() == scheme)
        label = next((label for m, label, _g in MODES if m == mode), mode)
        self.setText(_(label))
        self.setToolTip(_('Appearance: %s, %s') % (_(label), _(schemes.active().title)))
        icon = self.icon_for(glyph_for(mode))
        if icon is None:
            # No icon pack, so the button has to say what it is in words or it
            # is a blank square on an icon-only toolbar.
            self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        else:
            self.setIcon(icon)

    def icon_for(self, glyph: str):
        from calibre_zen.icons import registry

        ans = registry.glyph_icon(glyph)
        return None if ans is None or ans.isNull() else ans


# The buttons that are about the application rather than about the books in
# it. They belong at the far end of the bar, away from the ones that act on a
# selection -- which is the difference between a toolbar you read left to right
# and a row of seventeen icons.
TRAILING = frozenset({'Preferences', 'Help'})


def trailing_start(bar, gui) -> int:
    """
    Where the run of app-level buttons at the end of the bar begins.

    Read off the bar rather than off the preference, because the reader is
    free to arrange their own toolbar: if they have moved Preferences into the
    middle, there is no trailing run and the answer is the end of the bar --
    which pushes nothing but our own button over, and leaves their arrangement
    exactly as they left it.
    """
    names = {iaction.qaction: name for name, iaction in (getattr(gui, 'iactions', None) or {}).items()}
    actions = list(bar.actions())
    index = len(actions)
    while index > 0:
        ac = actions[index - 1]
        if ac.isSeparator() or names.get(ac) in TRAILING:
            index -= 1
            continue
        break
    return index


def add_spacer(bar, gui) -> None:
    "Push the app-level run to the right-hand end of the toolbar."
    spacer = QWidget(bar)
    spacer.setObjectName('zenToolbarSpacer')
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    actions = list(bar.actions())
    index = trailing_start(bar, gui)
    if index >= len(actions):
        bar.addWidget(spacer)
    else:
        bar.insertWidget(actions[index], spacer)


def install() -> bool:
    """
    Put the button at the end of both main toolbars, and a stretch before it.

    `BarsManager.init_bars` clears and refills them whenever the toolbar
    preferences change (`bars.py:778-787`), so both are added there rather
    than once: anything appended outside that call disappears the first time a
    reader edits their toolbar.

    The stretch goes in after `init_bar` has finished, which is also after it
    has recorded `preferred_width` -- so the width the bar compares against
    when deciding whether to drop its labels is still the width of the buttons
    alone, and an expanding spacer does not convince it that it is crowded.
    """
    global _installed
    if _installed:
        return True
    from calibre.gui2.bars import BarsManager

    orig_init_bars = BarsManager.init_bars

    def init_bars(self):
        ans = orig_init_bars(self)
        try:
            for bar in self.main_bars:
                add_spacer(bar, self.gui)
                bar.addWidget(ThemeButton(bar))
        except Exception:
            import traceback

            traceback.print_exc()
        return ans

    try:
        BarsManager.init_bars = init_bars
    except AttributeError, TypeError:
        return False
    _installed = True
    return True

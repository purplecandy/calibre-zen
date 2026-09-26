#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The one place the overlay attaches to calibre.

Everything the overlay does to a stock calibre happens in `install()`, from a
single call in calibre.gui2.Application.__init__. Nothing else upstream knows
the overlay exists, which is the whole point: `git pull` cannot conflict with
code that is not there.

What is patched, and why it is patched rather than edited:

    palette.default_{dark,light}_palette
        Module-level functions, looked up by name at call time. Replacing the
        attributes replaces the theme everywhere calibre asks for one --
        including the palette editor in Preferences, which uses them as the
        base a custom palette is edited from.

    PaletteManager.on_palette_change
        The one place calibre sets an application-wide stylesheet. We let it
        run, but swap our generated sheet in for the one it was going to
        install, so the palette_changed signal still fires exactly once and
        with the finished sheet already applied.

    PaletteManager.tree_view_hover_style
        A widget-local sheet calibre hands to the tag browser and friends.

    QWidget.setStyleSheet / QWidget.setFont
        Wrapped, not replaced -- see theme/rewrite.py. A widget-local sheet
        already beats the app sheet; a widget's own setFont() does not, which
        rewrite.contain_fonts() fixes by mirroring it into one.

    IconResourceManager.__call__ / QPushButton.__init__ / QPushButton.setIcon
        Wrapped -- see theme/variants.py. Qt has no "this button is
        destructive" signal, so a button that receives a known-dangerous icon
        gets tagged instead, for 02-buttons.qss to style.

    TagBrowserWidget.__init__ / TagsView.{set_database, indexAt,
    show_item_at_index}
        Wrapped -- see filters/. The tag browser's tree is hidden and a flat
        filter panel put in its place, reading the same TagsModel.
        CALIBRE_ZEN_FILTERS=0.

    BarsManager.init_bars
        Wrapped -- see theme/appearance.py. Puts a light/dark switcher and the
        colour schemes on the toolbar, driving the colour_palette preference
        calibre already has and our own scheme preference, and pushes the
        app-level buttons to the far end of the bar. The same wrap puts the
        overlay's own menu (features.py) before Preferences: a tick per
        replaceable part, stored for the next start, since each part reads
        its switch once at install.

    ToolBar.setup_tool_button / SearchToolBar.setup_tool_button
        Wrapped -- see theme/splits.py. A split button carries two targets in
        one skin and calibre draws it exactly like a button that carries one;
        this tracks which half the pointer is on so the sheet can say.
        CALIBRE_ZEN_SPLIT=0.

    LayoutMixin.finalize_layout / LayoutMixin.place_layout_buttons /
    StatusBar._set_label / Main.set_window_title /
    ConnectShareAction.content_server_state_changed
        Wrapped -- see status/. The status bar rebuilt around what is going on
        behind the window: which library, how it is sorted, whether the content
        server is up, and what the background jobs are doing.
        CALIBRE_ZEN_STATUS=0.

    wizard.FinishPage / Wizard.{__init__, set_finish_text}
        Rebound and wrapped -- see onboarding/. The welcome wizard's last page
        replaced with one page per layout change: a title, one line, and a
        recording of the window with it in use; the header loses its corner
        icon and its subtitle indent. CALIBRE_ZEN_ONBOARDING=0.

    Completer.__init__ / Completer.popup, and an application-wide filter
        See theme/dropdowns.py. A combo box's list and calibre's autocomplete
        list, dressed like the menus: a combo box on Fusion's menu delegate
        gets a styled one, and the autocomplete list -- which none of the app
        sheet reaches -- carries its own and has its height corrected.

    comments_editor.create_flow_toolbar / Editor.__init__
        Rebound and wrapped -- see theme/richtext.py. The rich text editor's
        toolbar on one line, and the editor marked so the sheet can give it one
        border instead of three.

    an application-wide event filter, twice
        See theme/popups.py, and icons/render.py's MenuPaintWatch: Qt asks a
        glyph for its Active mode both for a highlighted menu item and for a
        hovered tool button, and only the first is on the accent, so the span
        of a QMenu's paint is marked and Active flips the ink only inside it.

    an application-wide event filter
        See theme/popups.py. A menu, a tooltip and a combo box's list are
        windows of their own, so a radius in the sheet rounds what is drawn and
        leaves the window behind it square. They are made translucent as they
        are polished. CALIBRE_ZEN_ROUND_POPUPS=0.

    CentralContainer.initialize_with_gui / BooksView.{get_old_state,
    write_state, database_changed, do_row_sizing} / TableView.set_delegates /
    BooksModel.headerData
        Wrapped -- see centre/. A preview above the book list, calibre's search
        bar and a Grid/Table switcher between them, and the list itself drawn
        as a modern table with a composite Details column.
        CALIBRE_ZEN_CENTRE=0.

    MainWindow.unhandled_exception / main_window.error_dialog /
    threading.excepthook / Main.initialize
        Wrapped -- see report/. An unhandled exception with one of our frames
        on the stack gets a Send report button on the dialog calibre already
        shows; one without is left alone. A module that fails to install is
        switched off for the session instead of taking the rest down, and is
        offered for sending once there is a window. CALIBRE_ZEN_REPORT=0.

    single.editors / EditMetadataTab.register
        Added to and wrapped -- see editor/. The Edit metadata dialog laid out
        compact: tabs, one field per row, sorts folded away. One more entry in
        the table calibre already picks its layouts from, made the default.
        CALIBRE_ZEN_EDITOR=0.

    RatingEditor.{__init__, paintEvent, mouse*, keyPressEvent, wheelEvent,
    showPopup, sizeHint}
        Wrapped -- see rating.py. calibre's one rating widget, a drop-down of
        star characters, drawn as five stars you click, everywhere it is used.
        CALIBRE_ZEN_RATING=0.

    DateTimeEdit.__init__ / CalendarWidget.paintCell
        Wrapped -- see dates.py. The calendar every calibre date field opens,
        drawn in the theme, with Today and Clear under it.
        CALIBRE_ZEN_DATES=0.

    CheckForUpdates.run / Main.update_found / update.get_download_url
        Wrapped -- see update.py. The daily check reads this fork's release
        feed instead of calibre's server, and the status-bar notice and the
        dialog name the fork's release and open its page. calibre's check
        offered its users a calibre they could not install over this.
        CALIBRE_ZEN_UPDATE=0.

Off with CALIBRE_ZEN_STYLE=0, which is what makes before/after comparable.
"""

import os

from calibre_zen import centre, dates, devtools, editor, filters, onboarding, rating, report, status, update
from calibre_zen.icons import registry as icon_registry
from calibre_zen.report import guard
from calibre_zen.theme import appearance, dropdowns, generate, popups, rewrite, richtext, splits, variants

_installed = False


def enabled() -> bool:
    return os.environ.get('CALIBRE_ZEN_STYLE', '1') not in ('0', 'false', 'no', 'off')


def install() -> bool:
    """
    Apply the overlay. Call once, after PaletteManager exists and before it
    sets up styles -- which is to say, from Application.__init__.

    Returns whether the overlay is active. Safe to call twice.
    """
    global _installed
    if _installed or not enabled():
        return _installed
    from calibre.gui2 import palette as palette_mod

    palette_mod.default_dark_palette = generate.dark_palette
    palette_mod.default_light_palette = generate.light_palette

    pm = palette_mod.PaletteManager
    _patch_palette_manager(pm)
    _patch_toolbar_icon_size()
    _patch_toolbar_layout()
    _patch_preferences_menu()
    _patch_library_action()
    _patch_window_title()
    rewrite.install()
    rewrite.contain_fonts()
    icon_registry.install()
    variants.install()
    _installed = True
    return True


def _patch_window_title() -> None:
    """Show the display name in the title bar, not the identity.

    calibre titles its main window ``'<__appname__> — || <library> ||'``
    (``gui2/ui.py``, ``set_window_title``) and, before a library is open, just
    ``__appname__`` (``gui2/layout.py``). ``__appname__`` is ``calibre-zen`` and
    has to stay so: the config directory, the lock and the socket derive from
    it. What a person reads is ``zen_display_name``. Wrapping ``setWindowTitle``
    on the main window catches both call sites without touching either.
    """
    from calibre.constants import __appname__, zen_display_name
    from calibre.gui2.ui import Main

    orig = Main.setWindowTitle

    def setWindowTitle(self, title):
        if title.startswith(__appname__):
            title = zen_display_name + title[len(__appname__) :]
        return orig(self, title)

    Main.setWindowTitle = setWindowTitle


def _patch_toolbar_layout() -> None:
    """
    Put Preferences on the main toolbar.

    The only change the overlay makes to what is in the UI rather than to how it
    looks, and it is a small one: PreferencesAction already exists, already has
    its whole dropdown, and is already on the menu bar -- it is simply not in the
    toolbar's default layout. Nothing new is built here.

    Changing the *default* rather than the setting is what keeps it honest: a
    user who has arranged their own toolbar keeps it, and anyone who does not
    want this one removes it in Preferences -> Toolbars & menus like any other
    button.
    """
    from calibre.gui2 import gprefs

    for key in ('action-layout-toolbar', 'action-layout-toolbar-device'):
        current = tuple(gprefs.defaults.get(key) or ())
        if not current or 'Preferences' in current:
            continue
        # A separator first: it belongs with the other lone button at the end,
        # not with the group before it.
        gprefs.defaults[key] = current + (None, 'Preferences')


# The Preferences menu's five category submenus are all drawn with the same
# gear upstream, which next to a gear button opening a gear menu is a lot of
# gear. Keys are the untranslated category names.
PREFERENCE_CATEGORY_GLYPHS = {
    'Interface': 'layout',
    'Conversion': 'transform',
    'Import/Export': 'transfer',
    'Sharing': 'share',
    'Advanced': 'tool',
}


# The Choose library button. Upstream draws it with lt.png, calibre's logo,
# which the pack leaves unmapped so the window and the taskbar carry the
# fork's mark; the button that opens a library is a shelf of books, like the
# rest of the toolbar is line glyphs.
LIBRARY_GLYPH = 'books'


def _patch_library_action() -> None:
    """
    Give the Choose library action a glyph instead of the logo.

    Its action_spec names lt.png, and genesis() captures whatever icon the
    button has at that moment as ``original_library_icon`` and as the default
    for every library in the switch list without an icon of its own. Setting
    ours just before genesis means those captures take the glyph too, so
    "Remove current icon" comes back to it and the list stays consistent. A
    library icon the user chose is untouched: that path never reads the
    default.
    """
    from calibre.gui2.actions.choose_library import ChooseLibraryAction

    orig = ChooseLibraryAction.genesis

    def genesis(self):
        try:
            _reicon_library_action(self)
        except Exception:
            # Cosmetic. It must never be the reason the library menu fails to build.
            pass
        orig(self)

    ChooseLibraryAction.genesis = genesis


def _reicon_library_action(action) -> None:
    from calibre_zen.icons import registry

    icon = registry.glyph_icon(LIBRARY_GLYPH)
    if icon is None:
        return
    # The toolbar button, and its clone in the menu ("Switch/create library"),
    # which create_action copies the icon into rather than sharing it.
    action.qaction.setIcon(icon)
    clone = getattr(action, 'menuless_qaction', None)
    if clone is not None:
        clone.setIcon(icon)


def _patch_preferences_menu() -> None:
    from calibre.gui2.actions.preferences import PreferencesAction

    orig = PreferencesAction.initialization_complete

    def initialization_complete(self):
        orig(self)
        try:
            _reicon_preference_categories(self.preferences_menu)
        except Exception:
            # Cosmetic. It must never be the reason a menu fails to build.
            pass

    PreferencesAction.initialization_complete = initialization_complete


def _reicon_preference_categories(menu) -> None:
    """
    Give each category submenu its own icon.

    Upstream builds the submenus in category order and gives every one of them
    config.png, so there is nothing in the finished menu to tell them apart by:
    the categories are recovered by walking the plugins in the same order
    upstream does and pairing them with the submenus in the order they were
    added. If that pairing does not line up -- a plugin added a category, say --
    nothing is touched.
    """
    from calibre.customize.ui import preferences_plugins
    from calibre_zen.icons import registry

    categories = []
    for p in sorted(preferences_plugins(), key=lambda p: p.category_order * 100 + p.name_order):
        if p.category not in categories:
            categories.append(p.category)
    submenus = [a for a in menu.actions() if a.menu() is not None]
    if len(submenus) != len(categories):
        return
    for action, category in zip(submenus, categories):
        glyph = PREFERENCE_CATEGORY_GLYPHS.get(category)
        ans = registry.glyph_icon(glyph) if glyph else None
        if ans is not None:
            action.setIcon(ans)


def _patch_toolbar_icon_size() -> None:
    """
    Re-scale the toolbar.

    calibre's five icon-size settings map to 0/24/30/48/64 px, a scale drawn for
    detailed colour icons; a line icon at 48px is a diagram. The sizes are
    hard-coded in BarsManager.apply_settings rather than being a preference, so
    the size has to be set after that runs. The user's setting is still what
    chooses, only the scale under it changes.
    """
    from qt.core import QSize, Qt

    from calibre.gui2.bars import BarsManager, ToolBar
    from calibre_zen.theme.tokens import components

    orig = BarsManager.apply_settings
    orig_text_style = ToolBar.get_text_style

    def apply_settings(self):
        orig(self)
        from calibre.gui2 import gprefs

        px = components.TOOLBAR_ICON_SIZE.get(gprefs['toolbar_icon_size'])
        if px is None:
            return
        size = QSize(px, px)
        style = None if components.TOOLBAR_LABELS else Qt.ToolButtonStyle.ToolButtonIconOnly
        for bar in self.bars:
            bar.setIconSize(size)
            if style is not None:
                bar.setToolButtonStyle(style)
            if getattr(bar, 'donate_button', None) is not None:
                bar.donate_button.setIconSize(size)
                if style is not None:
                    bar.donate_button.setToolButtonStyle(style)

    def get_text_style(self):
        # ToolBar re-decides this on every resize, so setting the style once
        # from apply_settings would last until the window was dragged.
        if components.TOOLBAR_LABELS:
            return orig_text_style(self)
        return Qt.ToolButtonStyle.ToolButtonIconOnly

    BarsManager.apply_settings = apply_settings
    ToolBar.get_text_style = get_text_style


def _patch_palette_manager(pm) -> None:
    orig_on_palette_change = pm.on_palette_change

    def on_palette_change(self):
        from calibre.gui2 import qapplication_or_fail

        app = qapplication_or_fail()
        # The first call is the earliest point at which the QApplication exists
        # -- fonts, like devtools, need a live one to register against. So
        # does the filter panel: importing calibre.gui2.tag_browser.ui pulls in
        # calibre.gui2.dialogs.tag_categories, which evaluates QIcon.ic() in a
        # class body at import time -- before this point, that call finds no
        # QApplication at all and raises. Checked empirically, not assumed:
        # the earlier, eager import crashed exactly this way.
        # Each guarded: one that raises is switched off for the session and the
        # rest still install (report/guard.py). The reporter goes first so a
        # failure in any of the others can be offered for sending later.
        guard.run_install('report', report.install)
        guard.run_install('devtools', devtools.install)
        guard.run_install('fonts', _install_fonts)
        guard.run_install('popups', popups.install)
        guard.run_install('dropdowns', dropdowns.install)
        guard.run_install('richtext', richtext.install)
        guard.run_install('menu-ink', _install_menu_ink)
        guard.run_install('splits', splits.install)
        guard.run_install('filters', filters.install)
        guard.run_install('centre', centre.install)
        guard.run_install('status', status.install)
        guard.run_install('editor', editor.install)
        guard.run_install('rating', rating.install)
        guard.run_install('dates', dates.install)
        guard.run_install('appearance', appearance.install)
        guard.run_install('update', update.install)
        guard.run_install('onboarding', onboarding.install)
        if not self.using_calibre_style:
            # calibre is deferring to the platform style; so do we. Our sheet
            # is written for Fusion and would fight the native one.
            return orig_on_palette_change(self)
        check_fusion(app)
        set_stylesheet = type(app).setStyleSheet
        applied = []

        def shim(_sheet_upstream_wanted):
            applied.append(True)
            set_stylesheet(app, generate.stylesheet(app.palette(), self.is_dark_theme))

        # Upstream computes is_dark_theme, then sets its sheet, then emits
        # palette_changed. Standing in for that one call keeps all three in the
        # right order and applies the sheet exactly once.
        try:
            app.setStyleSheet = shim
        except AttributeError, TypeError:
            shim = None
        try:
            orig_on_palette_change(self)
        finally:
            if shim is not None:
                try:
                    del app.setStyleSheet
                except AttributeError:
                    pass
        if not applied:
            set_stylesheet(app, generate.stylesheet(app.palette(), self.is_dark_theme))

    def tree_view_hover_style(self):
        from calibre.gui2 import qapplication_or_fail

        return generate.local_stylesheet('treeview-hover', qapplication_or_fail().palette(), self.is_dark_theme)

    pm.on_palette_change = on_palette_change
    pm.tree_view_hover_style = tree_view_hover_style


def _install_fonts() -> bool:
    generate.install_fonts()
    return True


def _install_menu_ink() -> bool:
    "icons/render.py: the watch that tells a highlighted menu item's glyph from a hovered button's."
    from calibre_zen.icons import render

    return render.install()


def check_fusion(app) -> bool:
    """
    The sheet is written for Fusion: it assumes Fusion's subcontrol layout and
    that every unstyled widget stays consistent with the styled ones.

    calibre pins Fusion already -- CalibreStyle is a QProxyStyle over it -- so
    there is nothing to set here, and setting one would replace CalibreStyle and
    take its scrollbar and icon behaviour with it. This only reports, and only
    when it can see a style that positively is not Fusion: CalibreStyle itself
    comes back from Qt unnamed and not introspectable from Python.
    """
    style = app.style()
    if style is None:
        return False
    names = [style.objectName()]
    base = getattr(style, 'baseStyle', None)
    if callable(base):
        b = base()
        if b is not None:
            names.append(b.objectName())
    names = [n.lower() for n in names if n]
    if not names:
        return True
    if not any('fusion' in n for n in names):
        from calibre.constants import DEBUG

        if DEBUG:
            print('calibre-zen: expected a Fusion-based style, got', names)
        return False
    return True

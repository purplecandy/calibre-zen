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

Off with CALIBRE_ZEN_STYLE=0, which is what makes before/after comparable.
"""

import os

from calibre_zen import devtools
from calibre_zen.icons import registry as icon_registry
from calibre_zen.theme import generate, rewrite, variants

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
    rewrite.install()
    rewrite.contain_fonts()
    icon_registry.install()
    variants.install()
    _installed = True
    return True


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
        # -- fonts, like devtools, need a live one to register against.
        devtools.install()
        generate.install_fonts()
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

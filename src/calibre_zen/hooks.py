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

Off with CALIBRE_ZEN_STYLE=0, which is what makes before/after comparable.
"""

import os

from calibre_zen.theme import generate, rewrite

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
    rewrite.install()
    _installed = True
    return True


def _patch_palette_manager(pm) -> None:
    orig_on_palette_change = pm.on_palette_change

    def on_palette_change(self):
        from calibre.gui2 import qapplication_or_fail

        app = qapplication_or_fail()
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

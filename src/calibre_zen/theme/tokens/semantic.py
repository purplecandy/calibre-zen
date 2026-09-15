#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Semantic tokens: what each primitive is *for*.

Two things live here, and they are different in kind:

`PALETTE_DARK` / `PALETTE_LIGHT` are static maps from a QPalette colour role to
a primitive. They are the theme we ship.

`Chrome` is derived at runtime from whatever palette is actually installed --
ours, or one of the custom palettes calibre lets users define in Preferences.
The stylesheet is written against `Chrome`, never against the maps, so a sepia
palette gets sepia borders and scrollbars instead of stubbornly blue-grey ones.
"""

from qt.core import QColor, QPalette

from calibre_zen.theme.tokens import primitives as p

# Palettes {{{

# Keys are QPalette.ColorRole member names. 'Disabled' is not a role: it is the
# single colour every foreground role collapses to in the disabled group.
PALETTE_DARK = {
    'Window': p.NEUTRAL_DARK[20],
    'WindowText': p.NEUTRAL_DARK[90],
    'Base': p.NEUTRAL_DARK[10],
    'AlternateBase': p.NEUTRAL_DARK[15],
    'Text': p.NEUTRAL_DARK[90],
    'Button': p.NEUTRAL_DARK[25],
    'ButtonText': p.NEUTRAL_DARK[90],
    'PlaceholderText': p.NEUTRAL_DARK[60],
    'BrightText': p.DANGER_ON_DARK,
    # A dark tooltip on a dark UI. The stock pale yellow is the single most
    # dated thing on screen and it is not even legible against dark chrome.
    'ToolTipBase': p.NEUTRAL_DARK[30],
    'ToolTipText': p.NEUTRAL_DARK[90],
    'Link': p.LINK_ON_DARK,
    'LinkVisited': p.VISITED_ON_DARK,
    'Highlight': p.ACCENT,
    'HighlightedText': p.ON_ACCENT,
    'Accent': p.ACCENT,
    # Fusion derives frame and separator colours from these five; left at their
    # defaults they are far lighter than this window colour and every sunken
    # frame glows.
    'Light': p.NEUTRAL_DARK[40],
    'Midlight': p.NEUTRAL_DARK[30],
    'Mid': p.NEUTRAL_DARK[40],
    'Dark': p.NEUTRAL_DARK[5],
    'Shadow': p.NEUTRAL_DARK[0],
    'Disabled': p.NEUTRAL_DARK[60],
}

PALETTE_LIGHT = {
    'Window': p.NEUTRAL_LIGHT[90],
    'WindowText': p.NEUTRAL_LIGHT[15],
    'Base': p.NEUTRAL_LIGHT[100],
    'AlternateBase': p.NEUTRAL_LIGHT[95],
    'Text': p.NEUTRAL_LIGHT[15],
    # A white button on a grey window, rather than a grey button on a grey
    # window: the control well reads as raised without needing a bevel.
    'Button': p.NEUTRAL_LIGHT[100],
    'ButtonText': p.NEUTRAL_LIGHT[15],
    'PlaceholderText': p.NEUTRAL_LIGHT[60],
    'BrightText': p.DANGER_ON_LIGHT,
    # Dark tooltips in the light theme too: a tooltip is an overlay, and every
    # current UI inverts it.
    'ToolTipBase': p.NEUTRAL_LIGHT[18],
    'ToolTipText': p.NEUTRAL_LIGHT[97],
    'Link': p.ACCENT,
    'LinkVisited': p.VISITED_ON_LIGHT,
    'Highlight': p.ACCENT,
    'HighlightedText': p.ON_ACCENT,
    'Accent': p.ACCENT,
    'Light': p.NEUTRAL_LIGHT[100],
    'Midlight': p.NEUTRAL_LIGHT[85],
    'Mid': p.NEUTRAL_LIGHT[65],
    'Dark': p.NEUTRAL_LIGHT[55],
    'Shadow': p.NEUTRAL_LIGHT[40],
    'Disabled': p.NEUTRAL_LIGHT[60],
}

# The foreground roles that go flat grey when a widget is disabled.
DISABLED_ROLES = ('Text', 'ButtonText', 'WindowText', 'HighlightedText')
# }}}


def mix(a: QColor, b: QColor, f: float) -> QColor:
    "Blend f of b into a, in sRGB. Good enough for chrome, not for images."
    g = 1.0 - f
    return QColor(
        round(a.red() * g + b.red() * f),
        round(a.green() * g + b.green() * f),
        round(a.blue() * g + b.blue() * f),
    )


class Chrome:
    """
    Chrome colours derived from whatever palette is in use.

    Every attribute is a CSS colour string, ready to drop into a QSS template.
    """

    def __init__(self, pal: QPalette, is_dark: bool):
        i = 0 if is_dark else 1

        def blend(pair, toward):
            return mix(window, toward, pair[i]).name()

        window = pal.color(QPalette.ColorRole.Window)
        base = pal.color(QPalette.ColorRole.Base)
        text = pal.color(QPalette.ColorRole.WindowText)
        accent = pal.color(QPalette.ColorRole.Highlight)
        button = pal.color(QPalette.ColorRole.Button)

        self.window = window.name()
        self.accent = accent.name()
        self.accent_text = pal.color(QPalette.ColorRole.HighlightedText).name()
        self.alt = pal.color(QPalette.ColorRole.AlternateBase).name()
        self.button = button.name()

        # Borders blend toward the text colour rather than being a fixed grey,
        # so they stay a hairline against any window colour instead of turning
        # into a hard line on light themes and a glow on dark ones.
        self.border = blend(p.MIX_BORDER, text)
        self.border_weak = blend(p.MIX_BORDER_WEAK, text)
        self.border_strong = blend(p.MIX_BORDER_STRONG, text)
        self.muted = blend(p.MIX_MUTED, text)

        self.track = blend(p.MIX_TRACK, text)
        self.scroll = blend(p.MIX_SCROLL, text)
        self.scroll_hover = blend(p.MIX_SCROLL_HOVER, text)
        self.menu_bg = blend(p.MIX_MENU, base)

        self.button_hover = mix(button, text, p.MIX_BUTTON_HOVER[i]).name()
        self.button_pressed = mix(button, text, p.MIX_BUTTON_PRESSED[i]).name()

        rgb = f'{accent.red()}, {accent.green()}, {accent.blue()}'
        self.hover = f'rgba({rgb}, {p.ALPHA_HOVER[i]})'
        self.pressed = f'rgba({rgb}, {p.ALPHA_PRESSED[i]})'
        self.selected_soft = f'rgba({rgb}, {p.ALPHA_SELECTED_INACTIVE[i]})'

        self.tooltip_bg = pal.color(QPalette.ColorRole.ToolTipBase).name()
        self.tooltip_fg = pal.color(QPalette.ColorRole.ToolTipText).name()

    def as_mapping(self) -> dict:
        "The names a QSS template may substitute."
        return {k: v for k, v in vars(self).items() if not k.startswith('_')}

#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Semantic tokens: what each primitive is *for*.

Two things live here, and they are different in kind:

`palette_spec()` hands back the active scheme's map from a QPalette colour role
to a colour. Which scheme that is lives in `schemes.py`; this layer only knows
that there is one.

`Chrome` is derived at runtime from whatever palette is actually installed --
ours, or one of the custom palettes calibre lets users define in Preferences.
The stylesheet is written against `Chrome`, never against a scheme's map, so a
sepia palette gets sepia borders and scrollbars instead of stubbornly
blue-grey ones.
"""

from qt.core import QColor, QPalette

from calibre_zen.theme.tokens import schemes

# Palettes {{{


def palette_spec(is_dark: bool) -> dict:
    """
    The active scheme's role map.

    Keys are QPalette.ColorRole member names. 'Disabled' is not a role: it is
    the single colour every foreground role collapses to in the disabled group.
    """
    return schemes.active().roles(is_dark)


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
    The ratios come from the active scheme's `Blends`; the colours they are
    applied to come from the live palette.
    """

    def __init__(self, pal: QPalette, is_dark: bool):
        i = 0 if is_dark else 1
        scheme = schemes.active()
        b = scheme.blends

        def blend(pair, toward):
            return mix(window, toward, pair[i]).name()

        window = pal.color(QPalette.ColorRole.Window)
        base = pal.color(QPalette.ColorRole.Base)
        text = pal.color(QPalette.ColorRole.WindowText)
        accent = pal.color(QPalette.ColorRole.Highlight)
        accent_text = pal.color(QPalette.ColorRole.HighlightedText)
        button = pal.color(QPalette.ColorRole.Button)

        self.window = window.name()
        self.accent = accent.name()
        self.accent_text = accent_text.name()
        self.alt = pal.color(QPalette.ColorRole.AlternateBase).name()
        self.button = button.name()

        # Borders blend toward the text colour rather than being a fixed grey,
        # so they stay a hairline against any window colour instead of turning
        # into a hard line on light themes and a glow on dark ones.
        self.border = blend(b.border, text)
        self.border_weak = blend(b.border_weak, text)
        self.border_strong = blend(b.border_strong, text)
        self.muted = blend(b.muted, text)

        self.track = blend(b.track, text)
        self.scroll = blend(b.scroll, text)
        self.scroll_hover = blend(b.scroll_hover, text)

        # One surface for everything that floats above the page: a menu, a
        # popover, a row card in the book list. It sits between the window
        # colour and the base colour, and lifts toward the text colour under
        # the pointer.
        surface = mix(window, base, b.surface[i])
        self.surface = surface.name()
        self.surface_hover = mix(surface, text, b.surface_hover[i]).name()

        self.button_hover = mix(button, text, b.button_hover[i]).name()
        self.button_pressed = mix(button, text, b.button_pressed[i]).name()

        # The primary button variant is a solid accent fill, so its hover and
        # pressed states are a blend rather than the alpha overlay the flat
        # controls use -- a translucent wash does not read over an opaque fill
        # the way it does over window or base. It moves toward the colour of
        # the label sitting on the button, which is the only direction that
        # works at both ends of the lightness range: a near-black accent has
        # nowhere darker to go.
        self.accent_hover = mix(accent, accent_text, b.accent_hover[i]).name()
        self.accent_pressed = mix(accent, accent_text, b.accent_pressed[i]).name()

        rgb = f'{accent.red()}, {accent.green()}, {accent.blue()}'
        self.hover = f'rgba({rgb}, {b.hover[i]})'
        self.pressed = f'rgba({rgb}, {b.pressed[i]})'
        self.selected_soft = f'rgba({rgb}, {b.selected_inactive[i]})'

        # The destructive button variant, unlike primary, stays a translucent
        # tint rather than a solid fill -- a button-sized block of solid red is
        # a stronger warning than most of calibre's delete actions deserve.
        danger = QColor(schemes.active().danger[i])
        rgb_danger = f'{danger.red()}, {danger.green()}, {danger.blue()}'
        self.danger = danger.name()
        self.danger_bg = f'rgba({rgb_danger}, {b.danger_bg[i]})'
        self.danger_bg_hover = f'rgba({rgb_danger}, {b.danger_bg_hover[i]})'

        self.tooltip_bg = pal.color(QPalette.ColorRole.ToolTipBase).name()
        self.tooltip_fg = pal.color(QPalette.ColorRole.ToolTipText).name()

        # A scheme may state a chrome colour rather than leave it to a blend --
        # see Scheme.named() for why a tinted ramp has to. It only gets to do
        # that over its own palette: if the installed one is not the one this
        # scheme describes, the reader has edited a palette in Preferences and
        # every colour goes back to being derived from what they chose.
        roles = scheme.roles(is_dark)
        if window.name() == roles['Window'] and base.name() == roles['Base']:
            for key, value in scheme.named(is_dark).items():
                setattr(self, key, value)

        # `menu_bg` is the name the sheet has always used for the surface, and
        # is set last so it follows a named surface as well as a derived one.
        self.menu_bg = self.surface

    def as_mapping(self) -> dict:
        "The names a QSS template may substitute."
        return {k: v for k, v in vars(self).items() if not k.startswith('_')}

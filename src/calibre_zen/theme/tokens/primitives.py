#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Primitive tokens: raw values, named for what they are and nothing else.

Nothing here knows what a button is. The ramps are ordered by lightness, so a
semantic map can say "window is neutral step 20" and a reader can see at a
glance which surfaces sit above which. Adding a colour means adding a step
here first; picking one out of the air at the component layer is how a palette
stops being a palette.

Kept free of Qt imports so it can be read, diffed and unit-tested without a
QApplication.
"""

import os

# Colour {{{

# One accent for every selection, focus ring and active state, in both themes.
# calibre's stock palettes use a blue Highlight and an unrelated green Accent;
# the green appears in exactly one place (fts/cards.py), so folding the two
# together costs nothing and stops the UI reading as two-toned.
ACCENT = '#3574f0'
ON_ACCENT = '#ffffff'

# Links are the one thing that does not use ACCENT: on a dark ground this blue
# is too dark to read as body text.
LINK_ON_DARK = '#6ea8ff'
VISITED_ON_DARK = '#b98eff'
VISITED_ON_LIGHT = '#7b4dd8'

DANGER_ON_DARK = '#ff6b6b'
DANGER_ON_LIGHT = '#d1242f'

# The palette folds calibre's stray green into the one accent on purpose. This
# green is not part of that: it exists only for status marks, where red and
# green are the whole message and no amount of consistency is worth making
# "running" and "stopped" look the same.
SUCCESS_ON_DARK = '#4fc27f'
SUCCESS_ON_LIGHT = '#1a7f45'

# Neutral ramps, keyed by approximate lightness (0 = black, 100 = white). The
# two ramps are read in opposite directions: the dark theme builds up from 0,
# the light theme down from 100.
NEUTRAL_DARK = {
    0: '#0e0f11',
    5: '#16181a',
    10: '#1a1c1f',
    15: '#1f2124',
    20: '#24262a',
    25: '#2c2f34',
    30: '#32353a',
    40: '#3a3e44',
    60: '#787c84',
    90: '#dfe1e5',
}

NEUTRAL_LIGHT = {
    15: '#1f2329',
    18: '#2b2e33',
    40: '#8a9099',
    55: '#b4b9c1',
    60: '#9a9fa8',
    65: '#d8dbe0',
    85: '#eceef1',
    90: '#f4f5f7',
    95: '#f8f9fb',
    97: '#f2f3f5',
    100: '#ffffff',
}
# }}}

# Typography {{{

# Every family the overlay can load, keyed by the name CALIBRE_ZEN_FONT
# selects. 'dir' is where its faces live under theme/fonts/, loaded by
# theme/generate.install_fonts(); 'family' is the name Qt's font database
# actually groups them under, which a static face does not always agree with
# its own file name about.
#
# Only Inter ships four weights on purpose -- it is the one the app is
# designed around. A family with fewer real faces still gets asked for all
# four in FONT_WEIGHT; Qt substitutes its nearest weight rather than failing,
# which is exactly what a quick comparison needs and not what a shipped
# default should settle for silently.
FONTS = {
    'inter': {
        'family': 'Inter',
        'dir': 'inter',
        'faces': ('Inter-Regular.ttf', 'Inter-Medium.ttf', 'Inter-SemiBold.ttf', 'Inter-Bold.ttf'),
    },
    'droid-sans': {
        'family': 'Droid Sans',
        'dir': 'droid-sans',
        'faces': ('DroidSans.ttf', 'DroidSans-Bold.ttf'),
    },
    # Literata was drawn for Google Play Books, which is the reason to prefer
    # it over a general-purpose serif here: it is a face meant to be read in a
    # book-shaped context, and the only place the overlay uses it is a book's
    # title. The plain Literata-* files are the text optical size; the 7pt,
    # 36pt and 72pt cuts in the same upstream directory are for print sizes
    # this never renders at.
    'literata': {
        'family': 'Literata',
        'dir': 'literata',
        'faces': ('Literata-Regular.ttf', 'Literata-Medium.ttf', 'Literata-SemiBold.ttf', 'Literata-Bold.ttf'),
    },
}
DEFAULT_FONT = 'inter'
# The second family, loaded alongside the first rather than instead of it. One
# registry serves both: a serif is a font like any other, and naming it here
# means CALIBRE_ZEN_FONT=literata is also a real thing to try.
DEFAULT_SERIF = 'literata'


def active_font() -> dict:
    "The FONTS entry CALIBRE_ZEN_FONT asks for -- 'inter' unless told otherwise, and unless told a name that isn't there."
    return FONTS.get(os.environ.get('CALIBRE_ZEN_FONT', ''), FONTS[DEFAULT_FONT])


def active_serif() -> dict:
    "The FONTS entry CALIBRE_ZEN_SERIF asks for, on the same terms as active_font()."
    return FONTS.get(os.environ.get('CALIBRE_ZEN_SERIF', ''), FONTS[DEFAULT_SERIF])


# Two steps: most of the app reads at one size, and the handful of things that
# are caption rather than content -- tooltips, column headers -- read one step
# down. A third step is for the next thing that turns out to need one, not for
# symmetry.
FONT_SIZE = {
    'sm': 12,
    'base': 13,
}

# The four weights every family is asked for. Regular is the default every
# widget already gets without naming it; the other three exist to be asked
# for by name, whether or not the active family has a real face for them.
FONT_WEIGHT = {
    'regular': 400,
    'medium': 500,
    'semibold': 600,
    'bold': 700,
}
# }}}

# Geometry {{{

# The whole radius vocabulary. Six steps; a seventh means one of these was
# wrong.
RADIUS = {
    'xxs': 2,  # slider groove
    'xs': 3,  # scrollbar handle
    'sm': 4,  # check mark
    'md': 5,  # list row, menu row
    'lg': 6,  # anything the pointer treats as one control
    'xl': 8,  # anything that contains controls
}
# }}}

# Blends {{{

# Chrome colours are not fixed greys, they are blends of the palette that is
# actually in use: fraction of the text colour mixed into the window colour.
# Deriving rather than hard-coding is what keeps the overlay compatible with
# the custom palettes calibre lets users define in Preferences -- pick a sepia
# theme and the borders, hovers and scrollbars follow it instead of staying
# stubbornly blue-grey.
#
# Pairs are (dark theme, light theme). A dark ground needs slightly more
# contrast for the same apparent hairline.
MIX_BORDER = (0.16, 0.14)
MIX_BORDER_WEAK = (0.09, 0.07)
MIX_BORDER_STRONG = (0.30, 0.26)
MIX_MUTED = (0.55, 0.55)
MIX_TRACK = (0.12, 0.12)
MIX_SCROLL = (0.26, 0.26)
MIX_SCROLL_HOVER = (0.42, 0.42)
MIX_BUTTON_HOVER = (0.10, 0.10)
MIX_BUTTON_PRESSED = (0.18, 0.18)
# Menus float above the window, so they take the window colour pulled toward
# the content colour: halfway on dark, all the way on light.
MIX_MENU = (0.5, 1.0)

# Hover and pressed are translucent accent rather than a computed solid: one
# value that works over the window, over base, and over alternating rows.
# 0-255 alpha, (dark, light).
ALPHA_HOVER = (45, 28)
ALPHA_PRESSED = (75, 52)
ALPHA_SELECTED_INACTIVE = (95, 62)

# The destructive button variant is a translucent danger tint, not a solid
# fill -- resting and hover, 0-255 alpha, (dark, light). A dark ground reads
# the same tint as lighter, so it gets more of it for the same apparent weight.
ALPHA_DANGER_BG = (51, 26)  # ~20% dark, ~10% light
ALPHA_DANGER_BG_HOVER = (77, 51)  # ~30% dark, ~20% light
# }}}

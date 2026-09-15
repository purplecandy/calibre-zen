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
# }}}

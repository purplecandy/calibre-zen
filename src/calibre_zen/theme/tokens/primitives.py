#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Primitive tokens: raw values, named for what they are and nothing else.

Nothing here knows what a button is. The ramps are ordered by lightness, so a
semantic map can say "window is neutral step 20" and a reader can see at a
glance which surfaces sit above which. Adding a colour means adding a step
here first; picking one out of the air at the component layer is how a palette
stops being a palette.

Nothing here picks between these values either: which ramp, which radius
scale and which blend recipes are in force is a `Scheme`, next door.

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

# The greyscale ramps shadcn/ui builds its neutral presets from. Every one has
# the same twelve steps and differs only in how much hue is mixed into them, so
# one of those presets is a ramp and nothing else -- which is why `schemes.py`
# builds all of them with a single function.
#
# Keyed by OKLCH lightness x100: the same "approximate lightness" convention as
# the two ramps above, and here it is the exact figure the upstream tokens are
# defined at. What each step is, once, for all five:
#
#     0   black. Not one of the families -- Fusion's Shadow has to reach it
#    15   the page in dark                      --background
#    21   the card, sidebar and popover in dark, and --primary in light
#    27   secondary / muted / accent in dark
#    37   --chart-4
#    44   --chart-3
#    56   --muted-foreground in light, --ring in dark
#    71   --muted-foreground in dark, --ring in light
#    87   --chart-1
#    92   --border and --input in light, and --primary in dark
#    97   secondary / muted / accent in light
#    98   the chrome in light                   --sidebar
#   100   the page in light                     --background

# Tailwind neutral: no hue at all, chroma 0 at every step.
NEUTRAL = {
    0: '#000000',
    15: '#0a0a0a',
    21: '#171717',
    27: '#262626',
    37: '#404040',
    44: '#525252',
    56: '#737373',
    71: '#a1a1a1',
    87: '#d4d4d4',
    92: '#e5e5e5',
    97: '#f5f5f5',
    98: '#fafafa',
    100: '#ffffff',
}

# Tailwind stone: warm, tinted brown.
STONE = {
    0: '#000000',
    15: '#0c0a09',
    21: '#1c1917',
    27: '#292524',
    37: '#44403b',
    44: '#57534d',
    56: '#79716b',
    71: '#a6a09b',
    87: '#d6d3d1',
    92: '#e7e5e4',
    97: '#f5f5f4',
    98: '#fafaf9',
    100: '#ffffff',
}

# Tailwind zinc: cool, tinted blue.
ZINC = {
    0: '#000000',
    15: '#09090b',
    21: '#18181b',
    27: '#27272a',
    37: '#3f3f46',
    44: '#52525c',
    56: '#71717b',
    71: '#9f9fa9',
    87: '#d4d4d8',
    92: '#e4e4e7',
    97: '#f4f4f5',
    98: '#fafafa',
    100: '#ffffff',
}

# Warm, tinted yellow-green.
OLIVE = {
    0: '#000000',
    15: '#0c0c09',
    21: '#1d1d16',
    27: '#2b2b22',
    37: '#474739',
    44: '#5b5b4b',
    56: '#7c7c67',
    71: '#abab9c',
    87: '#d8d8d0',
    92: '#e8e8e3',
    97: '#f4f4f0',
    98: '#fbfbf9',
    100: '#ffffff',
}

# Cool, tinted teal.
MIST = {
    0: '#000000',
    15: '#090b0c',
    21: '#161b1d',
    27: '#22292b',
    37: '#394447',
    44: '#4b585b',
    56: '#67787c',
    71: '#9ca8ab',
    87: '#d0d6d8',
    92: '#e3e7e8',
    97: '#f1f3f3',
    98: '#f9fbfb',
    100: '#ffffff',
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

# The same six roles, rounder. shadcn/ui's scale is a base radius of 10px with
# six steps derived from it, drawn for web controls about 36px tall; ours are
# about 26px, so the scale is that one at the ratio our density actually has
# rather than its pixel values taken literally. A scheme picks one of these.
RADIUS_SOFT = {
    'xxs': 3,
    'xs': 4,
    'sm': 5,
    'md': 6,
    'lg': 8,
    'xl': 10,
}
# }}}

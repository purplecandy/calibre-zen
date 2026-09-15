#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
A scheme: one complete set of design tokens, swappable at runtime.

Everything above this layer -- the palette maps, `Chrome`, the radii the sheet
asks for by name -- used to be written directly against `primitives`, which
meant there could only ever be one answer. A `Scheme` is that same set of
answers made nameable, so a second one can exist without the first being
deleted and a reader can change their mind without restarting.

Three things make up a scheme, and they are different in kind:

    roles       QPalette.ColorRole -> hex, per mode. The theme's surfaces.
    blends      the recipes Chrome derives borders, hovers and scrollbars from.
                Ratios, not colours, which is what keeps a scheme compatible
                with the custom palettes calibre lets users define: pick a
                sepia palette and the chrome follows it.
    radius      the radius vocabulary. Roundness is as much a scheme's identity
                as its greys are.

Six schemes ship. Five are shadcn/ui's neutral presets, which differ from
each other only in how much hue is tinted into one greyscale ramp -- same
lightness steps, same alphas, same red, same radius -- so they are built by
one function from one ramp each:

    neutral     no tint at all. Shipped default.
    stone       warm, tinted brown.
    zinc        cool, tinted blue.
    olive       warm, tinted yellow-green.
    mist        cool, tinted teal.

    zen         the odd one out: the overlay's original, the same shapes
                around one blue accent.

Switch with CALIBRE_ZEN_SCHEME=<name>, or from the toolbar's appearance menu,
which writes gprefs['zen_color_scheme'] and re-themes the running window
through exactly the path the light/dark switch already uses.
"""

import os
from dataclasses import dataclass, field, replace

from calibre_zen.theme.tokens import primitives as p

ENV_VAR = 'CALIBRE_ZEN_SCHEME'
PREF_KEY = 'zen_color_scheme'
DEFAULT = 'neutral'


@dataclass(frozen=True)
class Blends:
    """
    How `Chrome` derives a colour it was not handed.

    Every pair is (dark theme, light theme). A `mix` is a fraction of a second
    colour blended into a first; an `alpha` is 0-255 over whatever is behind.
    The defaults are the original scheme's, so a new scheme overrides only the
    recipes it actually disagrees with.
    """

    # Fraction of the text colour mixed into the window colour. A dark ground
    # needs slightly more contrast for the same apparent hairline.
    border: tuple = (0.16, 0.14)
    border_weak: tuple = (0.09, 0.07)
    border_strong: tuple = (0.30, 0.26)
    muted: tuple = (0.55, 0.55)
    track: tuple = (0.12, 0.12)
    scroll: tuple = (0.26, 0.26)
    scroll_hover: tuple = (0.42, 0.42)

    # Fraction of the text colour mixed into the button colour.
    button_hover: tuple = (0.10, 0.10)
    button_pressed: tuple = (0.18, 0.18)

    # Where a floating surface -- a menu, a popover, a row card -- sits between
    # the window colour and the base colour, and how far it lifts under the
    # pointer (toward the text colour).
    surface: tuple = (0.5, 1.0)
    surface_hover: tuple = (0.10, 0.06)

    # Translucent accent rather than a computed solid: one value that works
    # over the window, over base, and over alternating rows. 0-255.
    hover: tuple = (45, 28)
    pressed: tuple = (75, 52)
    selected_inactive: tuple = (95, 62)

    # The destructive button variant is a translucent tint, not a solid fill --
    # a button-sized block of solid red is a stronger warning than most of
    # calibre's delete actions deserve. A dark ground reads the same tint as
    # lighter, so it gets more of it for the same apparent weight.
    danger_bg: tuple = (51, 26)
    danger_bg_hover: tuple = (77, 51)

    # The primary button's hover and pressed states move the accent toward the
    # colour of the label sitting on it, not toward the window's text colour.
    # It is the only direction that works in both themes and at both ends of
    # the lightness range: a near-black accent cannot get usefully darker.
    accent_hover: tuple = (0.10, 0.10)
    accent_pressed: tuple = (0.18, 0.18)


@dataclass(frozen=True)
class Scheme:
    name: str
    title: str  # what the appearance menu calls it
    note: str  # one line, for the menu's tooltip
    dark: dict
    light: dict
    radius: dict
    blends: Blends = field(default_factory=Blends)
    # (dark, light) for each. These are the colours that must carry a hue to
    # mean anything, even in a scheme that is otherwise greyscale.
    danger: tuple = (p.DANGER_ON_DARK, p.DANGER_ON_LIGHT)
    success: tuple = (p.SUCCESS_ON_DARK, p.SUCCESS_ON_LIGHT)

    # Chrome colours this scheme states outright instead of leaving to a
    # blend, per mode. See `named()`.
    chrome_dark: dict = field(default_factory=dict)
    chrome_light: dict = field(default_factory=dict)

    def roles(self, is_dark: bool) -> dict:
        return self.dark if is_dark else self.light

    def named(self, is_dark: bool) -> dict:
        """
        The chrome colours this scheme states rather than derives.

        A blend interpolates between the window colour and the text colour,
        which for these ramps are their two *extremes* -- and in a tinted ramp
        both extremes are very nearly neutral, because the tint lives in the
        mid-tones. Stone's --muted-foreground is #79716b, 14 apart across its
        channels; blending its #fafaf9 toward its #0c0a09 gives #757473, 2
        apart. Derived chrome would quietly flatten every preset back to the
        same greys, which is the one thing that distinguishes them.

        So where the token set states a value and that value is a step of the
        ramp, the scheme says so. `semantic.Chrome` uses these only while the
        scheme's own palette is the one installed: edit a custom palette in
        Preferences and every colour goes back to being derived from it, which
        is what the blends were always for.
        """
        return self.chrome_dark if is_dark else self.chrome_light


# The original: one blue accent, two neutral ramps read in opposite directions.
# Kept whole rather than described as a diff from the new default, because it
# is the thing every screenshot in this project's history was taken against.
ZEN = Scheme(
    name='zen',
    title='Blue',
    note='One blue accent, the overlay’s original palette',
    radius=p.RADIUS,
    dark={
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
        # Fusion derives frame and separator colours from these five; left at
        # their defaults they are far lighter than this window colour and every
        # sunken frame glows.
        'Light': p.NEUTRAL_DARK[40],
        'Midlight': p.NEUTRAL_DARK[30],
        'Mid': p.NEUTRAL_DARK[40],
        'Dark': p.NEUTRAL_DARK[5],
        'Shadow': p.NEUTRAL_DARK[0],
        'Disabled': p.NEUTRAL_DARK[60],
    },
    light={
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
        # Dark tooltips in the light theme too: a tooltip is an overlay, and
        # every current UI inverts it.
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
    },
)


# shadcn/ui's neutral presets. One ramp each, read in both directions, and two
# surfaces per mode rather than a gradient of them: a page colour and a card
# colour, everything else is one of those two plus a border.
#
#   light   page #ffffff, chrome <98>, muted <97>, border <92>
#   dark    page <15>,    chrome <21>, muted <27>, border white/10
#
# Qt's Window/Base split is what carries that: Window is the chrome a panel or
# toolbar sits on (their `sidebar`), Base is the page a list or a field is
# drawn on (`background`). In light they are a hair apart; in dark the chrome
# sits a step *lighter* than the page, which is the inverse of the original
# scheme and is what makes the shadcn dashboards read the way they do.
#
# The presets differ only in the ramp -- same lightness steps, same alphas, and
# every one of them shares the destructive red, the blue that is the only hue
# in their sidebar group, and the radius scale. So the arrangement is written
# once, here, and a preset is a ramp and a name.

# The two colours that have to carry a hue to mean anything, in a set that is
# otherwise grey. `destructive` is theirs, in both modes and every preset. The
# link has no token of theirs at all, and a link that is not a hue is not a
# link, so it borrows the blue their sidebar group uses. (dark, light).
DESTRUCTIVE = ('#ff6467', '#e7000b')
LINK = ('#51a2ff', '#1447e6')
LINK_VISITED = ('#a684ff', '#7f22fe')
# Not a token of theirs; Tailwind green, for the status marks where red and
# green are the whole message.
SUCCESS = ('#05df72', '#008236')

# Every ratio here was solved for a colour the token set names, against the
# window colour above it: `border` at 0.09 light lands on #e4e4e4 where theirs
# is #e5e5e5, `muted` on #737373 exactly, and dark `border` on #2e2e2e where
# white/10 over #171717 is #2e2e2e. Derived rather than hard-coded so a custom
# palette still gets chrome that belongs to it. The steps are the same in every
# preset, so one set of ratios serves all five.
SHADCN_BLENDS = Blends(
    border=(0.10, 0.09),  # --border
    border_weak=(0.055, 0.05),
    border_strong=(0.155, 0.095),  # --input
    muted=(0.61, 0.56),  # --muted-foreground
    track=(0.12, 0.10),
    # A card is the window colour in dark (chrome already sits above the page)
    # and the base colour in light (where the page is the lighter of the two).
    # Both land on their `card`.
    surface=(0.0, 1.0),
    surface_hover=(0.07, 0.04),  # --accent, one step off the card
    # Solved against --accent / --muted rather than kept at the original
    # scheme's alphas: a near-black accent at 45/255 over white is #d6d6d6,
    # which is a pressed state, not a hover.
    hover=(33, 19),
    pressed=(56, 34),
    selected_inactive=(72, 44),
)


def white_over(colour: str, alpha: float) -> str:
    "White at `alpha` over `colour` -- how they define a border in dark mode."
    parts = (int(colour[i : i + 2], 16) for i in (1, 3, 5))
    return '#' + ''.join(f'{round(v * (1 - alpha) + 255 * alpha):02x}' for v in parts)


def shadcn(name: str, title: str, note: str, ramp: dict) -> Scheme:
    "One of their neutral presets, which is to say: this arrangement of one ramp."
    return Scheme(
        name=name,
        title=title,
        note=note,
        radius=p.RADIUS_SOFT,
        blends=SHADCN_BLENDS,
        danger=DESTRUCTIVE,
        success=SUCCESS,
        chrome_dark={
            'border': white_over(ramp[21], 0.10),  # --border, white/10 over --card
            'border_strong': white_over(ramp[21], 0.15),  # --input, white/15
            'muted': ramp[71],  # --muted-foreground
            'surface': ramp[21],  # --card
            'surface_hover': ramp[27],  # --accent, one step off the card
        },
        chrome_light={
            'border': ramp[92],  # --border
            'border_strong': ramp[92],  # --input, which in light is the same
            'muted': ramp[56],  # --muted-foreground
            'surface': ramp[100],  # --card
            'surface_hover': ramp[97],  # --accent
        },
        dark={
            'Window': ramp[21],  # sidebar / card / popover
            'WindowText': ramp[98],  # foreground
            'Base': ramp[15],  # background
            'AlternateBase': ramp[21],  # a stripe is the card colour, one step off the page
            'Text': ramp[98],
            'Button': ramp[27],  # secondary
            'ButtonText': ramp[98],
            'PlaceholderText': ramp[44],
            'BrightText': DESTRUCTIVE[0],
            # Their tooltip inverts in both modes, which in dark means a white
            # slab over a black UI. The overlay's own rule wins here: a tooltip
            # is an overlay and stays dark, one step up from the surface it
            # floats on.
            'ToolTipBase': ramp[27],
            'ToolTipText': ramp[98],
            'Link': LINK[0],
            'LinkVisited': LINK_VISITED[0],
            'Highlight': ramp[92],  # primary
            'HighlightedText': ramp[21],  # primary-foreground
            'Accent': ramp[92],
            'Light': ramp[37],
            'Midlight': ramp[27],
            'Mid': ramp[37],
            'Dark': ramp[15],
            'Shadow': ramp[0],
            'Disabled': ramp[44],
        },
        light={
            'Window': ramp[98],  # sidebar
            'WindowText': ramp[15],  # foreground
            'Base': ramp[100],  # background / card / popover
            'AlternateBase': ramp[97],  # muted
            'Text': ramp[15],
            'Button': ramp[100],
            'ButtonText': ramp[15],
            'PlaceholderText': ramp[71],
            'BrightText': DESTRUCTIVE[1],
            'ToolTipBase': ramp[21],
            'ToolTipText': ramp[98],
            'Link': LINK[1],
            'LinkVisited': LINK_VISITED[1],
            'Highlight': ramp[21],  # primary
            'HighlightedText': ramp[98],  # primary-foreground
            'Accent': ramp[21],
            'Light': ramp[100],
            'Midlight': ramp[97],
            'Mid': ramp[92],
            'Dark': ramp[87],
            'Shadow': ramp[71],
            'Disabled': ramp[71],
        },
    )


NEUTRAL = shadcn('neutral', 'Neutral', 'Grey with no tint at all', p.NEUTRAL)
STONE = shadcn('stone', 'Stone', 'Warm grey, tinted brown', p.STONE)
ZINC = shadcn('zinc', 'Zinc', 'Cool grey, tinted blue', p.ZINC)
OLIVE = shadcn('olive', 'Olive', 'Warm grey, tinted yellow-green', p.OLIVE)
MIST = shadcn('mist', 'Mist', 'Cool grey, tinted teal', p.MIST)


# Order is menu order: the presets, then the odd one out.
SCHEMES = {s.name: s for s in (NEUTRAL, STONE, ZINC, OLIVE, MIST, ZEN)}

_active = None


def stored() -> str | None:
    "The reader's choice, or None. Never raises -- gprefs may not exist yet."
    try:
        from calibre.gui2 import gprefs

        value = gprefs.get(PREF_KEY)
    except Exception:
        return None
    return value if value in SCHEMES else None


def active() -> Scheme:
    """
    The scheme in force: the environment first, then the stored choice.

    Cached, because `Chrome` and the component radii both ask on every
    re-theme. `set_active` is the only thing that invalidates it.
    """
    global _active
    if _active is None:
        name = os.environ.get(ENV_VAR, '')
        _active = SCHEMES.get(name) or SCHEMES.get(stored() or '') or SCHEMES[DEFAULT]
    return _active


def set_active(name: str) -> bool:
    """
    Choose a scheme and remember it. Returns whether anything changed.

    Applying it is the caller's job and is one call --
    `PaletteManager.refresh_palette()`, the same path the light/dark switch
    takes -- because that rebuilds the palette from our functions and ends in
    `on_palette_change`, which re-renders the sheet.
    """
    global _active
    scheme = SCHEMES.get(name)
    if scheme is None or scheme is active():
        return False
    _active = scheme
    try:
        from calibre.gui2 import gprefs

        gprefs[PREF_KEY] = name
    except Exception:
        pass
    from calibre_zen.theme.tokens import components

    components.refresh()
    return True


def variant(scheme: Scheme, **kw) -> Scheme:
    "A scheme with a few fields changed -- for a test, or a third scheme later."
    return replace(scheme, **kw)

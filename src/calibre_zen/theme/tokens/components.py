#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Component tokens: the radii and densities the stylesheet actually asks for.

This layer exists only because the sheet already implies it -- a radius is
picked per *kind* of thing, not per widget class, and several unrelated
selectors want the same number. Anything that appears once and means nothing
elsewhere (a 6px nudge on a menu indicator, say) stays a literal in the QSS
where it can be seen next to the rule it affects.

Values are plain numbers where a template writes `${name}px`, and strings
where they are a CSS shorthand.
"""

from calibre_zen.theme.tokens.primitives import RADIUS

# Radii, by what the pointer thinks it is touching {{{
RADIUS_MARK = RADIUS['sm']  # a check or radio indicator
RADIUS_ROW = RADIUS['md']  # one row of a list, menu or tree
RADIUS_CONTROL = RADIUS['lg']  # a thing you click or type into
RADIUS_PANEL = RADIUS['xl']  # a thing that contains controls
RADIUS_SCROLL = RADIUS['xs']  # a scrollbar handle
RADIUS_GROOVE = RADIUS['xxs']  # a slider groove or progress track
# }}}

# Sizes {{{
MARK_SIZE = 14  # check and radio indicators
RADIUS_RADIO = 8  # MARK_SIZE / 2, rounded up past the border
SLIDER_HANDLE = 13
RADIUS_SLIDER_HANDLE = 7
CONTROL_MIN_HEIGHT = 20  # buttons and fields agree on one height
SCROLLBAR = 12  # thin, because the handle carries no arrows
SCROLL_HANDLE_MIN = 32
SPLITTER = 5
ACTIVE_TAB_UNDERLINE = 2
# }}}

# Density. The sheet's whole feel lives in these six strings {{{
PAD_BUTTON = '4px 14px'
PAD_FIELD = '3px 8px'
PAD_TOOLBUTTON = '3px'
PAD_TAB = '6px 14px'
PAD_HEADER = '5px 8px'
PAD_TOOLTIP = '5px 8px'

PAD_MENU = '5px'
# Asymmetric on purpose: room for a check mark on the left, a shortcut or
# submenu arrow on the right.
PAD_MENU_ITEM = '5px 28px 5px 26px'
PAD_MENUBAR_ITEM = '4px 9px'

PAD_GROUPBOX = '10px 4px 4px 4px'
GROUPBOX_TITLE_OFFSET = 11  # margin-top, so the title sits on the border

TOOLBAR_SPACING = 4
# A separator has to read as one gap, not three: its own margin plus the
# toolbar spacing on either side comes to about one gap's worth.
PAD_TOOLBAR_SEPARATOR = '6px 3px'
# }}}

# Icons {{{

# calibre maps its five icon-size settings to 0/24/30/48/64 px, drawn for
# detailed colour icons. A line icon at 48px is a diagram; these are the sizes
# the same glyph is legible at. Keys are calibre's own setting names, so the
# preference keeps working and only the scale under it changes.
TOOLBAR_ICON_SIZE = {'off': 0, 'small': 14, 'mid-small': 16, 'medium': 18, 'large': 22}

# Tabler draws at 2 in a 24px box. At 18px that reads as a marker pen next to
# the UI font; 1.5 is what the set itself recommends below 24.
ICON_STROKE = 1.5

# The chevrons that replace Qt's arrow triangles: the box they are drawn into,
# not the glyph.
INDICATOR_SIZE = 10
BRANCH_SIZE = 12
# Room a button reserves for its dropdown arrow, the same for every button
# that has one.
MENU_ARROW_ROOM = 16
# }}}


def as_mapping() -> dict:
    "The names a QSS template may substitute."
    g = globals()
    return {k.lower(): g[k] for k in g if k.isupper() and isinstance(g[k], (int, str))}

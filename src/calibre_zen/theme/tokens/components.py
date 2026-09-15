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
# }}}


def as_mapping() -> dict:
    "The names a QSS template may substitute."
    g = globals()
    return {k.lower(): g[k] for k in g if k.isupper() and isinstance(g[k], (int, str))}

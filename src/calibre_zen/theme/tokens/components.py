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

from calibre_zen.theme.tokens import primitives
from calibre_zen.theme.tokens.primitives import RADIUS

# Typography, by what is being read {{{
FONT_FAMILY = primitives.active_font()['family']  # CALIBRE_ZEN_FONT; 'Inter' unless told otherwise
FONT_SIZE_BASE = primitives.FONT_SIZE['base']  # everything, unless named below
FONT_SIZE_CAPTION = primitives.FONT_SIZE['sm']  # tooltips, column headers
WEIGHT_HEADING = primitives.FONT_WEIGHT['semibold']  # group box titles, the one heading Qt gives a subcontrol
# }}}

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

# The filter panel -- our replacement for the tag browser's tree, see
# calibre_zen/filters/. Read from the delegate rather than from a template:
# every row is painted, not laid out, so these are the whole geometry. {{{
FILTER_ROW_HEIGHT = 38  # a category row, the thing you aim at most
FILTER_VALUE_ROW_HEIGHT = 32  # one value inside a category; there can be thousands
FILTER_HEADER_HEIGHT = 34  # a section caption, with its air above it
FILTER_PAD_X = 14  # the sheet's left and right margin, shared by every row
FILTER_GAP = 8  # between label, value and mark
FILTER_MARK_SIZE = 14  # the chevron, the check and the dash
FILTER_INDENT = 14  # how far a nested row is pushed in per level
# }}}

# The centre pane -- the preview over the book table, see calibre_zen/centre/.
# Read from the delegate rather than from a template, the same as the filter
# panel above: a table row is painted, not laid out. {{{
TABLE_ROW_HEIGHT = 84  # cover height plus the air above and below it
TABLE_ROW_GAP = 6  # the horizontal band left unpainted, which is what makes a row a card
TABLE_ROW_RADIUS = RADIUS['xl']  # rounded on the row's two outer ends only
TABLE_PAD_X = 12  # inside a cell, left and right
TABLE_COVER_W = 44
TABLE_COVER_H = 66  # 2:3, the shape nearly every cover already is
TABLE_COVER_RADIUS = RADIUS['sm']
TABLE_DETAILS_WIDTH = 320  # the composite column's starting width
TABLE_LINE_GAP = 2  # between the series line, the title and the author

# How much of calibre's own cover-grid tile each density keeps. A multiplier
# rather than a size, for the same reason TOOLBAR_ICON_SIZE re-scales calibre's
# five icon settings instead of replacing them: the reader's Preferences ->
# Cover grid settings still choose the base, and this only changes the scale
# underneath. 'default' is calibre's size untouched, and must stay 1.0.
GRID_DENSITY = {'default': 1.0, 'compact': 0.66, 'tiny': 0.44}
GRID_DENSITY_DEFAULT = 'compact'

PREVIEW_HEIGHT = 300  # the top half's starting height, draggable after that
PREVIEW_COVER_W = 152
PREVIEW_COVER_H = 228  # 2:3, the shape nearly every cover already is
PREVIEW_COVER_RADIUS = RADIUS['lg']
PREVIEW_PAD = 20
PREVIEW_GAP = 6  # between one line of the metadata block and the next
PREVIEW_MARK = 13  # the rating star
PREVIEW_MAX_TAGS = 6  # after which the rest become a "+n" pill
PREVIEW_TITLE_SIZE = 21
PREVIEW_AUTHOR_SIZE = 14
# }}}

# Density. The sheet's whole feel lives in these six strings {{{
PAD_BUTTON = '4px 14px'
PAD_FIELD = '3px 8px'
PAD_TOOLBUTTON = '6px'
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

# An icon-only main toolbar. The labels doubled the bar's height to name things
# that are already named in the tooltip and on the menu, and a row of captions
# is most of what made it read as a 2005 toolbar. Set True to hand the decision
# back to calibre's "Show text under icons" preference.
TOOLBAR_LABELS = False

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

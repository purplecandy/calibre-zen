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

The radii are the one thing here that a scheme gets to change, so they are
rebound by `refresh()` rather than written once at import time.
"""

from calibre_zen.theme.tokens import primitives, schemes

# Typography, by what is being read {{{
FONT_FAMILY = primitives.active_font()['family']  # CALIBRE_ZEN_FONT; 'Inter' unless told otherwise
FONT_FAMILY_SERIF = primitives.active_serif()['family']  # CALIBRE_ZEN_SERIF; 'Literata' unless told otherwise
FONT_SIZE_BASE = primitives.FONT_SIZE['base']  # everything, unless named below
FONT_SIZE_CAPTION = primitives.FONT_SIZE['sm']  # tooltips, column headers
WEIGHT_HEADING = primitives.FONT_WEIGHT['semibold']  # group box titles, the one heading Qt gives a subcontrol
# }}}

# Radii, by what the pointer thinks it is touching {{{

# The scale itself belongs to the active scheme -- roundness is as much a
# scheme's identity as its greys are -- so these are rebound by refresh()
# rather than being written once at import. Which role gets which step does
# not change between schemes; only the six numbers behind them do.
RADIUS_MARK = 0  # a check or radio indicator
RADIUS_ROW = 0  # one row of a list, menu or tree
RADIUS_CONTROL = 0  # a thing you click or type into
RADIUS_PANEL = 0  # a thing that contains controls
RADIUS_SCROLL = 0  # a scrollbar handle
RADIUS_GROOVE = 0  # a slider groove or progress track
TABLE_ROW_RADIUS = 0  # rounded on the row's two outer ends only
TABLE_COVER_RADIUS = 0
PREVIEW_COVER_RADIUS = 0
GRID_CARD_RADIUS = 0
GRID_ACTION_RADIUS = 0
STATUS_SEGMENT_RADIUS = 0

# Which step each role takes. A seventh entry in the scale would mean one of
# these was wrong.
_RADIUS_ROLES = {
    'RADIUS_MARK': 'sm',
    'RADIUS_ROW': 'md',
    'RADIUS_CONTROL': 'lg',
    'RADIUS_PANEL': 'xl',
    'RADIUS_SCROLL': 'xs',
    'RADIUS_GROOVE': 'xxs',
    'TABLE_ROW_RADIUS': 'xl',
    'TABLE_COVER_RADIUS': 'sm',
    'PREVIEW_COVER_RADIUS': 'lg',
    'GRID_CARD_RADIUS': 'xl',
    'GRID_ACTION_RADIUS': 'lg',
    'STATUS_SEGMENT_RADIUS': 'md',
}


def refresh() -> None:
    """
    Re-read the radii from whatever scheme is now active.

    Called when the scheme changes, and again from generate.mapping() on every
    re-theme -- these are plain module attributes because that is how the
    delegates and the templates read them, and a module attribute does not
    follow a scheme on its own.
    """
    scale = schemes.active().radius
    g = globals()
    for name, step in _RADIUS_ROLES.items():
        g[name] = scale[step]


refresh()
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

# The welcome wizard's last pages -- see calibre_zen/onboarding/. One
# recording per page; the sizes here are the ones a layout takes. {{{
ONBOARDING_SPACING = 12  # between the recording and the footer
ONBOARDING_DEMO_MIN_WIDTH = 480  # the least a recording may be given: 16:9
ONBOARDING_DEMO_MIN_HEIGHT = 270
# The wizard's opening size once our pages are in it. Upstream's 600x520 was
# chosen for three paragraphs; a recording of a whole window wants room, and
# this still fits a 13" display with the dock showing.
ONBOARDING_WIZARD_WIDTH = 960
ONBOARDING_WIZARD_HEIGHT = 640
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
TABLE_PAD_X = 12  # inside a cell, left and right
TABLE_COVER_W = 44
TABLE_COVER_H = 66  # 2:3, the shape nearly every cover already is
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
PREVIEW_PAD = 20
PREVIEW_GAP = 6  # between one line of the metadata block and the next
PREVIEW_MARK = 13  # the rating star
PREVIEW_MAX_TAGS = 6  # after which the rest become a "+n" pill
PREVIEW_TITLE_SIZE = 21
PREVIEW_AUTHOR_SIZE = 14
PREVIEW_QUICK_ACTIONS = 4  # from the row's own context menu, before the overflow button

# A cover-grid tile under the pointer -- the ring around the cover and the card
# above it, see calibre_zen/centre/tiles.py. Painted, not laid out, so these are
# the whole geometry. The ring's gap and stroke add up to CoverDelegate.MARGIN,
# which is 4: any more and the ring is drawn outside the tile it belongs to.
GRID_RING = 2  # the ring's stroke
GRID_RING_GAP = 2  # between the cover's edge and the ring
GRID_CARD_PAD_X = 12
GRID_CARD_PAD_Y = 9
GRID_CARD_POINT = 7  # the pointer: its height, and half its width
GRID_CARD_GAP = 9  # between the tile and the card's pointer
GRID_CARD_MAX_W = 340
GRID_CARD_LINE_GAP = 3
GRID_CARD_DELAY = 320  # ms of rest on one tile before the card appears

# The quick actions that appear over a hovered cover.
GRID_ACTION_SIZE = 26  # one button's box
GRID_ACTION_ICON = 16
GRID_ACTION_PAD = 4  # inside the bar, around the buttons
GRID_ACTION_GAP = 2  # between buttons
GRID_ACTION_INSET = 7  # from the cover's bottom edge
# }}}

# The status bar -- see calibre_zen/status/. A row of segments, laid out rather
# than painted, so these are the sheet's numbers and the two painted ones. {{{
STATUS_ICON = 15  # a segment's glyph; one step under the toolbar's
STATUS_GAP = 2  # between one segment and the next -- they are their own hover targets
STATUS_GROUP_GAP = 10  # between the two ends of the bar and around the layout buttons
STATUS_PAD = '3px 6px'
STATUS_MARGIN_X = 6  # the bar's own inset; set on the layout, not in the sheet,
STATUS_MARGIN_Y = 1  # because a plain QWidget's padding does not move its layout
STATUS_PROGRESS = 2  # the job segment's progress rule, drawn along its bottom edge
STATUS_PROGRESS_INSET = 6  # how far short of the segment's ends that rule stops
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
# How far short of a split button's top and bottom edge its seam stops.
# Measured against the thing it must not be mistaken for: a QToolBar separator
# on this bar is 23px of $border, and at the first inset tried -- the
# separator's own 6 -- the seam came out at exactly 23px of $border too, so a
# division inside one button and a division between two groups were the same
# mark. This is the shorter of the two, and 03-marks' weaker line.
TOOLBAR_SPLIT_INSET = 10
# }}}


def as_mapping() -> dict:
    "The names a QSS template may substitute."
    g = globals()
    return {k.lower(): g[k] for k in g if k.isupper() and isinstance(g[k], (int, str))}

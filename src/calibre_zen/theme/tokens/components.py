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

# Forms -- see calibre_zen/forms/. A grouped form in the shape of macOS System
# Settings: rows in rounded groups, the label at the row's start, the control
# at its end, a hairline between rows. Every form the overlay lays out reads
# these, so a change here moves all of them at once. {{{
FORM_ROW_HEIGHT = 40  # a row, hairline to hairline
FORM_ROW_PAD_X = 12  # inside a group, either side of a row
FORM_ROW_PAD_Y = 6
FORM_SECTION_GAP = 22  # between one group and the next
FORM_MARGIN = 14  # around a form that fills a page of its own
FORM_GROUP_TITLE_GAP = 6  # between a group's title and its rows
FORM_LABEL_GAP = 12  # label to control
FORM_LABEL_MAX = 200  # the label column: as wide as its longest label, up to this
FORM_SLOT = 26  # a row's trailing action (the list editor, clear): the same box on every row, filled or not
# A control is as wide as what goes in it, never narrower than these; only
# free text stretches to the row's end.
FIELD_WIDTH_NUMBER = 112
FIELD_WIDTH_DATE = 160
FIELD_WIDTH_CHOICE = 176
FIELD_WIDTH_SERIES_INDEX = 80  # the # beside a series name
# Free text -- names, tags, a series -- in the control column: this share of
# what a row has once its padding and slots are taken, between the two widths.
# The label side gets the rest. System Settings keeps its controls at the
# trailing end and never runs a field from the label to the edge.
FORM_CONTROL_SHARE = 0.55
FIELD_WIDTH_TEXT_MIN = 240
FIELD_WIDTH_TEXT_MAX = 420
FIELD_WIDTH_TEXT_MAX_FILL = 560  # a form that lets text fill the row: the Details tab
# A long or rich text field's text area, at least: about four lines. A size
# rather than a count of lines because it is the sheet that sets it -- the app
# sheet's min-height on every text area beats one set from code.
TEXTAREA_MIN_HEIGHT = 92
# }}}

# The Edit metadata dialog -- see calibre_zen/editor/. {{{
EDITOR_COVER_W = 150  # the cover beside the Details form
EDITOR_COVER_H = 225
FILES_COVER_W = 184  # the same cover, on Cover & files
FILES_COVER_H = 276
FILES_COVER_GAP = 20  # between that cover and its actions
FILES_ACTIONS_MAX_W = 380  # the cover's action buttons, two to a row
FILES_LIST_MIN_H = 108  # the book files list: three rows before it scrolls
EDITOR_TOP_GAP = 6  # above the tabs; the dialog has no margin of its own
EDITOR_FOOTER_PAD_X = 14
EDITOR_FOOTER_PAD_Y = 10
# A dialog footer's lift off the page, like the title bar's -- theme/surfaces.py.
FOOTER_SHADOW_BLUR = 16  # wide and faint: a hint of lift, not an edge
FOOTER_SHADOW_LIGHT = 0.03
FOOTER_SHADOW_DARK = 0.2
# }}}

# The star rating -- see calibre_zen/rating.py. Painted, not laid out. {{{
RATING_STAR = 16  # one star's box; shrinks to fit a shorter widget, never grows
RATING_GAP = 4  # between one star and the next, and the whole of it is a hit target
RATING_PAD = 8  # from the field's edge to the first star: PAD_FIELD's horizontal
RATING_STROKE = 1.4  # an empty star's outline
RATING_CLEAR = 9  # the clear cross, drawn at the end once there is a rating
RATING_STAR_CELL = 13  # in a book list cell, where it sits beside text
RATING_CELL_PAD = 3  # from a cell's edge, as far in as its text would start
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
# A row in a list that drops down under a field -- a combo box's own, or an
# autocomplete list: a menu item's height, no room held for a tick.
PAD_LIST_ITEM = '5px 8px'
LIST_GAP = 4  # between the field and the autocomplete list that opens under it
LIST_PAD = 4  # inside a dropping list's frame -- see theme/dropdowns.py

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
# A spin box's two steppers, stacked at its right end, and their chevrons.
SPIN_BUTTON_WIDTH = 18
SPIN_ARROW_SIZE = 8
# A rich text editor's toolbar button, around its 16px glyph -- see theme/richtext.py.
RICHTEXT_BUTTON_PAD = 3
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


# Download metadata -- see calibre_zen/download/. The match cards and the
# cover tiles are painted, not laid out, so these are their whole geometry;
# the headers, the side panel and the footer are widgets and take the sheet. {{{
DOWNLOAD_PAD = 16  # around each page, and either end of the footer
DOWNLOAD_GAP = 8  # between things on one line: header parts, footer buttons
DOWNLOAD_SECTION_GAP = 12  # between the header and the body, the list and the panel
DOWNLOAD_LINE_GAP = 3  # between the lines of a card, a tile or the panel
DOWNLOAD_FOOTER_PAD_Y = 10
DOWNLOAD_PAGE_TITLE_SIZE = 16  # "Choose a match", "Choose a cover"
DOWNLOAD_SPINNER = 16  # the header's, while covers arrive
DOWNLOAD_STATE_SPINNER = 28  # the searching state's, and a cover tile's
DOWNLOAD_SPINNER_STROKE = 2
DOWNLOAD_STATE_WIDTH = 360  # the most an empty state's words run across

DOWNLOAD_MATCH_HEIGHT = 108  # one card and the gap under it
DOWNLOAD_MATCH_GAP = 8  # between one card and the next
DOWNLOAD_MATCH_PAD = 12  # inside a card
DOWNLOAD_MATCH_COVER_W = 56
DOWNLOAD_MATCH_COVER_H = 84  # 2:3, as TABLE_COVER_W/H
DOWNLOAD_MATCH_TITLE_SIZE = 14
DOWNLOAD_MATCH_SOURCE_MAX = 150  # the card's right column: source and what it has
DOWNLOAD_MATCH_MIN_WIDTH = 360
DOWNLOAD_RING = 2  # a selected card's outline, and a selected cover's ring

DOWNLOAD_PANEL_MIN_WIDTH = 260
DOWNLOAD_PANEL_PAD = 16
DOWNLOAD_PANEL_TITLE_SIZE = 18  # the match's title, in the serif
DOWNLOAD_CHANGE_GAP = 8  # between the rows of What changes

DOWNLOAD_COVER_W = 120
DOWNLOAD_COVER_H = 180  # 2:3: the box a candidate cover is fitted into
DOWNLOAD_TILE_PAD = 12  # round the box inside its grid cell, and room for the ring
DOWNLOAD_RING_GAP = 3  # between a cover's edge and its ring
DOWNLOAD_TILE_TEXT_GAP = 8  # between the box and the lines under it
DOWNLOAD_TILE_TEXT = 40  # those two lines
# }}}

# calibre-zen overlay

Our UI work, kept out of calibre's source tree so `git pull` upstream stays
boring.

calibre draws its UI with Qt Widgets through the CalibreStyle proxy over
Fusion. That is correct, dense and thoroughly dated chrome, and none of it is
Qt's fault -- Fusion is styleable and nobody had styled it. This package is
that styling: colours, radii and spacing. Almost all of it is a stylesheet
and a palette, no widget is subclassed and no layout is touched, so the worst a
mistake there can do is look wrong.

`filters/` and `centre/` are the exceptions, and they are deliberate: the tag
browser and the book list draw and behave in code rather than in a stylesheet,
so no token could reach them. Those two replace widgets, and each has an off
switch of its own for the same reason the sheet does.

Off with `CALIBRE_ZEN_STYLE=0`, which is what makes before/after comparable;
`CALIBRE_ZEN_FILTERS=0` puts the tag browser's tree back and
`CALIBRE_ZEN_CENTRE=0` puts the book list back, each without giving up the
rest.

## The hook

One call, in `calibre.gui2.Application.__init__`, immediately after the
`PaletteManager` is constructed:

```python
self.palette_manager = PaletteManager(force_calibre_style, headless)
if not headless:  # the calibre-zen overlay -- see src/calibre_zen/README.md
    from calibre_zen.hooks import install as install_zen_overlay

    install_zen_overlay()
```

That is the whole upstream footprint of the theme. `install()` then patches
three things from the outside:

| patched | why |
| --- | --- |
| `palette.default_{dark,light}_palette` | module-level functions, resolved by name at call time, so replacing the attributes replaces the theme everywhere calibre asks for one -- including the palette editor in Preferences, which edits a custom palette starting from them |
| `PaletteManager.on_palette_change` | the one place calibre sets an application-wide stylesheet. Upstream still runs; our sheet is substituted for the one it was about to install, so `palette_changed` still fires once, after the finished sheet is applied |
| `PaletteManager.tree_view_hover_style` | a widget-local sheet calibre hands to the tag browser and a few other trees |

Ordering matters in one direction only: `install()` must run before anything
does `from calibre.gui2.palette import default_dark_palette`, because that
binds the function by value. Application startup is well before any dialog, so
the call site above is early enough.

`install()` is idempotent and returns whether the overlay is active.

## A fork, not a skin

Since `BUILDING.md`, calibre-zen installs *beside* calibre rather than being a
way of running it. That is one string -- `calibre.constants.__appname__` --
plus everything that must be derived from it rather than spelled out again:
the config and cache directories, the single-instance lock, the IPC endpoint,
the PATH names, the Linux desktop ids, the macOS bundle identifiers.

It matters here because it changes what the overlay is allowed to assume. The
rule below still holds for everything to do with *looks*: no upstream file is
edited to change how something is drawn, and `src/calibre_zen/` is reachable
from exactly one line upstream. Fork identity is a separate category, kept
narrow and marked `# calibre-zen:` in each file so an upstream merge conflicts
once. BUILDING.md lists every one.

One of those changes was a bug rather than a rename, and it is worth knowing
about because it is the sort of thing that only shows up when two copies are
running: upstream derives the single-instance lock from `__appname__` but
hardcodes the GUI socket as `/tmp/calibre-{uid}-gui.sock`. The lock therefore
let both applications start, and `Listener.start_listening` answers
`AddressInUseError` by calling `removeServer()` -- so the second one to start
took the first's socket, and "open in calibre" from the file manager went to
whichever had most recently launched.

## The rule

**Do not edit an upstream widget to change how it looks.** The point of the
overlay is that our diff against upstream is one hook, so a conflict during a
pull is about behaviour, never about styling. In order of preference:

1. Change a token. Most things are a token.
2. Change or add a rule in `theme/qss/app/`.
3. If a widget-local `setStyleSheet()` upstream is punching a hole through the
   app sheet, add an entry to `theme/rewrite.py`.
4. Only if none of those can work, edit upstream -- and say why in the commit.

## Layout

```
hooks.py              install(): the single entry point
theme/
  tokens/
    primitives.py     raw values: the colour ramps, two radius scales, the
                      font families and their size and weight scales
    schemes.py        a Scheme: one complete set of those choices, swappable
                      at runtime -- `neutral` and `zen` ship
    semantic.py       what each primitive is for: the active scheme's palette
                      map, and Chrome, derived at runtime from the palette
                      actually in use
    components.py     the radii, densities and typography the stylesheet asks
                      for by name
  generate.py         tokens -> QPalette, tokens -> QSS; also loads the
                      vendored fonts into Qt (install_fonts())
  qss/app/*.qss       the application-wide sheet, concatenated in filename order
  qss/local/*.qss     sheets calibre applies to one widget rather than the app
  marks/*.svg         check, dash, dot and the four chevrons; mark_url() for
                      QSS, mark_icon() for whoever is painting instead
  fonts/<name>/*.ttf  the vendored faces for each family CALIBRE_ZEN_FONT or
                      CALIBRE_ZEN_SERIF can select, see "Typography" below
  popups.py           gives a rounded popup a rounded window, see below
  splits.py           which half of a split tool button the pointer is on,
                      see "A split button says so" below
  rewrite.py          wraps setStyleSheet and setFont so a widget's own wins
  variants.py         tags a QPushButton primary/destructive when Qt gives a
                      signal for it, see "Buttons" below
filters/              the tag browser, replaced -- see "The filter panel" below
  __init__.py         install(): hides the tree and wraps four methods
  panel.py            FilterPanel: the nav bar, the list and Reset
  levels.py           what one screenful holds, and what a row does
  view.py             the list, its model and the delegate that paints a row
centre/               the centre pane -- see "The centre pane" below
  __init__.py         install(): the seven wraps
  layout.py           ZenCentre, the toolbar strip and the Grid/Table switcher
  preview.py          PreviewPane: the metadata header above the list
  table.py            the Details column: arrangement, delegate, covers
  grid.py             how big a cover-grid tile is: default/compact/tiny
  tiles.py            what a tile does under the pointer: a ring, a card,
                      and the quick actions
status/               the status bar, rebuilt -- see "The status bar" below
  __init__.py         install(): the six wraps
  bar.py              ZenStatusBar: one layout across the whole bar, and the
                      adoption of calibre's own widgets into it
  segments.py         a segment: library, sort, counts, server, jobs
icons/
  registry.py         which pack is active; wraps QIcon.ic
  pack.py             a pack: calibre's icon names -> a directory of SVGs
  packs/*.py          one module per provider, discovered not listed
  assets/<pack>/      the vendored glyphs, and the pack's licence
  vendor.py           copy newly mapped glyphs out of a downloaded icon set
```

### Tokens

Four layers, and a rule: **a `.qss` template may only name a semantic or a
component token.** A value that is in neither belongs in one of them, not in
the rule.

`primitives` holds raw values and picks between none of them. A **`Scheme`**
does the picking: which ramp, which radius scale, which blend recipes, which
six colours have to carry a hue. `semantic.Chrome` is then computed from
whatever palette is installed at the time -- ours, or one of the custom
palettes calibre lets users define in Preferences. Borders, hovers and
scrollbars are blends of that palette rather than fixed greys, which is why a
sepia theme gets sepia chrome instead of stubbornly blue-grey chrome. Write
rules against `Chrome`, never against a scheme's map.

Numbers that appear once and mean nothing anywhere else -- a 6px nudge on a
menu indicator -- stay literals in the QSS, next to the rule they affect.

### Colour schemes

Six ship, and `CALIBRE_ZEN_SCHEME=<name>` or the toolbar's appearance menu
chooses between them:

| scheme | what it is |
| --- | --- |
| `neutral` | no tint at all. The default. |
| `stone` | warm, tinted brown. |
| `zinc` | cool, tinted blue. |
| `olive` | warm, tinted yellow-green. |
| `mist` | cool, tinted teal. |
| `zen` | the odd one out: the overlay's original, one blue accent. |

The first five are shadcn/ui's neutral presets, and they differ from each other
**only in the ramp** -- same lightness steps, same alphas, same destructive
red, same radius. So the arrangement is written once, as `schemes.shadcn()`,
and each preset is a ramp and a name. Adding a sixth is a ramp in
`primitives.py` and one line.

A scheme is four things, and only the first is a list of colours:

- **roles** -- `QPalette.ColorRole` to a hex value, per mode.
- **blends** -- the ratios `Chrome` derives a border, a hover or a scrollbar
  from. Ratios rather than colours is what keeps a scheme compatible with a
  custom palette: every derived colour still comes from the palette actually
  installed.
- **named chrome** -- the colours a scheme states outright instead of deriving.
  See below; a tinted ramp cannot do without them.
- **radius** -- the six-step scale. Roundness is as much a scheme's identity
  as its greys are, so `components.refresh()` re-reads the radii whenever the
  scheme changes, and `generate.mapping()` calls it on every re-theme.

These are the shadcn token sets rather than something in their spirit, and the
check asserts each one against its published table -- typed out from the export
rather than read back off the ramp, or it would only prove the ramp equals
itself. It also pins the three steps no table states outright (`--chart-1`,
`--chart-3` and `--chart-4` are the ramp at 87, 44 and 37), and confirms that
in dark `--border` and `--input` reproduce white at 10% and 15% over `--card`
to within a value.

### Dim

shadcn's dark is very nearly black -- a `#0a0a0a` page -- which is a look, and
not one everyone wants to sit in front of. **Dim** is the same arrangement with
a higher floor: `#1f1f1f` under `#2e2e2e` on the neutral ramp, a soft charcoal
rather than an unlit screen.

It is not a scheme. A scheme is a ramp, and darkness is a depth, so making it
one would have doubled the list to twelve instead of multiplying with it. It is
a second set of **step positions** read off whatever ramp the active scheme
already has:

| | page | card | raised | line | faint | shadow |
| --- | --- | --- | --- | --- | --- | --- |
| `dark` | 15 | 21 | 27 | 37 | 44 | 0 |
| `dim` | 24 | 30 | 37 | 44 | 52 | 10 |

`schemes.at()` reads a ramp at a lightness it has no step for by interpolating
between its neighbours -- *within* the ramp, which is what keeps the tint that
blending its two ends loses. So dim Mist is still teal (`#1c2224`) and dim
Olive still yellow-green (`#24241c`); only the floor moves. The gap between
page and card is held at what shadcn has, so a dim UI has the same depth and
not a flatter one, and the foregrounds do not move at all: they are already at
the far end of the ramp, and `--primary` is a near-white fill whose label has
to stay dark whatever the page does.

The `zen` scheme has no dim of its own and hands back its dark, which was
always a soft one (`#1a1c1f` under `#24262a`).

**calibre still thinks it is dark.** `gprefs['color_palette']` stays `'dark'`
and our own `zen_dark_variant` says how dark, which is what keeps
`is_dark_theme`, the palette editor and everything downstream working -- the
only thing that changes is which palette `default_dark_palette` hands back. In
the appearance menu it is a fourth entry between Light and Dark;
`CALIBRE_ZEN_DARK=dim` does the same thing.

### Why a tinted ramp cannot derive its own chrome

`Chrome` blends between the window colour and the text colour, which for these
ramps are its two *extremes* -- and in a tinted ramp both extremes are very
nearly neutral, because the tint lives in the mid-tones. Stone's
`--muted-foreground` is `#79716b`, 14 apart across its channels; blending its
`#fafaf9` toward its `#0c0a09` gives `#757473`, 2 apart. Derived chrome would
quietly flatten all five presets back to the same greys, which is the one thing
that distinguishes them. It is a real limit of the model, not a tolerance to
widen: it was found by the check failing on Stone, Zinc, Olive and Mist while
Neutral passed.

So where the token set states a value *and* that value is a step of the ramp,
the scheme says so rather than deriving it: `border`, `border_strong`, `muted`,
`surface` and `surface_hover`. `Chrome` applies those **only while the scheme's
own palette is the one installed** -- it compares Window and Base -- so editing
a custom palette in Preferences puts every colour back to being derived from
what the reader chose, which is what the blends were always for. The `zen`
scheme names nothing and is derived exactly as before.

Three places the presets depart from the document, each on purpose:

- **Window and Base carry the two surfaces.** shadcn has a page colour and a
  card colour, not a gradient of them, and Qt's Window/Base split is what can
  hold that: Window is the chrome a panel or a toolbar sits on (`--sidebar`),
  Base is the page a list or a field is drawn on (`--background`). In dark the
  chrome therefore sits a step *lighter* than the page, which is the inverse of
  the `zen` scheme and is what makes those dashboards read the way they do.
- **Tooltips stay dark in both modes.** Theirs invert, which in dark means a
  white slab over a black UI. The overlay's own rule wins: a tooltip is an
  overlay, one step up from the surface it floats on.
- **Links keep a hue.** The sets are pure greyscale; a link that is not a hue
  is not a link. Tailwind blue, which is the same family as `--sidebar-primary`
  -- the one chromatic token in their own export, and the same in all five. The
  destructive red is theirs unchanged, and is shared by every preset.

The radii are the scale at our density, not its pixel values: their base is
10px drawn for controls about 36px tall, and ours are about 26px, so the same
ratio gives 3/4/5/6/8/10. Every preset shares it.

The six sit in a **submenu** under the appearance button rather than inline.
The job that menu is opened for is flipping light and dark; a scheme is chosen
once and then left, and six of them inline would bury the three that are not.

Switching is one call. `set_active()` stores the choice and invalidates the
radii; applying it is `PaletteManager.refresh_palette()` -- the identical path
the light/dark switch takes, because that rebuilds the palette from the
functions the overlay installed as `default_{dark,light}_palette` and ends in
`on_palette_change()`. Choosing a scheme and choosing a mode are the same
operation with a different input.

### QSS

QSS has no variables, so templates use `$name` / `${name}` and are substituted
in `generate.py`. `$` rather than `{}` because QSS is nothing but braces: a
`.format()` template would have to double every one of them and would stop
being readable as a stylesheet.

Files in `qss/app/` are concatenated in filename order -- that is what the
numeric prefixes are for, since later rules win among equally specific ones.

Qt stops drawing a subcontrol natively the moment you style it, so the rounded
accent-filled check and radio marks have to supply their own glyph, and QSS
`url()` wants a real file. `generate.mark_url()` renders `marks/*.svg` for the
current accent colour into the cache directory, once per colour.

### Typography

`Inter` by default, four vendored weights (`theme/fonts/inter/`), loaded once
by `generate.install_fonts()`. `${font_family}`, `${font_size_base}`,
`${font_size_caption}` and `${weight_heading}` are the names a template has
for it, the same as any other component token.

The four files share one typographic-family name record, so Qt's font
database groups them under a single family and a template can ask for
`font-weight: 600` and get the real SemiBold face rather than a synthesized
one -- checked with `QFontInfo.exactMatch()` against this build's Qt before
vendoring anything, not assumed from how the files are named.

**There is a second family, not a second choice.** `Literata` is loaded
alongside the UI family, not instead of it, and exactly one thing uses it: a
book's title in the preview. A serif is a signal there precisely because it is
not used anywhere else, and Literata rather than a general-purpose serif
because it was drawn for Google Play Books -- a face meant to be read in a
book-shaped context, which is what that label is. `${font_family_serif}` is
its name in a template, `CALIBRE_ZEN_SERIF=<name>` swaps it on the same terms
as `CALIBRE_ZEN_FONT`, and `install_fonts()` loads both, skipping the second
pass if they name the same family.

`CALIBRE_ZEN_FONT=<name>` selects a different UI family for comparison --
`droid-sans` and `literata` are the others vendored right now. `primitives.FONTS` is the
whole registry: a short name to a family, the directory under `theme/fonts/`
it lives in, and the face files to load. Every family is asked for all four
weights in `FONT_WEIGHT` regardless of how many it actually has real faces
for -- Qt substitutes its nearest match rather than failing, which is exactly
what a quick comparison needs and not what the shipped default should settle
for silently. **Adding a family** is one entry in `FONTS`, its faces under
`theme/fonts/<name>/`, and its licence alongside them -- nothing else is
edited, the same shape as adding an icon pack.

The gotcha worth knowing before touching this again: Qt's application
stylesheet does not cascade the way CSS specificity suggests. A
`QWidget { font-family: ... }` rule in the app sheet overrides a widget's own
`setFont()` call, not the other way round -- checked empirically, not assumed.
`00-typography.qss` sets the base rule on `QWidget` anyway, deliberately, to
reach the whole app in one rule instead of an allowlist of chrome classes.

The fix for the trade-off is `rewrite.contain_fonts()`: it wraps
`QWidget.setFont` the same way `rewrite.install()` wraps `setStyleSheet`, and
mirrors every `setFont()` call into a rule on that widget's own sheet -- which,
being local, wins the same way a hand-written `setStyleSheet()` already does.
That restores the font a code editor or a font-preview label actually asked
for without this overlay having to know, ahead of time, which of calibre's
several dozen `setFont()` call sites matter. `grep -rn '\.setFont(' src/calibre/gui2`
still finds them, for whoever is checking one.

### Buttons

calibre builds every `QPushButton` the same Qt way, with no concept of
"primary" or "destructive" -- there is no `variant` prop to read the way there
would be on a web component. `theme/variants.py` recovers what signal Qt
actually gives, and is honest in the QSS comments and in its own docstring
about where that signal runs out:

- **Primary** is `QPushButton:default` -- free, already set by calibre (~30
  explicit `setDefault(True)` calls) or by `QDialogButtonBox` for the
  Accept-role button. `02-buttons.qss` turns it from a border tint into a
  solid accent fill: one clear action per dialog, `$accent_hover` /
  `$accent_pressed` blending toward text the same way an ordinary button's
  hover/pressed already do.
- **Destructive** has no Qt signal at all -- `DestructiveRole` exists on
  `QDialogButtonBox` but calibre never uses it, checked across the whole of
  `gui2`, zero hits. The only real signal left is the icon a delete button
  already carries. `variants.py` wraps `IconResourceManager.__call__` to
  remember the `QIcon.cacheKey()` for any name in `DANGER_ICON_NAMES`
  (`trash.png` only, on purpose -- `minus.png` and friends are used for
  ordinary list-row removal too often to read as "destructive"), then wraps
  `QPushButton.__init__` *and* `setIcon` to tag a button that receives one --
  both, because `QPushButton(icon, text)` sets the icon from the compiled
  constructor, which does not call back into a Python-level `setIcon`
  override. Checked empirically, not assumed, the same way the font gotcha
  above was. The tag is a plain dynamic property (`zenVariant`), read back in
  QSS as `QPushButton[zenVariant="destructive"]`.
- **Ghost** (`QPushButton:flat`) already existed in the sheet; upstream just
  never sets it -- `setFlat(True)` on a push button is zero occurrences across
  `gui2`. The rule stays, for whenever something does.
- Everything else -- roughly 330 of calibre's ~376 `QPushButton`s, the ones
  with no default, no destructive icon, no flat flag -- gets one consistent
  resting style: same radius, height, padding and border as every other
  button, which on its own is most of the actual "stop looking random" fix,
  variant colour or not.

`DANGER_ICON_NAMES` is one name today. Finding the next one is the same
`grep -rhoE "QIcon\.ic\('[a-zA-Z0-9_./-]+'\)" src/calibre/gui2` this one came
from, read against whether a name is used for something genuinely hard to
undo -- not just "removes a row."

### A split button says so

calibre's toolbar carries two kinds of button wearing one skin. A
`MenuButtonPopup` button is **two** targets -- the icon runs the action, the
strip on the right opens the menu -- and an `InstantPopup` button is one target
that opens a menu. Both draw the same chevron, so the only way to find out
which kind you were pointing at was to click it and see what happened. Which
one an action gets is `InterfaceAction.popup_type`, and it is set per action:
Add Books and Edit Metadata are split, Connect/share and Choose Library are
not.

Two marks fix it. At rest a split button draws a **seam** between its halves.
Under the pointer the menu strip **fills** -- and only when the pointer is
actually on it.

The second of those is not something Qt will tell you. A hovered tool button
reports `activeSubControls = SC_ToolButton` whichever half you are over, and
`QStyleOptionToolButton` only names `SC_ToolButtonMenu` once the menu half is
*pressed* -- measured with real hover events against an offscreen button, after
assuming the opposite. So `QToolButton::menu-button:hover` fires for the whole
button and lights the strip when the pointer is nowhere near it, which is
exactly the ambiguity the seam is there to remove. `theme/splits.py` asks the
style where the strip is -- so the answer follows the sheet's own `width`
rather than a number repeated in Python -- and writes the half into a dynamic
property the sheet selects on. Re-polishing is what makes a property rule take
effect, so it happens once per crossing of the seam rather than once per mouse
move, and the filter is installed from calibre's two `setup_tool_button`
methods rather than application-wide, because hover moves are the
highest-volume event there is.

Two things went wrong on the way and both were caught by measuring rather than
by looking:

- The seam's first version was `$border` inset 6px from the button's top and
  bottom. A `QToolBar::separator` on that bar is `$border`, 23px tall -- and
  the seam came out `$border`, 23px tall. A division *inside* one button and a
  division *between* two groups were the same mark. The seam is now the shorter
  and lighter of the two.
- The inset that makes it shorter is a `margin` on the `::menu-button`
  sub-control, and a margin shrinks the sub-control's whole box, not just its
  border -- so the menu half's hover fill came out as a 15px band floating in
  the middle of a 35px button. The margin is dropped while a half is tracked,
  because under the pointer the fill is doing the dividing anyway.

`CALIBRE_ZEN_SPLIT=0` keeps the seam and hands the hover back to Qt, which
lights the whole button as one shape.

**The far end of the bar.** `theme/appearance.py` also puts an expanding spacer
before the run of app-level buttons at the end of the toolbar, so the left of
the bar acts on books and the right is the application. Where that run starts
is read off the bar rather than off the preference: a reader who has moved
Preferences into the middle has no trailing run, the spacer goes at the end,
and their arrangement is left exactly as they left it. It is inserted after
`init_bar` has recorded `preferred_width`, so the width the bar compares
against when deciding whether to drop its labels is still the width of the
buttons alone.

### The filter panel

The category list on the left -- Authors, Series, Tags and the rest -- is a
`QTreeView` (`TagsView`) with its own delegate, and it is the one part of
calibre's chrome a stylesheet was never going to fix. Dense click-to-cycle rows
with a tri-state icon are a *behaviour*, and there is no token for a behaviour.
`filters/` replaces it with the flat filter sheet in the reference: one row per
category showing what it is filtering by, and one screen per category to choose
in.

**The tree is hidden, not removed, and that is the whole trick.** `TagsView`
stays alive and keeps its model, its recounts, its database listener and its
context menu, and stays the object the rest of calibre talks to -- `gui.tags_view`
is referenced from a couple of dozen places and every one of them keeps working.
The panel is a second view onto the same `TagsModel`, which is a thing Qt models
are for. Nothing about search, renaming, or the twenty signals
`init_tag_browser_mixin` connects is reimplemented or rerouted, and marking a
value goes out through `TagsView.tags_marked` exactly as a click on the tree did.

Four wraps, all from outside:

| wrapped | why |
| --- | --- |
| `TagBrowserWidget.__init__` | build the panel, put it where the tree was, hide the tree |
| `TagsView.set_database` | the first moment the model has a database and the Configure menu has the action groups "Sort by" and "Match" are read from |
| `TagsView.indexAt` | answers with the right-clicked row *while the panel is asking*, so `show_context_menu` -- untouched -- builds calibre's real menu for our row |
| `TagsView.show_item_at_index` | keeps the Find box working: calibre says "show this", and the panel opens the levels above it instead of scrolling a tree nobody can see |

Three things are worth knowing before changing it:

- **Rows address the model by named path, never by `QModelIndex`.** A recount
  throws the whole node tree away and builds a new one, so an index the panel
  was holding is stale the moment a book is added. `TagsView.recount` remembers
  a named path across its own rebuild for the same reason.
- **A click is never exclusive.** Upstream clears every other mark unless Ctrl
  is held, which is right for a tree you click through and wrong for a sheet
  whose whole shape says "tick what you want". Reset, at the foot of the panel,
  is how you get back to nothing.
- **The list is painted, not built.** A category in a real library is routinely
  several thousand values, and a column of that many row widgets is a visible
  stall on every recount. It is a `QListView` with a delegate, so nothing exists
  per row; the *background* of a row is still handed to the style first, which
  is what keeps hover and the panel's colours in `qss/app/11-filters.qss` with
  the rest of the look.

The grouping into "Filter by --" sections is ours, and it is invented: calibre
has no notion of what a category is *about*. It is recovered from the only
signal the keys carry -- `@` is a user category, `#` a custom column, `search`
the saved searches -- and the user's configured order is kept *within* each
section, so rearranging categories in Preferences still does what it says.
Changing the grouping is `sections()` and `section_for()` in `levels.py`, and
nothing else.

What the tree did that this does not: dropping books onto a category, several
categories open at once, and keyboard navigation. The module docstring in
`filters/__init__.py` is the current list.

### The centre pane

The book list is a `QTableView` that paints nothing itself -- every cell goes
through a delegate assigned per column by `TableView.set_delegates`
(`pin_columns.py:128`). So unlike the tag browser, the look here was reachable
without replacing the widget at all; what had to change was the arrangement
around it.

```
ZenCentre
├── PreviewPane        the metadata header, see preview.py
├── CentreToolbar      calibre's SearchBar, moved in whole, + the switcher
└── gui.stack          calibre's real QStackedWidget, untouched
```

`CentralContainer` is handed the centre exactly once, as one opaque widget
(`central.py:423`), and everything it does to it afterwards is reparent,
`setVisible` and `setGeometry`. So one wrap of `initialize_with_gui` puts the
wrapper in its place, and `gui.stack` keeps the identity that `ui.py:1050` and
`ui.py:1192` address by index.

The switcher switches nothing itself: it sets `gui.grid_view_button`'s checked
state and calibre's `AlternateViewsButtons.toggle_view` (`init.py:309-323`)
does the showing, the un-checking of the bookshelf button, the sort button's
visibility and the preference. Same reason the filter panel's Sort-by row
drives real `QAction`s -- the day upstream changes what switching a view means,
this follows for free.

**Details is not a new column.** It is the `title` column taken over: its
header reads "Details", its cell paints the cover, the series line, the bold
title and the author, and `authors` and `series` are hidden because they now
live inside it. The strings come out of those hidden cells --
`model.index(row, column_map.index('authors')).data(DisplayRole)` -- because
hiding a section does not remove it from the model, so they are already there
and already formatted the way the reader asked for. No metadata lookup per
paint.

**Nothing of that reaches the reader's library.** `get_old_state` and
`write_state` (`views.py:1001, 1127`) are the only two methods that name the
per-library column pref, so they are pointed at a key of our own. The overlay's
layout persists normally into that key, calibre's is never written again, and
`CALIBRE_ZEN_CENTRE=0` hands back the layout the reader had. It also means the
arrangement is expressed as a **state dict** and handed to `apply_state`, so
the hiding and the moving happen in calibre's own code with its own
save-state batching and its own Qt relayout workaround -- nothing here calls
`setSectionHidden` or `moveSection`.

Two things worth knowing before changing it:

- **A row card is drawn one cell at a time**, because that is the only place a
  `QTableView` lets anyone draw. Adjacent cells fill identically with no gap
  and only the row's two outer ends are rounded, so N cells read as one rounded
  row. `qss/app/12-centre.qss` takes the item's own background away or Qt paints
  over the card on every cell but the first.
- **Row height is the vertical header's**, not the delegate's `sizeHint`
  (`views.py:1196-1210`), and `BooksModel` caches it -- both have to be set.

Editing, sorting, resizing and the column-header context menu are untouched:
`ZenCellDelegate` wraps whatever delegate calibre assigned and forwards every
editing method to it, so a rating column still opens a rating editor.

**The preview** is the header every modern reading app puts above a book:
cover, series, title, authors, a line of facts, the tags as pills and the
description. Everything comes from `db.new_api.get_proxy_metadata(book_id)`,
which reads each field only when asked, and is rendered with
`ProxyMetadata.format_field` -- calibre's own formatter, so the rating arrives
as "4.5" out of five rather than the 0-10 integer stored, a date as "Mar 2015"
in the reader's locale and a series as "Name [2]". Formatting them here would
mean disagreeing with every other place in calibre that shows the same value.

Only what is known is shown: no series line on a standalone, no star on an
unrated book, no empty gap between two separators. Ratings counts, reader
histograms and genre taxonomies are in the references this is built from and
have no local equivalent, so they are not invented. calibre's own Book details
panel is untouched -- this is the glance, that is still the full record, and
the two are not meant to converge.

The description **truncates**. `QLabel` can wrap and it can elide, but not
both -- `ElideRight` on a word-wrapped label elides nothing and the text runs
straight off the bottom, which is what a long publisher blurb did to the whole
panel. `ElidedLabel` lays the text out with `QTextLayout` and elides the last
line that fits, so the number of lines follows the height the splitter is
giving it rather than being a constant someone had to pick.

Underneath is a row of **quick actions**: the things you would otherwise
right-click the row to reach. Read is outlined in the accent rather than filled
with it -- it is the most likely thing to press, not the only safe one, and a
solid accent block above a row of flat buttons reads louder than it deserves.
Its glyph is re-tinted to match, because the icon pack renders everything in
the palette's text colour and a text-coloured icon inside an accent-coloured
label is the mismatch the eye finds first. The other labels are left at full
strength for the same reason, since their glyphs are: what makes them read as
secondary is the missing frame, not a paler word.

The rest are the first few entries of the
book list's own context menu, in the order they are in, and the overflow button
pops that very menu. Nothing is named here except Read, so a reader who
rearranges Preferences -> Toolbars & menus -> The context menu gets their own
choices in this bar too. `setDefaultAction` does the work: each button takes
its action's icon, text, tooltip and -- the part that matters -- its enabled
state, which calibre already keeps in step with the selection.

Two Qt traps live in that bar, both commented where they bite. calibre builds
the context menu *after* it sets the database (`ui.py:432` against `ui.py:393`),
so the bar cannot be filled when the panel attaches and is built lazily
instead. And the description's `Ignored` vertical policy -- which is what stops
a long blurb from growing the panel -- will squeeze any sibling that does not
insist on its own height down to nothing, so the bar is `Fixed` and calls
`updateGeometry()` once it has something in it.

It is the one part of the centre where the look is a stylesheet again: a
handful of real `QLabel`s that change on selection, not thousands of rows that
change on every scroll.

**Grid tile size** is three densities -- default, compact, tiny -- on the view
switcher's menu, because that is the control that already chooses the grid.
calibre computes one tile size from `cover_grid_height`/`_width`, both of which
default to 0 meaning "a fifth of the screen's height" (`alternate_views.py:77`),
and there is nothing between that and typing centimetres into Preferences.

It is a **multiplier**, the same shape as `TOOLBAR_ICON_SIZE` re-scaling
calibre's five icon settings: whatever Preferences -> Cover grid says still
decides the base, and the density only changes the scale under it. `default` is
1.0 and has to stay 1.0 -- that is what makes it switchable off.
`CoverDelegate.set_dimensions` is wrapped rather than reimplemented, and the
original's answer scaled afterwards, so the title strip and the emblem gutter
(four more preferences) keep working without `grid.py` knowing their rules. Two
things deliberately do not scale: the title strip, because text at 44% is not a
smaller label but an unreadable one, and an explicitly configured spacing,
because that is a number the reader typed. `CALIBRE_ZEN_GRID=<name>` overrides
the stored choice for a session.

What is not done: how a grid tile is *drawn*, and the reference's "Add column"
pill -- calibre's column-header context menu already does that job. Header labels stay centred, because `HeaderView.paintSection`
hard-codes `AlignHCenter` (`views.py:125`) and changing one flag would mean
reimplementing its sort-indicator and elide handling.

### One shape for every tile

calibre scales a cover to *fit* the tile's cover box and centres it, so a 2:3
cover fills the height, a squarer one fills the width and stops short, and a
shelf of them has a ragged edge where the tiles do not. `grid.fill()` crops
every thumbnail to cover the box instead. The book table already did this for
its row thumbnails, so this is the grid catching up rather than a new idea.

It is done to the **pixmap**, not to the painting, which is what makes it
cheap and what makes everything else fall into place: a thumbnail that already
fills the box leaves calibre's own centring offsets at zero, so the cover, the
ring around it and the embossed emblem's right offset all line up without any
of them being told about it. The crop is keyed on the pixmap's own cache key,
so a cover is cut once rather than on every repaint of every visible tile, and
a re-rendered thumbnail gets a new key by itself.

Filling means trimming, so the cost was measured rather than waved at. Against
calibre's default tile -- three quarters as wide as it is tall -- over a real
shelf:

| | trim |
| --- | --- |
| median cover | 6% of one dimension |
| worst | 13% |
| over 8% | 3 of 31 |

That also settled a wrong instinct. Covers cluster nearer 4:5 than 2:3, so
re-shaping the tile to 2:3 -- which sounds like the shape of a book, and is
what `TABLE_COVER_W/H` uses for the much smaller row thumbnail -- would have
taken the median trim to **16%**, not less. Whatever tile the reader has
configured is the right one to fill.

The crop is central, because a cover's title is usually at the top and its
author at the foot and trimming from one end would reliably cut one of them.
`CALIBRE_ZEN_GRID_CROP=0` turns the whole thing off and gives back the ragged
shelf, for anyone who would rather see every cover whole.

### Cover-grid tiles

`tiles.py` gives a cover under the pointer -- or selected -- a **ring**, and a
tile the pointer rests on a **card** above it with the title, its year, the
author and the series.

The ring **replaces** the tile's fill rather than joining it. Upstream's first
act in `CoverDelegate.paint` is a full-tile selection highlight, which in these
palettes is the accent -- the same colour the ring wants to be, so on a focused
view the two cancelled out and the ring vanished. The state flags are cleared
before the original runs, the same way `table.py` clears them before handing a
cell to calibre's delegate. A tile is an object rather than a band: it takes an
outline, not a wash. Selected draws the accent, hovered draws `muted`, and
selected wins when it is both.

The ring is drawn from a wrap of **`paint_cover`**, which upstream calls with
exactly the cover's rectangle -- the one rect in that delegate that knows where
the artwork ended up after being centred in a tile that is rarely its shape.
`paint` is wrapped too, but only to leave the row and the state flags somewhere
`paint_cover` can find them: it is handed a painter, a rect and a pixmap and
nothing else. Re-deriving that rect out here from `MARGIN`, the title height
and the pixmap's size is six lines of arithmetic that would go quietly wrong
the next time upstream changed one of them.

It is concentric with the cover's own corners, which are a reader preference
and can be a percentage or a number of pixels: a percentage grows with the box
by itself, an absolute radius has to be grown by hand. `GRID_RING_GAP` plus
`GRID_RING` comes to 4, which is `CoverDelegate.MARGIN` -- any more and the
ring is drawn outside the tile it belongs to.

The card is a `Qt::ToolTip` window with a pointer, placed against the tile
rather than the cursor, and it is the tooltip surface rather than a colour of
its own -- it is a tooltip, and a second opinion about what a floating panel
looks like is the thing this overlay exists to remove. It flips below the tile
when there is no room above, and when a card near the edge of the screen has to
be pushed sideways the pointer keeps aiming at the tile. It waits
`GRID_CARD_DELAY` for the pointer to rest: sweeping across a shelf of covers
should not fire twenty tooltips, and the ring is instant feedback enough while
the pointer is still moving. `helpEvent` is wrapped to report "handled" without
showing anything, so calibre's own tooltip does not fight it for the same
corner of the screen; the card carries the same facts, the series line
included.

Hover is tracked by one event filter on the viewport rather than read off
`option.state`, because the card needs the tile's rectangle and a rest timer
anyway, and one filter answers all three questions.

**The quick actions.** A pill over the cover's foot: select, edit metadata,
book details, remove. Three of those are calibre's own actions, looked up in
`gui.iactions` and *triggered* -- so Edit metadata is the same dialog, and
Remove books is still the thing that asks before it removes anything. Only the
selection toggle is ours, because selecting is a view's business and no action
plugin does it.

What an action acts on follows the rule every file manager uses, and calibre's
own views use before they show a context menu: a tile **already in the
selection** leaves the selection alone, so a button pressed on one of five
chosen books acts on all five; a tile outside it becomes the selection on its
own.

Three things about it were found by looking rather than by reasoning:

- **The glyphs have to be re-inked.** An action's icon is drawn in the window's
  text colour, and this pill is dark in *both* themes because it floats over a
  cover rather than over the window. Left alone, every glyph in the light theme
  would be black on a black pill. They go through `preview.tinted()` against
  `Chrome.scrim`'s foreground -- `scrim` being the one surface in the whole
  overlay that is not derived from the palette, because what is behind it is
  artwork and could be any colour at all.
- **A plain `QWidget` paints no background from the application sheet** unless
  it is told its background is styled (`WA_StyledBackground`). Without it the
  pill is not square, it is *absent*, and the glyphs float over the cover with
  nothing behind them.
- **Reaching for a button is leaving the viewport**, because the bar is a child
  widget and takes the pointer off it. Treating that `Leave` as leaving the
  tile made the bar vanish from under the cursor on its way to being clicked,
  so `Leave` is ignored while the pointer is inside the bar's own geometry.

A tile too small for the pill -- the `tiny` density on a narrow window -- keeps
its cover instead. The card still appears, and the context menu still has
everything.

A warning for anyone verifying this kind of thing: `QWidget.render()` defaults
to `DrawWindowBackground`, which paints the background brush as a flat
rectangle. That is not what a child widget does on screen, and it made these
corners look square through two rounds of chasing a bug that was not there.
Render with `DrawChildren` alone.

### The status bar

calibre's bar spends its widest column on `calibre 9.14 created by Kovid
Goyal`, and its right-hand end on four widgets put there by four unrelated
pieces of code. `status/` replaces what it says without replacing what it can
do.

The dividing idea is that a status bar reports **what is going on behind the
window** and gives one click to it. On the left, what you are looking at: which
library, what the list is sorted by, how many books and how many of them are
selected. On the right, what the application is doing without you: whether the
content server is up, and how far through the background jobs are. calibre's
own layout toggles sit between the two.

| segment | reads | a click |
| --- | --- | --- |
| library | the open library | `Choose Library`'s menu |
| sort | the field and direction | `Sort By`'s menu |
| counts | books, filtered, selected | nothing -- it is text |
| device | a connected reader | nothing |
| message | whatever calibre said | nothing |
| layout | calibre's own toggles, moved | calibre's own behaviour |
| server | on, and the port | starts or stops it |
| jobs | how many, and how far | opens the Jobs window |

Not one of those clicks is implemented here. A menu segment shows the QMenu
that already belongs to calibre's action -- the same object the toolbar button
opens, so both stay in step including the `aboutToShow` handlers upstream fills
them with -- and the server segment calls `toggle_content_server`, so the
confirmation calibre shows while the server winds down still appears.

**Why one widget instead of styling the bar.** `QStatusBar` is not a layout so
much as three of them, and the spacing between two buttons in it is decided by
`QStatusBar::reformat`. So the bar gets a single child holding a single layout,
and calibre's widgets are adopted into it: the update notice, the layout
toggles, the Layout button and All-actions keep their code, their preferences
and their behaviour, and only move house. `place_layout_buttons` rebuilds that
run whenever the window changes shape, so it is wrapped and the adoption runs
again.

**Messages.** That takeover has one consequence worth naming: `QStatusBar`
shows a transient message by hiding every non-permanent widget it holds, which
with one widget holding everything would blank the bar for as long as the
message lasts. `showMessage` and `clearMessage` are wrapped and routed to a
label inside the bar instead -- the Qt methods rather than calibre's
`show_message`, which leaves its tray-notification half untouched.

**The percentage** is the mean across running jobs, drawn as a rule along the
segment's bottom edge rather than as a bar behind the text, which would turn
the label into something that flickers between two colours. The mean is the
only honest summary of several: the worst would say a two-second job had
stalled, and the best would promise a conversion was nearly done. It is free to
compute -- `JobManager` already recomputes `percent` on its own timer and emits
`dataChanged` when it does.

**The version and the attribution** are not dropped. They are in Help -> About,
which is where a version number is looked for, and the bar's widest column is
worth more as a reading.

`CALIBRE_ZEN_STATUS=0` gives calibre's bar back exactly -- checked by
photographing both.

### Appearance

calibre has had the setting all along -- `gprefs['color_palette']` is
`system`, `light` or `dark`, and `PaletteManager.refresh_palette()` applies it
to a running window. What it has not had is a way to reach it without opening
Preferences, picking a category and finding a combo box. `theme/appearance.py`
puts it on the toolbar: one button, three modes, nothing about how the palette
is chosen or applied reimplemented. The same menu carries the colour schemes
(see "Colour schemes" above), which are ours rather than calibre's but apply
through the identical path.

It is added from a wrap of `BarsManager.init_bars` rather than once at startup,
because that method clears and refills the bars whenever the toolbar
preferences change (`bars.py:778-787`) -- anything appended outside it
disappears the first time a reader edits their toolbar.

The switch is live because `refresh_palette()` ends in `on_palette_change()`,
which the overlay already wraps to re-render its sheet. What did not survive it
was everything the overlay *paints* rather than styles, so those are re-inked
from the same signal: the icons (see "Colour, unlike the pack" above), the
table's cached `Chrome` -- two dozen blends, built once per palette rather than
per cell -- and the preview's marks and tinted glyph.

### A glyph on the selection fill

A highlighted menu item flips its label to `HighlightedText`. Its icon used to
stay in the window's ink, which in the light theme means `#0a0a0a` on a
`#171717` fill -- about 1.05:1, which is not a dim icon, it is no icon at all.

`LiveIcon` holds a palette *role*, and the **mode** Qt asks for now decides
which colour that role resolves to. Which modes those are was measured rather
than assumed, by recording what each widget asks the engine for:

| where | mode |
| --- | --- |
| menu item, highlighted | `Active` |
| item view, selected row | `Selected` |
| tool button, pressed | `Normal` |
| anything disabled | `Disabled` |

So `Active` and `Selected` -- and only those -- resolve to `on-accent`
(`HighlightedText`). A pressed tool button comes through as `Normal`, which is
right: its background is a translucent wash, not the accent, and its label does
not flip either.

That left one contradiction to settle. Qt hands an item view the **same**
`Selected` mode whether or not the view has focus, but the sheet used to give
an unfocused selection a pale wash *and* normal-coloured text -- so the glyph
would have flipped while the label beside it did not, which is the same bug
upside down. The unfocused selection is now a weaker accent rather than a
different idea: it keeps `HighlightedText` for both, and
`Blends.selected_inactive` was solved per scheme for the weakest fill its own
label still clears 3:1 on. Every scheme and mode is asserted, along with the
fill staying visibly quieter than a focused row's. The blue scheme needs almost
the full accent to get there, which is its own comment on the blue.

### Rounded popups

`border-radius` on a menu, a tooltip or a combo box's list rounds what the
sheet *draws*. The window it is drawn into is still a rectangle, and Qt fills
that rectangle with the widget's background before the sheet paints over it, so
each corner keeps a square block and the rounding never shows. With the dark
scheme installed, every pixel of a menu's grab -- `(0, 0)` included -- comes
back `#171717` opaque; a combo box's container comes back `#0e0e0e` behind a
`#171717` list, which is why that one reads as a defect rather than as a square
menu.

`theme/popups.py` sets `WA_TranslucentBackground` on those windows, which stops
Qt pre-filling the rectangle so that whatever the sheet does not paint stays at
alpha 0. It has to be set before the platform window exists, which means at
`Polish` -- by the time anything holds a reference to a menu it is usually too
late.

Nothing there knows any widget by name. The rule is **a top-level popup**
(`Qt::Popup` or `Qt::ToolTip`), which is what those three have in common and
what every other rounded thing in the sheet -- a group box, a list, a tab pane
-- does not: those are inside a window someone else has already painted, so
their corners were never a problem.

The hook is an application-wide event filter because it is the only one that
sees all three: a combo box's container and a line edit's context menu are
built in C++, so wrapping `QMenu.__init__` -- which does work, and is what
`variants.py` does to QPushButton -- would leave both of those square. Every
event that is not a `Polish` costs one integer comparison.

`CALIBRE_ZEN_ROUND_POPUPS=0` turns it off. It is the only thing the overlay
does to a native window rather than to a painted one, so it gets its own way
back: a compositor that disagrees should cost the corners, not the theme. The
alternative if it ever has to go is not a workaround, it is dropping
`border-radius` from `QMenu`, `QToolTip` and `QComboBox QAbstractItemView` --
a square popup is better than a rounded one with a square behind it.

A note on verifying this: an offscreen grab measures the widget, not the
compositor. It shows the menu case honestly, but a combo box's container holds
a scroll area that paints its own full rect into a grab, so that one comes back
opaque no matter what the window is doing. The check asserts the menu's corners
and only the *attribute* for the container; the container was confirmed on
screen.

### Crash reports, for our code only

calibre phones nobody, and Zen keeps that. What `report/` adds is a way for a
person who has just watched something break to tell us, in one click, with
everything we need and nothing we should not have.

calibre funnels every unhandled GUI exception through
`MainWindow.unhandled_exception`, which prints the traceback and shows an
error dialog with a Copy button. That method is wrapped, and the first thing
the wrap does is ask whose exception it is. A frame under `calibre_zen/` on
the stack means ours -- including upstream code called from inside one of our
wraps, which is exactly where a renamed upstream method surfaces. No frame of
ours means calibre's or a plugin's, and the dialog is left exactly as it was.
Ours gets one more button, **Report to Calibre Zen…**, which opens the one
window every path ends in: a sentence about what happened, the exact JSON that
will leave the machine, and Send or Cancel. What is on screen is the payload
byte for byte -- the install id is stamped before the text is rendered -- and
Copy puts the same text on the clipboard for anyone who would rather attach it
to an issue. Nothing is ever sent from a dialog that did not show it.

| wrapped | why |
| --- | --- |
| `MainWindow.unhandled_exception` | classify; when ours, build the event and let calibre's handler run unchanged |
| `calibre.gui2.main_window.error_dialog` | the name that handler calls, rebound in its module; adds the button when an event is waiting (`consent.py`, `preview.py`) |
| `threading.excepthook` | a worker-thread crash has no dialog; ours crosses to the main thread over a Qt signal and is asked about there |
| `Main.initialize` | once there is a window, offer the modules that failed to install |

**What leaves the machine** is written out in `report/event.py` rather than
left to an SDK's defaults: the exception's type and message, its frames as
file, function and line with three lines of source either side of ours, which
Zen and which calibre, the OS and Qt, and the overlay's own state -- scheme,
appearance, icon pack, font, which modules installed. Not local variables (in
this application those are book titles and library paths), not the user name,
the executable path, the library location or the names of installed plugins.
Paths are normalised to `calibre_zen/...` so two installs group as one issue,
and anything under the home directory is written `~`. A random install id is
minted the first time a report is previewed so Sentry can count users rather than events; it
identifies nothing and deleting it is harmless.

**The transport** is one HTTPS POST of a Sentry envelope over calibre's own
`HTTPSConnection`, verified against the CA directory in the bundle and routed
through the user's proxy, on a daemon thread with an eight-second timeout.
Failure is dropped: a crash reporter that queues and retries is a second bug
surface. The official SDK is not vendored -- it wants `urllib3` and `certifi`,
the bundle has neither, and the protocol is three lines of JSON. The DSN is
public by design; it grants no read access and can be rotated.

**Every module installs, or fails alone.** The eight `install()` calls in the
palette hook used to run bare, so a raise in the third left the rest
uninstalled and the palette change half-done. `report/guard.py` now wraps each
one: a failure is printed, that module is off for the session, and the others
carry on. Stock calibre with a Zen sheet is an acceptable Tuesday. That failure
is also the most useful report the project can receive -- it is the signal,
from the field, on the day upstream ships, that calibre renamed something a
wrap reaches for -- so it is kept as an event and offered once the window is
up, in the same preview window with an "ask again" checkbox -- stored where
calibre keeps its own skippable questions -- as the only "always send" switch
there is. There is no heartbeat and no usage ping.

`CALIBRE_ZEN_REPORT=0` removes the button, the question and the wraps.
`CALIBRE_ZEN_REPORT_DRY=<path>` appends envelopes to a file instead of
sending, which is how the headless test reads them back.

### Fusion

The sheet assumes Fusion. calibre already pins it -- `CalibreStyle` is a
`QProxyStyle` over Fusion -- so the overlay does not set a style: doing that
would replace `CalibreStyle` and take its scrollbar and icon behaviour with it.
`hooks.check_fusion()` only reports, and only when it can see a style that
positively is not Fusion.

When the user has chosen the platform style (`using_calibre_style` is false),
the overlay applies nothing at all.

## Icons

calibre's icons are hand-coloured PNGs, the other half of the dated look and out
of reach of any stylesheet. `icons/` replaces them with monochrome line icons
rendered from SVG in the palette's own colour, so one glyph serves both themes
and follows a custom palette.

Every icon in calibre arrives through `QIcon.ic(name)`, which is
`IconResourceManager.__call__`. Wrapping that one method is the whole
integration, and it is what makes a pack swappable:

- a name the active pack maps is rendered from its SVG;
- a name it does not falls straight through to calibre's own icon.

So a pack is never required to be complete, and a screen can be migrated at a
time. `CALIBRE_ZEN_ICONS=0` restores calibre's icons exactly;
`CALIBRE_ZEN_ICONS=<pack>` selects another; `registry.use(name)` swaps at
runtime, though widgets that took their QIcon once at construction keep the old
pack's glyph until a restart.

**Colour, unlike the pack, is not baked in.** An icon is a `LiveIcon`
(`icons/render.py`), a `QIconEngine` that resolves its palette role when it
paints rather than when it is built, so the copy a QAction took at startup is
still the right colour after the reader switches theme. It used to be a
photograph: measured before the change, a held icon stayed `(31, 35, 40)`
against a `#24262a` window, which is a toolbar you cannot see. An engine also
has to answer `availableSizes()`, because calibre's `QIcon.is_ok()` is
`not isNull() and len(availableSizes()) > 0` (`gui2/__init__.py:309`) and an
SVG-backed QIcon reports none. Rendered pixmaps are still cached, keyed by
colour and size and dropped when the palette moves.

**Adding a pack** is one module in `icons/packs/` exposing a `pack`, plus its
glyphs in `icons/assets/<name>/`. Nothing else is edited -- packs are
discovered, not listed.

**What is left to map** is a question with an answer:

```bash
calibre-debug -e src/calibre_zen/icons/audit.py -- tabler <path to the set's svg dir>
```

It lists every icon calibre ships, says which the pack covers, and proposes
glyphs for the rest by matching calibre's name against the set's names and
keyword tags. The proposals are a shortlist, not a mapping -- string similarity
cheerfully offers `dog` for `donate`, and `car-suv` for `auto-scroll`. Finding
the candidates is the automatable half; choosing between them is not.

A status mark is the exception to monochrome. `dot_green.png` and `dot_red.png`
say "running" and "stopped" with nothing but their colour, so they map to one
filled dot in two roles rather than to two glyphs. `success` is the one role
that does not come from the palette -- the palette has no green, deliberately --
and comes from the tokens instead.

**Adding an icon** to an existing pack is one entry in its `MAP`, then

```bash
calibre-debug -e src/calibre_zen/icons/vendor.py -- tabler <path to the set's svg dir>
```

which copies just that glyph in. Only mapped glyphs are vendored: Tabler ships
5130 of them and a fork carrying all of them to use forty is a fork nobody wants
to clone. The downloaded set lives in `.calibre-zen/icon-sources/`, which is
ignored.

An entry may name a palette role -- `('heart', 'danger')` keeps the donate
button red -- and defaults to `text`.

**Size and weight are tokens, not properties of the glyphs.** `ICON_STROKE`
re-weights every icon as it is rendered, because a set drawn for a 24px box is a
marker pen at 18px and they have to be re-weighted together or the toolbar stops
looking like one set. `TOOLBAR_ICON_SIZE` re-scales calibre's five size
settings: its own scale runs to 48px, which was drawn for detailed colour icons
and makes a line icon a diagram. The sizes are hard-coded in
`BarsManager.apply_settings`, so the overlay sets them after it runs; the user's
setting still chooses, only the scale under it changes.

Arrows are icons too. Qt draws every one as a filled triangle, so `marks/`
carries chevrons and the sheet points the toolbar dropdowns, combo boxes,
submenu arrows, header sort indicators and tree expanders at them. Both branch
states have to be given an image -- Qt keeps drawing its own triangle for any
state a stylesheet leaves out, silently.

## Screenshots without taking the machine

`devtools.py` is off unless `CALIBRE_ZEN_SHOT_DIR` is set. When it is, calibre
watches that directory for a `request` file and renders its own visible windows
with `QWidget.grab()`.

Photographing from outside means raising the window and grabbing a rectangle of
the screen, which takes focus from whoever is working, cannot be driven without
synthetic clicks that land wherever the pointer is, and is not occlusion-proof:
whatever is on top of calibre ends up in the file. Rendering from inside has
none of those problems, and it works on an open menu, since a QMenu is a
top-level widget in its own right.

## Known gaps

- **Format and device marks.** `mimetypes/`, `devices/` and `plugins/` are left
  to calibre: a Kindle is not a line drawing of a Kindle, and an EPUB badge is a
  file-format mark rather than an icon.

  The exception is the generic things that happen to live in those folders -- a
  folder, a tablet, an archive -- which turn up in ordinary menus, where one
  colour PNG among line icons is the only thing you notice. Those are mapped.
  Excluding the folders is a default, not a rule, and `audit.py` lists every
  subfolder icon calibre's code actually references so the next one is found by
  the tool rather than in a screenshot.
- **Component-level work.** The bookshelf paint path and the cover grid draw
  themselves and are untouched by any of this. The tag browser and the book
  list used to be on this list and no longer are -- see "The filter panel" and
  "The centre pane" above. Between them they are the two shapes the rest of it
  can take: a widget of our own reading calibre's model, or calibre's widget
  with our delegate in front of it.
- **Packaging.** `setup/install.py` copies `.py` and `.so` out of `src/`; it
  now copies `.qss`, `.svg` and `.ttf` too, or the overlay would ship without
  its stylesheet or the vendored Inter faces. Nothing else in `src/` has any
  of those extensions.

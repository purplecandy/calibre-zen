# calibre-zen overlay

Our UI work, kept out of calibre's source tree so `git pull` upstream stays
boring.

calibre draws its UI with Qt Widgets through the CalibreStyle proxy over
Fusion. That is correct, dense and thoroughly dated chrome, and none of it is
Qt's fault -- Fusion is styleable and nobody had styled it. This package is
that styling: colours, radii and spacing, and nothing else. No widget is
subclassed and no layout is touched, so the worst a mistake here can do is look
wrong.

Off with `CALIBRE_ZEN_STYLE=0`, which is what makes before/after comparable.

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

## The rule

**Do not edit an upstream widget to change how it looks.** The point of the
overlay is that our diff against upstream is one hook, so a conflict during a
pull is about behaviour, never about styling. In order of preference:

1. Change a token. Most things are a token.
2. Change or add a rule in `theme/qss/app/`.
3. If a widget-local `setStyleSheet()` upstream is punching a hole through the
   app sheet, add an entry to `theme/rewrite.py`.
4. Tag a button's variant with a plain dynamic property -- see "Variant tags"
   below. Still an upstream edit, held to a narrower rule than #5.
5. Only if none of those can work, edit upstream -- and say why in the commit.

### Variant tags: the one upstream edit that isn't rule #5

`theme/variants.py` can only *infer* a button's variant from a signal Qt
already gives (`:default`, an icon name). Where there is no signal --
`check_library.py`'s "Delete marked", say, a plain-text button with no icon --
the only way to mark it is to say so at the point it is built. That is an
upstream edit, but a specific and narrow one, not an opening for rule #5:

- **One line**, added after the button already exists, never changing one
  that is already there.
- **A bare Qt dynamic property**, `widget.setProperty('zenVariant', 'destructive')`
  -- no `import calibre_zen`, anywhere, ever. calibre already supports
  arbitrary dynamic properties; this uses that mechanism the ordinary way, not
  a hook into the overlay. Pull calibre_zen out entirely and the property is
  still set, still inert, still exactly as harmless as it is today.
- **Commented** `# calibre-zen -- see src/calibre_zen/README.md`, so it reads
  as intentional rather than stray, the same courtesy the hook in
  `gui2/__init__.py` gets.
- **Chosen as conservatively as `DANGER_ICON_NAMES`** -- a button that
  destroys something with no easy undo, not any button whose label happens to
  say "Remove."

`grep -rn "zenVariant" src/calibre` finds every one of these, the same way
`grep -rn '\.setFont('` finds every font call site worth checking.

## Layout

```
hooks.py              install(): the single entry point
theme/
  tokens/
    primitives.py     raw values: colour ramps, the radius scale, blend ratios,
                      the font family and its size and weight scales
    semantic.py       what each primitive is for: the palette maps, and Chrome,
                      derived at runtime from the palette actually in use
    components.py     the radii, densities and typography the stylesheet asks
                      for by name
  generate.py         tokens -> QPalette, tokens -> QSS; also loads the
                      vendored fonts into Qt (install_fonts())
  qss/app/*.qss       the application-wide sheet, concatenated in filename order
  qss/local/*.qss     sheets calibre applies to one widget rather than the app
  marks/*.svg         check, indeterminate and radio marks
  fonts/<name>/*.ttf  the vendored faces for each font CALIBRE_ZEN_FONT can
                      select, see "Typography" below
  rewrite.py          wraps setStyleSheet and setFont so a widget's own wins
  variants.py         tags a QPushButton primary/destructive when Qt gives a
                      signal for it, see "Buttons" below
icons/
  registry.py         which pack is active; wraps QIcon.ic
  pack.py             a pack: calibre's icon names -> a directory of SVGs
  packs/*.py          one module per provider, discovered not listed
  assets/<pack>/      the vendored glyphs, and the pack's licence
  vendor.py           copy newly mapped glyphs out of a downloaded icon set
```

### Tokens

Three layers, and a rule: **a `.qss` template may only name a semantic or a
component token.** A value that is in neither belongs in one of them, not in
the rule.

Two of the layers are static, one is not. `PALETTE_DARK` / `PALETTE_LIGHT` are
the theme we ship. `semantic.Chrome` is computed from whatever palette is
installed at the time -- ours, or one of the custom palettes calibre lets users
define in Preferences. Borders, hovers and scrollbars are blends of that
palette rather than fixed greys, which is why a sepia theme gets sepia chrome
instead of stubbornly blue-grey chrome. Write rules against `Chrome`, never
against the maps.

Numbers that appear once and mean nothing anywhere else -- a 6px nudge on a
menu indicator -- stay literals in the QSS, next to the rule they affect.

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

`CALIBRE_ZEN_FONT=<name>` selects a different family for comparison --
`droid-sans` is the other one vendored right now. `primitives.FONTS` is the
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

**Status: parked, working but not pursued further.** Everything below is
verified end to end, including two live-state gotchas Qt gives no warning for
-- `:default` following focus rather than marking intent, and a dynamic
property needing an explicit repolish once a widget has already been shown.
That is what it took to skin calibre's stock `QPushButton` into a variant
language, for a result that only reaches the buttons with a role, a
`setDefault()` call, or a known-dangerous icon -- not the majority of
calibre's ~376 `QPushButton`s, which carry none of those. Composing bespoke
button widgets instead of restyling calibre's own would sidestep all of this
by construction, at the cost of being real widgets rather than a stylesheet.
Worth it later; not started here.

calibre builds every `QPushButton` the same Qt way, with no concept of
"primary" or "destructive" -- there is no `variant` prop to read the way there
would be on a web component. `theme/variants.py` recovers what signal Qt
actually gives, and is honest in the QSS comments and in its own docstring
about where that signal runs out:

- **Primary** looked like it was free -- `QPushButton:default`, already set
  by calibre (~30 explicit `setDefault(True)` calls) or by `QDialogButtonBox`
  for the Accept-role button -- until styling it with a solid fill exposed
  that `:default` is a *live* state, not a fixed marker: it follows keyboard
  focus among every `autoDefault` button in a dialog, so clicking Cancel
  handed the fill to Cancel. Checked empirically, not assumed: nothing in
  Python explains the change, not even inside `QDialogButtonBox` itself,
  which never calls a traceable `setDefault()` on its own Accept-role button
  either. Fixed with a static tag instead: `_tag_button_box_roles()` reads
  `QDialogButtonBox.buttonRole()`, which does not move, and
  `_tag_explicit_default()` covers the ~30 `setDefault(True)` calls outside
  any button box. `02-buttons.qss` keeps `:default` itself, but only for a
  subtle border tint -- a button that transiently picks it up while focused
  still hints "Enter does this" without reading as though it just became the
  dialog's primary action. The solid accent fill is
  `QPushButton[zenVariant="primary"]`, `$accent_hover` / `$accent_pressed`
  blending toward text the same way an ordinary button's hover/pressed
  already do.
- **Destructive** has no Qt signal at all by default -- `DestructiveRole`
  exists on `QDialogButtonBox` but calibre never uses it, checked across the
  whole of `gui2`, zero hits -- so `_tag_button_box_roles()` wires it up
  anyway, for whenever that changes. The only signal calibre actually gives
  today is the icon a delete button already carries. `variants.py` wraps
  `IconResourceManager.__call__` to remember the `QIcon.cacheKey()` for any
  name in `DANGER_ICON_NAMES` (`trash.png` only, on purpose -- `minus.png`
  and friends are used for ordinary list-row removal too often to read as
  "destructive"), then wraps `QPushButton.__init__` *and* `setIcon` to tag a
  button that receives one -- both, because `QPushButton(icon, text)` sets
  the icon from the compiled constructor, which does not call back into a
  Python-level `setIcon` override. Checked empirically, not assumed, the same
  way the `:default` and font gotchas above were. The tag is a plain dynamic
  property (`zenVariant`), read back in QSS as
  `QPushButton[zenVariant="destructive"]`.
- Where even the icon isn't there -- a plain-text "Delete marked" button --
  the tag is set upstream directly, one line, no import: see "Variant tags"
  above. `check_library.py`'s `delete_button` and `spell.py`'s
  `remove_dictionary_button` are the first two.
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

One more gotcha, found the same way as the `:default` one: setting the
`zenVariant` property is not enough on its own. Qt only re-evaluates an
attribute selector like `[zenVariant=...]` the next time a widget is
polished, and a button that already exists and is visible has already been
polished once -- calibre's own Preferences dialog tags its Close button from
`hide_plugin()`, well after the button box was built and shown, so the
property changed but nothing repainted. `variants.set_variant()` is what
every tagging path in the module goes through instead of a bare
`setProperty()`; it calls `style().unpolish()` / `style().polish()` itself so
the fix cannot be forgotten by whichever tagging path is added next.

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
runtime, though widgets that took their QIcon once at construction keep it until
a restart.

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
- **Component-level work.** The tag browser, the item delegates, the bookshelf
  paint path and the cover grid draw themselves and are untouched by any of
  this.
- **Packaging.** `setup/install.py` copies `.py` and `.so` out of `src/`; it
  now copies `.qss`, `.svg` and `.ttf` too, or the overlay would ship without
  its stylesheet or the vendored Inter faces. Nothing else in `src/` has any
  of those extensions.

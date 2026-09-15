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
4. Only if none of those can work, edit upstream -- and say why in the commit.

## Layout

```
hooks.py              install(): the single entry point
theme/
  tokens/
    primitives.py     raw values: colour ramps, the radius scale, blend ratios
    semantic.py       what each primitive is for: the palette maps, and Chrome,
                      derived at runtime from the palette actually in use
    components.py     the radii and densities the stylesheet asks for by name
  generate.py         tokens -> QPalette, tokens -> QSS
  qss/app/*.qss       the application-wide sheet, concatenated in filename order
  qss/local/*.qss     sheets calibre applies to one widget rather than the app
  marks/*.svg         check, indeterminate and radio marks
  rewrite.py          wraps QWidget.setStyleSheet to contain widget-local sheets
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

## Known gaps

- **Icons beyond the main window.** The map covers the toolbar, the tag browser
  categories and the chrome around the book list. Dialogs, the viewer and the
  editor still use calibre's PNGs, which is what falling through is for.
- **Component-level work.** The tag browser, the item delegates, the bookshelf
  paint path and the cover grid draw themselves and are untouched by any of
  this.
- **Packaging.** `setup/install.py` copies `.py` and `.so` out of `src/`; it
  now copies `.qss` and `.svg` too, or the overlay would ship without its
  stylesheet. Nothing else in `src/` has either extension.

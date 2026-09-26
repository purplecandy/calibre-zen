# The design system

calibre-zen gives calibre one calm, consistent look. This guide explains the choices behind it and the pieces that carry them: tokens, surfaces, forms, dialogs and controls. Read it before you add a screen or change how one looks.

The overlay's contract, including which upstream files may change, is in [the overlay README](../../src/calibre_zen/README.md). This guide is the why. The README is the what and the where.

## Principles

1. **One look, from one place.** Every colour, size and radius is a token. A sheet or a widget names a token, never a number of its own.
2. **Wrap, never fork.** calibre keeps its widgets, values, commits and shortcuts. We change how they are drawn and where they sit, from `src/calibre_zen/`.
3. **Borrow good defaults.** Colours and radii follow shadcn/ui's neutral presets. Forms and dialogs follow Apple's Human Interface Guidelines, in the shape of macOS System Settings.
4. **Fewer boxes.** Space groups things before a border does. A page has one level of boxes, and a tab is a page, not a box.
5. **Every part can be switched off.** Each replaced piece has a switch in the features menu and an environment variable, so it can be judged beside stock calibre.

## Where a change goes

Try these in order. Stop at the first one that works.

1. Change a token in `theme/tokens/`.
2. Change or add a rule in `theme/qss/app/`.
3. Name a widget or set a property from Python, and style it from the sheet.
4. Wrap a calibre method from an `install()` that `hooks.py` calls.
5. Only then, a widget of our own. Keep calibre's widget as the thing that holds the value.

## Tokens

Tokens come in four layers. Each layer only reads the one below it.

| Layer | File | Holds |
|---|---|---|
| Primitives | `tokens/primitives.py` | Raw values: colour ramps, font sizes, the radius scales |
| Schemes | `tokens/schemes.py` | One whole look: palette roles, blend ratios, which radius scale |
| Semantic | `tokens/semantic.py` | What a colour is for. `Chrome` derives these from the live palette |
| Components | `tokens/components.py` | Sizes the sheet and the layouts ask for by name |

A QSS template may only name a semantic or component token, as `$name` or `${name}`. `test_theme.py` fails if it names anything else.

`Chrome` is built from whatever palette is installed. So borders, hovers and surfaces follow a palette the reader edits in Preferences, and the same sheet works for every scheme.

## Surfaces

Four surfaces carry everything. Pick by what the thing is, not by how light it should look.

| Token | Use it for |
|---|---|
| `window` | The page behind everything |
| `base` | Where you type: fields, lists, text areas, grouped-form cards |
| `surface` (`menu_bg`) | Things that float: menus, pop-up lists, the calendar |
| `raised` | Bars that sit over a page: a dialog's footer |

`raised` is the base colour in a light palette. In a dark palette it is a step lighter than the window, because the base is darker still and a raised bar in it would read as a hole.

Borders come in three weights, `border_weak`, `border` and `border_strong`. They are blends toward the text colour, so they stay a hairline on any window colour. Use weak for separators inside a group, normal for group edges, strong for fields.

The accent is the one strong colour. It marks the selection, the focused field, the primary button and filled stars. It is never decoration.

## Shape and density

- **Radius by role.** `RADIUS_ROW`, `RADIUS_CONTROL`, `RADIUS_PANEL` and the rest name what the pointer is touching. The scheme decides the numbers.
- **One control height.** Every single-line control is 28px, including date fields, spin boxes and the rating. `CONTROL_MIN_HEIGHT` plus the field padding makes it.
- **Paddings are strings.** `PAD_FIELD`, `PAD_BUTTON`, `PAD_LIST_ITEM` and friends are the density. Change them together.

## Forms

Forms follow Apple's grouped form, as in macOS System Settings. `forms/` builds them. The Edit metadata dialog's Details, Cover & files and Your columns tabs all use it.

### Anatomy

```
Group title
┌───────────────────────────────────────────────────────┐
│ Label            [ text field ..................... ] ⓘ │
│─────────────────────────────────────────────────────────│
│ Label                                   [ date     ▾ ] ⓘ │
│─────────────────────────────────────────────────────────│
│ Label                                   ★★★★☆           │
└───────────────────────────────────────────────────────┘
```

- **Groups** are rounded cards on `base`, with a small muted title above. Rows are split by a `border_weak` hairline.
- **The label** starts the row. It is left-aligned, has no colon, and is never cut short. The label column is as wide as the longest label, up to `FORM_LABEL_MAX`.
- **The control** ends the row. Every control on every row ends on the same line.
- **Slots** hold a field's tools, such as a list editor or a clear button. Every row keeps the same number of slots, filled or not, so icons line up in columns.
- **Text areas** sit under their label and start `TEXTAREA_MIN_HEIGHT` tall.

### How controls are sized

The form never owns a value. It is handed calibre's widgets and only places and sizes them by kind.

| Kind | Width |
|---|---|
| `NUMBER` | `FIELD_WIDTH_NUMBER`, or the widget's own if wider |
| `DATE` | `FIELD_WIDTH_DATE`, or its own |
| `CHOICE` | `FIELD_WIDTH_CHOICE`, or its own |
| `NATURAL` | Its own, such as the stars |
| `STRETCH` | The control column, below |

Free text sits in a **control column** that is the same on every free-text row. By default it takes `FORM_CONTROL_SHARE` of what the row has left after its padding and slots, between `FIELD_WIDTH_TEXT_MIN` and `FIELD_WIDTH_TEXT_MAX`. A form built with `fill=True` gives the column everything after the label column instead, up to `FIELD_WIDTH_TEXT_MAX_FILL`. Use `fill` where the text fields are the point of the page, like a book's title and authors.

The column has a ceiling and a floor, never a fixed width. A fixed width becomes the form's minimum, and the form then scrolls sideways when a vertical scrollbar appears.

### Using it

```python
from calibre_zen import forms

form = forms.Form(parent, slots=1, fill=True)
g = form.group(_('Book'))
g.row(title_label, title_edit, slots=(swap_button,))
g.row(date_label, date_edit, kind=forms.DATE, slots=(clear_button,))
g = form.group(_('Notes'))
g.stacked(_('Review'), review_editor)
form.finish()  # settles the label column
```

- Choose `slots` as the most tools any row needs. An empty slot on every row is wasted space.
- Put a form that can outgrow its page in calibre's `ScrollArea`.
- Put a page's margin, `FORM_MARGIN`, on the page, not on the dialog.

## Dialogs

The Edit metadata dialog set the pattern. Download metadata follows it.

- **Tabs are pages.** The dialog's own tab pane has no frame. The groups on a page are the only boxes.
- **The footer is lifted, like the title bar.** It runs the dialog's full width on `raised`, with a `border_weak` hairline and a very soft shadow cast up over the page. `theme/surfaces.lift()` draws the shadow, since a sheet cannot. Its strength is `FOOTER_SHADOW_*`.
- **The dialog has no margins of its own.** Each page keeps `FORM_MARGIN` inside itself, so the footer can span the width.
- **Buttons.** Secondary actions on the left, then Cancel, then the primary button last on the right. The primary button is the only filled one.
- **Size.** The compact editor opens at 880 by 640 and keeps its own saved geometry, so calibre's near-full-screen size does not carry over.
- **One widget, one place.** If a widget belongs on two tabs, like the cover, move it between them on tab change. Never draw a second copy.

## Controls

Each of these replaces how a calibre widget looks and behaves everywhere it is used, not just in one dialog.

| Control | What changed | Module |
|---|---|---|
| Rating | Five stars you click, a clear cross, arrow keys, no list, the wheel left alone. Book list cells draw the same stars | `rating.py` |
| Date fields | The combo box's chevron, and a calendar in the theme with Today and Clear | `dates.py`, `16-dates.qss` |
| Drop-down lists | Combo box lists and calibre's autocomplete list, dressed like menus | `theme/dropdowns.py` |
| Spin boxes | Two small chevrons, the same height as other fields | `04-fields.qss` |
| Rich text | One border, the toolbar on one line with an overflow button | `theme/richtext.py`, `17-richtext.qss` |

## Qt behaviour to know

These cost us time. Each one is why some code is shaped the way it is.

- **A list shown as its own window under a QComboBox gets none of the app sheet.** calibre's autocomplete list is one. It carries a sheet of its own.
- **Fusion draws a combo box's list with a menu delegate,** which `::item` rules never reach. We swap in a styled delegate when the combo box is polished.
- **A combo box's list window paints a menu panel,** and no app rule can name it. A sheet on the window itself can, but then the app's item-view rules stop reaching the list inside, so that sheet carries the list's look too.
- **A scroll area gives its sheet background to its viewport,** a square that paints over rounded corners, and ignores the sheet's padding. Leave the viewport unfilled, inset it, and paint the rounded surface under it.
- **The app sheet's `min-height` beats `setMinimumHeight()`.** A size that must hold goes in a sheet rule.
- **A rule keyed on an ancestor's property is read at polish.** Set the property, then re-polish the children.
- **Styling a spin box's buttons removes its arrows.** Name the arrows too.
- **QCalendarWidget sizes itself from its rows, not its layout.** Anything added to its layout must be added to its size hint.
- **Fixed widths become minimums.** Prefer a ceiling and a floor.

## Adding a screen

1. Build it from calibre's widgets. Hold values in them, not in yours.
2. Lay out fields with `forms.Form`. Pick `slots` and `fill` on purpose.
3. Name containers with `setObjectName` and style them in a numbered sheet in `theme/qss/app/`.
4. Put every new size in `components.py`, in a block for your screen.
5. Give it a feature switch in `features.py` and install it through `guard.run_install()` in `hooks.py`.
6. Add tests to `src/calibre_zen/tests/`. Check structure and behaviour, not pixels, unless the pixels are the point.
7. Render it offscreen, light and dark, and look at it. The overlay README's "Screenshots without taking the machine" section explains how.

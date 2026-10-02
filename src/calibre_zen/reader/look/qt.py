#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The reader window's Qt side, where the app sheet alone cannot reach.

The reader is a QMainWindow (`EbookViewer`) with up to six dock panels beside
a web page. The overlay's sheet already reaches the controls in them; what it
cannot do is give a panel a header, mark the open chapter in the contents, put
a match in a search result in a stronger weight than the words around it, or
turn a heavy spinner into a quiet one. `qss/app/22-reader.qss` is the look,
scoped to `EbookViewer` so nothing in it can reach the main window; this file
is only what a sheet has no word for.

Four wraps, all from outside:

`MainWindow.__init__`
    Says `zenReader` on an `EbookViewer` as soon as it exists, which is what
    the sheet waits for. Only that class is touched; the base is shared.

`EbookViewer.__init__`
    After calibre has built the window and its docks, each dock gets the
    header below in place of Qt's title, the panels inside them get one set of
    margins, and the three tree panels and the contents get delegates.

`TOCView.set_style_sheet`
    The contents' own sheet goes, since it washes a hovered row in two pieces.

`LoadingOverlay.__init__`
    The spinner and the words under it are swapped for the quiet ones the
    download dialog uses.

Runs once, in a reader process only, after the Application exists. A window
that was built before this ran is left as calibre made it: nothing here is
needed for the reader to work.
"""

import re

from qt.core import (
    QColor,
    QFont,
    QHBoxLayout,
    QIcon,
    QLabel,
    QPainter,
    QPalette,
    QRect,
    QSize,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    Qt,
    QToolButton,
    QWidget,
)

from calibre_zen.theme import rewrite
from calibre_zen.theme.tokens import components, primitives

MARK = 'zen_reader_look'
# What the window says once it is dressed, which is what 22-reader.qss waits for.
PROPERTY = 'zenReader'

# Chrome is two dozen blends and a list paints a screenful at a time: built
# again only when the application palette is replaced by another.
_chrome = None
_chrome_key = None
_RGBA = re.compile(r'^rgba\((\d+), (\d+), (\d+), (\d+)\)$')


def colors():
    "The live Chrome, rebuilt only when the application palette changes."
    global _chrome, _chrome_key
    from calibre.gui2 import qapplication_or_fail

    key = qapplication_or_fail().palette().cacheKey()
    if _chrome is None or key != _chrome_key:
        _chrome, _chrome_key = rewrite.chrome(), key
    return _chrome


def text_color() -> QColor:
    from calibre.gui2 import qapplication_or_fail

    return qapplication_or_fail().palette().color(QPalette.ColorRole.WindowText)


def qcolor(value: str) -> QColor:
    "A `Chrome` colour as a QColor: `#rrggbb`, or the `rgba(r, g, b, 0-255)` a sheet reads."
    m = _RGBA.match(value)
    if m is not None:
        r, g, b, a = (int(x) for x in m.groups())
        return QColor(r, g, b, a)
    return QColor(value)


def semibold(font: QFont) -> QFont:
    font = QFont(font)
    font.setWeight(QFont.Weight(primitives.FONT_WEIGHT['semibold']))
    return font


# The header {{{


class DockTitle(QWidget):
    """
    A panel's header: its title, then float and close.

    Qt's own title is one line of text with two buttons that the app sheet had
    to switch off, since a sheet cannot draw them in the icon pack's glyphs.
    This is the same three things as widgets, so the sheet styles them like
    any other row and the buttons are the pack's glyphs in the palette's ink.
    The title follows the dock's window title, which calibre changes while a
    search runs ("Search :: 5352 matches").
    """

    def __init__(self, dock):
        super().__init__(dock)
        self.dock = dock
        self.setObjectName('zenDockTitle')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFixedHeight(components.READER_TITLE_HEIGHT)
        lay = QHBoxLayout(self)
        pad = components.READER_PANEL_PAD
        lay.setContentsMargins(pad, 0, pad // 2, 0)
        lay.setSpacing(2)
        self.label = la = QLabel(dock.windowTitle(), self)
        la.setObjectName('zenDockTitleLabel')
        # A long title is cut by the panel, never the panel widened by it.
        la.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        lay.addWidget(la, 1)
        self.float_button = self._button('zenDockFloat', 'external-link')
        self.close_button = self._button('zenDockClose', 'x')
        lay.addWidget(self.float_button)
        lay.addWidget(self.close_button)
        dock.windowTitleChanged.connect(la.setText)
        dock.topLevelChanged.connect(self.floating_changed)
        self.floating_changed(dock.isFloating())

    # QDockWidget reads the height to reserve for its header from the widget's
    # sizeHint, which a fixed height does not change: the layout's is the
    # buttons' 28, and the panel would start under the hairline.
    def sizeHint(self):  # noqa: N802  (matching the Qt name is the point)
        return QSize(super().sizeHint().width(), components.READER_TITLE_HEIGHT)

    def minimumSizeHint(self):  # noqa: N802
        return QSize(super().minimumSizeHint().width(), components.READER_TITLE_HEIGHT)

    def _button(self, name, glyph):
        from calibre.utils.localization import _

        b = QToolButton(self)
        b.setObjectName(name)
        b.setAutoRaise(True)
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        side = components.READER_TITLE_BUTTON
        b.setFixedSize(side, side)
        icon = self.glyph(glyph)
        if icon is None:
            b.setText('×' if glyph == 'x' else '⧉')
        else:
            b.setIcon(icon)
            b.setIconSize(QSize(components.READER_TITLE_ICON, components.READER_TITLE_ICON))
        if name == 'zenDockClose':
            b.setToolTip(_('Close'))
            b.clicked.connect(self.dock.close)
        else:
            b.clicked.connect(lambda: self.dock.setFloating(not self.dock.isFloating()))
        return b

    @staticmethod
    def glyph(name: str):
        """
        The pack's glyph, quiet at rest and in the palette's own ink under the
        pointer. A QToolButton asks for its Active mode while it is hovered.
        """
        from calibre_zen.icons import registry, render

        pack = registry.active()
        if pack is None:
            return None
        svg = pack.glyph_svg(name)
        if not svg:
            return None
        chrome = colors()
        ink = QIcon()
        for mode, color in ((QIcon.Mode.Normal, chrome.muted), (QIcon.Mode.Active, qcolor(chrome.accent).name())):
            for size in (16, 24, 32):
                pm = render.render(render.restyle(svg, color, components.ICON_STROKE), size, 1.0)
                ink.addPixmap(pm, mode, QIcon.State.Off)
        return ink

    def floating_changed(self, floating: bool) -> None:
        from calibre.utils.localization import _

        self.float_button.setToolTip(_('Dock this panel') if floating else _('Move this panel into its own window'))


# }}}

# Delegates {{{


def row_height(size: QSize, height: int) -> QSize:
    size.setHeight(max(size.height(), height))
    return size


def is_section(index) -> bool:
    "A chapter's label over its results: the top level of a two-level tree."
    return not index.parent().isValid() and index.model().rowCount(index) > 0


def row_rect(option) -> QRect:
    """
    The whole row, edge to edge of the list's viewport.

    Not the item's own rectangle: a tree starts that after the indent, and Qt
    paints a washed row in two pieces -- the branch column and the item -- with
    a seam where they meet. The sheet leaves a reader's lists unwashed and
    the delegates paint the one rectangle.
    """
    view = option.widget
    width = view.viewport().width() if view is not None else option.rect.right() + 1
    return QRect(0, option.rect.top(), width, option.rect.height())


class Wash:
    """
    Under the pointer and under the chosen row: a soft wash across the row,
    drawn here, with the text left in its own colour.

    A mixin for a QStyledItemDelegate. The state the sheet would wash for is
    taken out of the option before the delegate it sits on draws the content,
    which is what keeps a chosen row's text from flipping to the colour meant
    for a solid fill.
    """

    # Whether a top-level row with rows under it is a chapter's label. In the
    # contents it is a chapter like any other.
    sections = True

    def is_label(self, index) -> bool:
        return self.sections and is_section(index)

    def wash(self, option, index, hover: bool, selected: bool) -> str | None:
        "The `Chrome` colour to wash this row with, or None."
        if self.is_label(index):
            return None  # a label is not a thing to point at
        if selected:
            return colors().pressed
        return colors().hover if hover else None

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        hover = bool(opt.state & QStyle.StateFlag.State_MouseOver)
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        opt.state &= ~(QStyle.StateFlag.State_MouseOver | QStyle.StateFlag.State_Selected)
        self.is_selected = selected
        color = self.wash(option, index, hover, selected)
        if color is not None:
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(color))
            painter.drawRoundedRect(row_rect(option), components.RADIUS_ROW, components.RADIUS_ROW)
            painter.restore()
        self.paint_content(painter, opt, index)

    def paint_content(self, painter, option, index):
        super().paint(painter, option, index)

    def initStyleOption(self, option, index):  # noqa: N802  (matching the Qt name is the point)
        super().initStyleOption(option, index)
        if self.is_label(index):
            section_style(option)

    def sizeHint(self, option, index):  # noqa: N802
        height = components.READER_SECTION_HEIGHT if self.is_label(index) else components.READER_ROW_HEIGHT
        return row_height(super().sizeHint(option, index), height)


class RowDelegate(Wash, QStyledItemDelegate):
    "Highlights and bookmarks, whose rows calibre lets the default delegate paint."


def section_style(option) -> None:
    "The look of a chapter's label: a caption, semibold, quiet."
    font = semibold(_upright(option.font))
    font.setPixelSize(components.FONT_SIZE_CAPTION)
    option.font = font
    ink = qcolor(colors().muted)
    pal = option.palette
    for group in (pal.ColorGroup.Active, pal.ColorGroup.Inactive, pal.ColorGroup.Disabled):
        pal.setColor(group, pal.ColorRole.Text, ink)
        pal.setColor(group, pal.ColorRole.HighlightedText, ink)
    option.palette = pal


def make_toc_delegate(base):
    """
    The contents' delegate, a subclass of calibre's own (which shows a tooltip
    for an elided title) so that is kept.

    calibre marks the chapters you are in with a bold italic font and nothing
    else. The one you are in gets a wash and a dot in the accent colour at its
    end, the chapters it sits inside get the weight alone, and the italic is
    gone because a book's own titles are often italic already.
    """

    class TocDelegate(Wash, base):
        sections = False

        def _state(self, index):
            "(is being viewed, is the one being read): ancestors are the first and not the second."
            model = index.model()
            item = model.itemFromIndex(index) if hasattr(model, 'itemFromIndex') else None
            if item is None or not getattr(item, 'is_being_viewed', False):
                return False, False
            for i in range(item.rowCount()):
                child = item.child(i)
                if child is not None and getattr(child, 'is_being_viewed', False):
                    return True, False
            return True, True

        def wash(self, option, index, hover, selected):
            if self._state(index)[1]:
                return colors().pressed
            return colors().hover if hover else None

        def initStyleOption(self, option, index):  # noqa: N802
            super().initStyleOption(option, index)
            if self._state(index)[0]:
                option.font = semibold(_upright(option.font))

        def paint_content(self, painter, option, index):
            reading = self._state(index)[1]
            row = row_rect(option)
            dot = components.READER_DOT
            if reading:
                # Room for the dot, so a long title is cut before it and not under it.
                option.rect = QRect(option.rect)
                option.rect.setRight(row.right() - dot - 2 * components.READER_ROW_PAD_X)
            super().paint_content(painter, option, index)
            if reading:
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(qcolor(colors().accent))
                box = QRect(0, 0, dot, dot)
                box.moveCenter(QRect(row.right() - components.READER_ROW_PAD_X - dot, row.top(), dot, row.height()).center())
                painter.drawEllipse(box)
                painter.restore()

    return TocDelegate


def _upright(font: QFont) -> QFont:
    font = QFont(font)
    font.setItalic(False)
    return font


def make_results_delegate(base):
    """
    A search result: the words around the match quiet, the match itself in
    semibold and the accent colour. The chapter's name over them is a label.

    calibre draws the context in the text colour and the match in bold; the
    only change is which colour and which weight, so the drawing of the match
    is the one in `calibre.gui2.viewer.widgets`, written out with those two
    swapped. If calibre changes the signature, `draw_match` here raises and
    `paint` there catches it, which leaves a result unpainted rather than the
    panel broken.
    """

    class ResultsDelegate(Wash, base):
        def paint_content(self, painter, option, index):
            if not self.is_label(index):
                # The ink the words are drawn in: quiet around the match.
                ink = text_color() if self.is_selected else qcolor(colors().muted)
                pal = option.palette
                for group in (pal.ColorGroup.Active, pal.ColorGroup.Inactive):
                    pal.setColor(group, pal.ColorRole.Text, ink)
                option.palette = pal
            super().paint_content(painter, option, index)

        def draw_match(
            self,
            painter,
            flags,
            before,
            text,
            after,
            rect,
            before_width,
            match_width,
            after_width,
            ellipsis_width,
            emphasis_font,
            normal_font,
        ):
            from qt.core import QFontMetrics

            context = painter.pen().color()
            match_font = semibold(normal_font)
            extra_width = int(rect.width() - match_width)
            if before_width < after_width:
                left_width = min(extra_width // 2, before_width)
                right_width = extra_width - left_width
            else:
                right_width = min(extra_width // 2, after_width)
                left_width = min(before_width, extra_width - right_width)
            x = rect.left()
            nfm = QFontMetrics(normal_font)
            if before_width and left_width:
                r = rect.adjusted(0, 0, 0, 0)
                r.setRight(x + left_width)
                painter.setFont(normal_font)
                painter.setPen(context)
                ebefore = nfm.elidedText(before, Qt.TextElideMode.ElideLeft, left_width)
                if self.add_ellipsis and ebefore == before:
                    ebefore = '…' + before[1:]
                r.setLeft(x)
                x += painter.drawText(r, flags, ebefore).width()
            painter.setFont(match_font)
            painter.setPen(qcolor(colors().accent))
            r = rect.adjusted(0, 0, 0, 0)
            r.setLeft(x)
            painter.drawText(r, flags, text)
            x += match_width
            if after_width and right_width:
                painter.setFont(normal_font)
                painter.setPen(context)
                r = rect.adjusted(0, 0, 0, 0)
                r.setLeft(x)
                eafter = nfm.elidedText(after, Qt.TextElideMode.ElideRight, right_width)
                if self.add_ellipsis and eafter == after:
                    eafter = after[:-1] + '…'
                painter.drawText(r, flags, eafter)

    return ResultsDelegate


# }}}

# The window {{{


def tidy_layout(layout, left=None, top=None, right=None, bottom=None, spacing=None) -> None:
    "Margins and spacing for a layout calibre made, only where it has one."
    if layout is None:
        return
    pad = components.READER_PANEL_PAD
    layout.setContentsMargins(pad if left is None else left, pad if top is None else top, pad if right is None else right, pad if bottom is None else bottom)
    layout.setSpacing(8 if spacing is None else spacing)


def dress_panels(viewer) -> None:
    "One set of insets: the list runs to the panel's edges, everything else sits 12px in."
    pad = components.READER_PANEL_PAD

    toc = viewer.toc_container
    tidy_layout(toc.layout(), left=0, right=0, top=4, bottom=pad, spacing=8)
    tidy_layout(viewer.toc_search.layout(), top=0, bottom=0, spacing=6)
    from calibre.gui2.viewer.toc import Delegate as TocBase

    viewer.toc.delegate = d = make_toc_delegate(TocBase)(viewer.toc)
    viewer.toc.setItemDelegate(d)
    viewer.toc.setIndentation(18)

    sp = viewer.search_widget
    tidy_layout(sp.layout(), left=0, right=0, top=pad - 2, bottom=pad, spacing=8)
    for panel in (sp, viewer.highlights_widget):
        si = panel.search_input
        tidy_layout(si.layout(), top=0, bottom=0, spacing=8)
        for h in si.layout().children():
            tidy_layout(h, left=0, right=0, top=0, bottom=0, spacing=6)
    from calibre.gui2.viewer.widgets import ResultsDelegate

    sp.results.delegate = d = make_results_delegate(ResultsDelegate)(sp.results)
    sp.results.setItemDelegate(d)

    hp = viewer.highlights_widget
    tidy_layout(hp.layout(), left=0, right=0, top=pad - 2, bottom=pad, spacing=8)
    for child in hp.layout().children():
        tidy_layout(child, top=0, bottom=0, spacing=8)
    hp.highlights.delegate = d = RowDelegate(hp.highlights)
    hp.highlights.setItemDelegate(d)
    hp.highlights.setIndentation(18)

    bp = viewer.bookmarks_widget
    tidy_layout(bp.layout(), top=pad - 2, spacing=8)
    bp.bookmarks_list.delegate = d = RowDelegate(bp.bookmarks_list)
    bp.bookmarks_list.setItemDelegate(d)

    lw = viewer.lookup_widget
    panel = getattr(lw, 'dictionary_panel', None)
    if panel is not None:
        tidy_layout(panel.layout(), top=pad - 2, spacing=8)

    # A list that runs to the panel's edges needs its rows kept off them.
    for view in (viewer.toc, sp.results, hp.highlights, bp.bookmarks_list):
        view.setObjectName('zenReaderList')

    tb = viewer.actions_toolbar
    side = components.READER_TOOLBAR_ICON
    tb.setIconSize(QSize(side, side))


def dress(viewer) -> None:
    "Everything above, once, on a window calibre has finished building."
    if getattr(viewer, MARK, False):
        return
    setattr(viewer, MARK, True)
    for dock in viewer.dock_widgets:
        dock.setTitleBarWidget(DockTitle(dock))
    try:
        dress_panels(viewer)
    except Exception:
        # Cosmetic, and the reader without it is the reader.
        import traceback

        traceback.print_exc()


def wrap_toc(toc) -> bool:
    """
    The contents' own sheet goes: it paints a hover wash on the item and a
    second one on its branch column, which is the seam a row's delegate
    avoids by painting the one rectangle. The reader's list colours are the
    app sheet's and the delegate's.
    """
    cls = toc.TOCView
    orig = cls.set_style_sheet
    if getattr(orig, MARK, False):
        return False

    def set_style_sheet(self):
        self.setStyleSheet('')
        self.setProperty('hovered_item_is_highlighted', True)

    setattr(set_style_sheet, MARK, True)
    set_style_sheet.__wrapped__ = orig
    cls.set_style_sheet = set_style_sheet
    return True


def wrap_window(ui) -> bool:
    cls = ui.EbookViewer
    orig = cls.__init__
    if getattr(orig, MARK, False):
        return False

    def __init__(self, *a, **k):
        orig(self, *a, **k)
        dress(self)

    setattr(__init__, MARK, True)
    cls.__init__ = __init__
    return wrap_base(ui.MainWindow, cls)


def wrap_base(base, cls) -> bool:
    """
    The window says it is dressed as soon as it exists, which is before any of
    its widgets do.

    A sheet rule that waits for a property is read when a widget is polished,
    and a list or a label is polished the moment something gives it a sheet or
    asks its size -- long before `EbookViewer.__init__` returns, and a repolish
    afterwards does not redo the frame and viewport a scroll area worked out
    the first time. So it is set where the base class has finished and the
    subclass has not begun. The base is calibre's `MainWindow`, shared with the
    main window and the editor: only `cls` is touched.
    """
    orig = base.__init__
    if getattr(orig, MARK, False):
        return False

    def __init__(self, *a, **k):
        orig(self, *a, **k)
        if isinstance(self, cls):
            self.setProperty(PROPERTY, True)

    setattr(__init__, MARK, True)
    base.__init__ = __init__
    return True


# }}}

# The loading screen {{{


def wrap_overlay(overlay) -> bool:
    cls = overlay.LoadingOverlay
    orig = cls.__init__
    if getattr(orig, MARK, False):
        return False

    def __init__(self, *a, **k):
        orig(self, *a, **k)
        try:
            quiet_overlay(self)
        except Exception:
            import traceback

            traceback.print_exc()

    setattr(__init__, MARK, True)
    cls.__init__ = __init__
    return True


def quiet_overlay(self) -> None:
    """
    A small spinner on a track, and one line of words under it.

    calibre draws a 96px snake and the message in bold at one and a half
    times the text. Both are swapped for what the download dialog uses.
    """
    from calibre_zen.download.chrome import Spinner

    self.setObjectName('zenLoadingOverlay')
    lay = self.layout()
    old = self.pi
    new = Spinner(components.READER_SPINNER, self)
    lay.replaceWidget(old, new)
    lay.setAlignment(new, Qt.AlignmentFlag.AlignHCenter)
    old.stop()
    old.setParent(None)
    old.deleteLater()
    self.pi = new
    lay.setSpacing(components.READER_SPINNER_GAP)
    la = self.label
    la.setObjectName('zenLoadingLabel')
    font = QFont(la.font())
    font.setBold(False)
    font.setPixelSize(components.FONT_SIZE_BASE)
    la.setFont(font)
    la.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
    # Opaque, on the sheet's own colour: a page half drawn behind a spinner is noise.
    self.setAutoFillBackground(False)
    self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)


# }}}


def install() -> bool:
    import importlib

    # Imported by the reader's own `main`; this only fetches them.
    ui = importlib.import_module('calibre.gui2.viewer.ui')
    overlay = importlib.import_module('calibre.gui2.viewer.overlay')
    toc = importlib.import_module('calibre.gui2.viewer.toc')
    # The contents' sheet first: it is read when the window is built.
    results = [wrap_toc(toc), wrap_window(ui), wrap_overlay(overlay)]
    return any(results)

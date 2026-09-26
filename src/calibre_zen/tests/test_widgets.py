#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Widgets painted offscreen with the app sheet, judged by their pixels.

A rule that renders is not a rule that works: Qt drops what it does not
understand and paints the rest with its own fallbacks, silently. These tests
build the widget, grab it, and check that the fill under a label is the one
the label's colour was chosen for. Each is a screenshot from issue #4 turned
into an assertion.
"""

from collections import Counter

from qt.core import QColor, QCoreApplication, QEvent, QHoverEvent, QIcon, QMenu, QPoint, QPointF, QPushButton, Qt, QTreeWidget, QTreeWidgetItem

from calibre_zen.tests.base import ZenTestCase, app, process_events


def dominant(img, rect) -> str:
    "The most common colour inside `rect`, as #rrggbb."
    c = Counter()
    for y in range(rect.top(), rect.bottom()):
        for x in range(rect.left(), rect.right()):
            c[QColor(img.pixel(x, y)).name()] += 1
    return c.most_common(1)[0][0]


def colours(img, rect) -> set:
    return {QColor(img.pixel(x, y)).name() for y in range(rect.top(), rect.bottom()) for x in range(rect.left(), rect.right())}


def hover(widget, pos) -> None:
    QCoreApplication.sendEvent(widget, QHoverEvent(QEvent.Type.HoverMove, QPointF(pos), QPointF(pos), QPointF(-1, -1)))
    process_events()


def luminance(name: str) -> float:
    c = QColor(name)

    def chan(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * chan(c.red()) + 0.7152 * chan(c.green()) + 0.0722 * chan(c.blue())


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


class TestSelectionFill(ZenTestCase):
    """
    Issue #4: a selected row in a focused list or tree came out on plain base
    with its label already flipped to HighlightedText, and under the pointer
    the hover wash painted over nothing. Once ::item has box properties Qt no
    longer falls back to selection-background-color, so the sheet has to say
    what a selected row looks like.
    """

    def setUp(self):
        from calibre_zen.theme.tokens import semantic

        self.chrome = semantic.Chrome(app().palette(), bool(app().property('is_dark_theme')))
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.resize(300, 160)
        self.items = [QTreeWidgetItem(self.tree, [f'Row {i}']) for i in range(4)]
        self.tree.show()
        self.tree.setCurrentItem(self.items[1])
        process_events()
        self.row = self.tree.visualItemRect(self.items[1])
        self.addCleanup(self.tree.deleteLater)

    def grab(self) -> str:
        return dominant(self.tree.grab().toImage(), self.row)

    def test_focused_selection_is_the_accent(self):
        self.tree.setFocus()
        process_events()
        self.assertEqual(self.grab(), self.chrome.accent)
        self.assertIn(self.chrome.accent_text, colours(self.tree.grab().toImage(), self.row), 'the label is not in HighlightedText')

    def test_hover_does_not_wash_out_a_focused_selection(self):
        self.tree.setFocus()
        hover(self.tree.viewport(), self.row.center())
        self.assertEqual(self.grab(), self.chrome.accent_hover)

    def test_unfocused_selection_is_a_weaker_accent_its_label_still_clears(self):
        self.tree.clearFocus()
        hover(self.tree.viewport(), QPoint(-5, -5))
        fill = self.grab()
        base = app().palette().color(app().palette().ColorRole.Base).name()
        self.assertNotEqual(fill, base, 'unfocused selection is not painted')
        self.assertNotEqual(fill, self.chrome.accent, 'unfocused selection is as loud as a focused one')
        self.assertGreaterEqual(contrast(fill, self.chrome.accent_text), 3.0, f'{self.chrome.accent_text} on {fill}')


class TestGlyphInk(ZenTestCase):
    "A glyph is inked for the fill it is drawn on, or it is not there at all."

    def glyph_colours(self, button) -> set:
        "Every colour in the glyph's corner of the button, minus its fill."
        img = button.grab().toImage()
        area = button.rect().adjusted(8, 4, -button.width() * 2 // 3, -4)
        return colours(img, area) - {dominant(img, area)}

    def primary(self) -> QPushButton:
        b = QPushButton(QIcon.ic('ok.png'), 'Apply')
        b.setDefault(True)
        b.show()
        process_events()
        self.addCleanup(b.deleteLater)
        return b

    def assert_on_accent(self, button, fill: str) -> None:
        seen = self.glyph_colours(button)
        self.assertTrue(seen, 'no glyph painted at all')
        window_text = app().palette().color(app().palette().ColorRole.WindowText).name()
        self.assertNotIn(window_text, seen, f"the glyph is in the window's ink on {fill}")
        self.assertGreaterEqual(max(contrast(c, fill) for c in seen), 3.0, f'nothing in the glyph reads against {fill}')

    def test_primary_button_glyph_is_on_accent(self):
        "Issue #4: the check on a dark theme's Apply was #fafafa on #e5e5e5."
        from calibre_zen.theme.tokens import semantic

        chrome = semantic.Chrome(app().palette(), bool(app().property('is_dark_theme')))
        self.assert_on_accent(self.primary(), chrome.accent)

    def test_primary_button_glyph_stays_on_accent_under_the_pointer(self):
        "Qt asks for Active when hovered; the fill is still the accent, one step deeper."
        from calibre_zen.theme.tokens import semantic

        chrome = semantic.Chrome(app().palette(), bool(app().property('is_dark_theme')))
        b = self.primary()
        hover(b, b.rect().center())
        self.assert_on_accent(b, chrome.accent_hover)

    def test_disabled_primary_button_keeps_the_windows_ink(self):
        "A disabled default button drops its fill, so its glyph must not flip."
        from calibre_zen.theme.tokens import semantic

        chrome = semantic.Chrome(app().palette(), bool(app().property('is_dark_theme')))
        b = self.primary()
        b.setEnabled(False)
        process_events()
        seen = self.glyph_colours(b)
        self.assertTrue(seen, 'no glyph painted at all')
        self.assertNotIn(chrome.accent_text, seen, 'a disabled default button flipped its glyph to on-accent')

    def test_destructive_default_button_keeps_the_danger_ink(self):
        "The danger tint wins over :default in the sheet, so the glyph follows the tint, not the accent."
        from calibre_zen.theme.tokens import semantic

        chrome = semantic.Chrome(app().palette(), bool(app().property('is_dark_theme')))
        b = QPushButton(QIcon.ic('trash.png'), 'Delete')
        b.setProperty('zenVariant', 'destructive')
        b.setDefault(True)
        b.show()
        process_events()
        self.addCleanup(b.deleteLater)
        seen = self.glyph_colours(b)
        self.assertTrue(seen, 'no glyph painted at all')
        self.assertNotIn(chrome.accent_text, seen, 'a destructive default button took the on-accent ink')

    def test_highlighted_menu_item_is_on_accent(self):
        from calibre_zen.theme.tokens import semantic

        chrome = semantic.Chrome(app().palette(), bool(app().property('is_dark_theme')))
        menu = QMenu()
        a = menu.addAction(QIcon.ic('edit_input.png'), 'Embed metadata')
        menu.addAction(QIcon.ic('news.png'), 'Fetch news')
        menu.popup(QPoint(0, 0))
        process_events()
        menu.setActiveAction(a)
        process_events()
        img = menu.grab().toImage()
        rect = menu.actionGeometry(a)
        self.assertEqual(dominant(img, rect), chrome.accent)
        self.assertIn(chrome.accent_text, colours(img, rect))
        menu.hide()
        menu.deleteLater()

    def test_hover_alone_leaves_a_menu_item_dark(self):
        "Qt does not highlight a disabled item; its label stays muted, not flipped."
        from calibre_zen.theme.tokens import semantic

        chrome = semantic.Chrome(app().palette(), bool(app().property('is_dark_theme')))
        menu = QMenu()
        a = menu.addAction('Disabled thing')
        a.setEnabled(False)
        menu.popup(QPoint(0, 0))
        process_events()
        menu.setActiveAction(a)
        process_events()
        img = menu.grab().toImage()
        rect = menu.actionGeometry(a)
        self.assertEqual(dominant(img, rect), chrome.menu_bg, 'a disabled item took the accent fill')
        self.assertIn(chrome.muted, colours(img, rect), 'the disabled label is not in the muted ink')
        menu.hide()
        menu.deleteLater()


def click(widget, pos) -> None:
    from qt.core import QMouseEvent

    for kind, buttons in ((QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton), (QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton)):
        QCoreApplication.sendEvent(widget, QMouseEvent(kind, QPointF(pos), QPointF(pos), Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier))
    process_events()


def key(widget, k) -> None:
    from qt.core import QKeyEvent

    QCoreApplication.sendEvent(widget, QKeyEvent(QEvent.Type.KeyPress, k, Qt.KeyboardModifier.NoModifier))
    process_events()


class TestRating(ZenTestCase):
    """
    calibre's RatingEditor, redrawn as five stars (rating.py). Driven the way
    a person would, through its events, and read back through rating_value --
    the one thing every caller of it relies on.
    """

    def make(self, half=False, value=0):
        from calibre.gui2.widgets2 import RatingEditor

        w = RatingEditor(is_half_star=half)
        w.rating_value = value
        w.resize(w.sizeHint())
        w.show()
        process_events()
        self.addCleanup(w.deleteLater)
        return w

    def test_installed(self):
        from calibre_zen import rating

        self.assertTrue(rating._installed, 'the rating widget was not wrapped')

    def test_click_sets_whole_stars(self):
        from calibre_zen import rating

        w = self.make()
        click(w, rating.star_rect(w, 2).center().toPoint())
        self.assertEqual(w.rating_value, 6)
        self.assertEqual(w.currentIndex(), 3, 'the combo index underneath no longer means what callers expect')
        # The left half of a star is still the whole star when halves are off.
        click(w, rating.star_rect(w, 0).topLeft().toPoint() + QPoint(1, 4))
        self.assertEqual(w.rating_value, 2)

    def test_click_left_half_sets_half_star(self):
        from calibre_zen import rating

        w = self.make(half=True)
        click(w, rating.star_rect(w, 3).topLeft().toPoint() + QPoint(1, 4))
        self.assertEqual(w.rating_value, 7)
        click(w, rating.star_rect(w, 3).topRight().toPoint() + QPoint(-1, 4))
        self.assertEqual(w.rating_value, 8)

    def test_clear_cross_and_keys(self):
        from calibre_zen import rating

        w = self.make(value=6)
        click(w, rating.clear_rect(w).center())
        self.assertEqual(w.rating_value, 0)
        key(w, Qt.Key.Key_Right)
        key(w, Qt.Key.Key_Right)
        self.assertEqual(w.rating_value, 4)
        key(w, Qt.Key.Key_Left)
        self.assertEqual(w.rating_value, 2)
        key(w, Qt.Key.Key_End)
        self.assertEqual(w.rating_value, 10)
        key(w, Qt.Key.Key_Backspace)
        self.assertEqual(w.rating_value, 0)
        key(w, Qt.Key.Key_3)
        self.assertEqual(w.rating_value, 6, "calibre's own digit keys stopped working")

    def test_wheel_does_not_change_it(self):
        from qt.core import QPointingDevice, QWheelEvent

        w = self.make(value=6)
        pos = QPointF(w.width() / 2, w.height() / 2)
        ev = QWheelEvent(
            pos,
            pos,
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
            Qt.MouseEventSource.MouseEventNotSynthesized,
            QPointingDevice.primaryPointingDevice(),
        )
        QCoreApplication.sendEvent(w, ev)
        process_events()
        self.assertEqual(w.rating_value, 6)
        self.assertFalse(ev.isAccepted(), 'the wheel should go on to the scroll area behind')

    def test_no_list_opens(self):
        w = self.make(value=4)
        w.showPopup()
        process_events()
        self.assertFalse(w.view().isVisible())

    def test_cell_value(self):
        from calibre_zen.rating import cell_value

        self.assertEqual([cell_value(v) for v in (None, 0, 7, 8.0, '6', 'x', 42)], [0, 0, 7, 8, 6, 0, 10])


class TestCalendar(ZenTestCase):
    "The calendar calibre's date fields open, dressed and extended in dates.py."

    def make(self):
        from qt.core import QDate, QDateTime, QTime

        from calibre.gui2.widgets2 import DateTimeEdit

        w = DateTimeEdit()
        w.setDisplayFormat('dd MMM yyyy')
        w.setDateTime(QDateTime(QDate(2020, 5, 17), QTime(12, 0)))
        w.show()
        process_events()
        self.addCleanup(w.deleteLater)
        return w

    def test_installed_and_named(self):
        from calibre_zen import dates

        self.assertTrue(dates._installed, 'the calendar was not wrapped')
        self.assertEqual(self.make().calendarWidget().objectName(), 'zenCalendar')

    def test_weekends_are_not_red(self):
        from qt.core import QTextCharFormat

        cw = self.make().calendarWidget()
        colours = {cw.weekdayTextFormat(d).foreground().color().name() for d in Qt.DayOfWeek if isinstance(cw.weekdayTextFormat(d), QTextCharFormat)}
        self.assertEqual(len(colours), 1, f'weekdays and weekends differ: {colours}')
        self.assertNotIn('#ff0000', colours)

    def test_footer_today_and_clear(self):
        from qt.core import QDate, QToolButton

        from calibre.gui2.widgets2 import UNDEFINED_QDATETIME

        w = self.make()
        cw = w.calendarWidget()
        cw.findChild(QToolButton, 'zenCalendarToday').click()
        process_events()
        self.assertEqual(w.date(), QDate.currentDate())
        cw.findChild(QToolButton, 'zenCalendarClear').click()
        process_events()
        self.assertEqual(w.dateTime(), UNDEFINED_QDATETIME)

    def test_popup_is_tall_enough_for_the_footer(self):
        from qt.core import QCalendarWidget, QWidget

        cw = self.make().calendarWidget()
        footer = cw.findChild(QWidget, 'zenCalendarFooter')
        self.assertIsNotNone(footer)
        self.assertEqual(cw.sizeHint().height(), QCalendarWidget.sizeHint(cw).height() + footer.sizeHint().height())

    def test_days_paint(self):
        cw = self.make().calendarWidget()
        cw.resize(cw.sizeHint())
        img = cw.grab().toImage()
        self.assertFalse(img.isNull())


class TestDropdowns(ZenTestCase):
    "A combo box's list and calibre's autocomplete list, dressed like menus (theme/dropdowns.py)."

    def test_combo_list_gets_a_styled_delegate_and_rows(self):
        from qt.core import QComboBox, QWidget

        host = QWidget()
        self.addCleanup(host.deleteLater)
        cb = QComboBox(host)
        cb.addItems(['Read', 'Reading', 'Want to read'])
        host.show()
        process_events()
        self.assertNotEqual(cb.itemDelegate().metaObject().className(), 'QComboMenuDelegate')
        cb.showPopup()
        process_events()
        v = cb.view()
        m = v.model()
        container = v.parentWidget()
        self.assertIn('QComboBoxPrivateContainer', container.styleSheet(), 'the container still paints a menu panel')
        # The rows sit a row's height apart -- not where they were laid out
        # before the sheet gave them their padding.
        self.assertEqual(v.visualRect(m.index(1, 0)).top(), v.sizeHintForRow(0))
        self.assertGreater(v.sizeHintForRow(0), 20)
        cb.hidePopup()

    def test_completer_carries_its_own_sheet_and_fits(self):
        from qt.core import QWidget

        from calibre.gui2.complete2 import EditWithComplete

        host = QWidget()
        self.addCleanup(host.deleteLater)
        e = EditWithComplete(host)
        e.update_items_cache(['Manning', 'Penguin', 'Portfolio', 'Simon and Schuster'])
        host.resize(300, 300)
        host.show()
        process_events()
        e.showPopup()
        process_events()
        c = e.lineEdit().mcompleter
        self.assertTrue(c.isVisible())
        self.assertFalse(c.alternatingRowColors())
        self.assertIn('QListView::item', c.styleSheet())
        self.assertGreater(c.sizeHintForRow(0), 20, 'the list rows are still 16px')
        rows = c.model().rowCount()
        self.assertEqual(c.viewport().height(), rows * c.sizeHintForRow(0), 'the list was not sized to its rows')
        c.hide()


class TestFieldsAndRichText(ZenTestCase):
    "Spin boxes that match the fields beside them, and the rich text editor as one field (theme/richtext.py)."

    def test_spin_boxes_are_as_tall_as_a_line_edit(self):
        from qt.core import QDoubleSpinBox, QFormLayout, QLineEdit, QSpinBox, QWidget

        host = QWidget()
        self.addCleanup(host.deleteLater)
        form = QFormLayout(host)
        le, sb, dsb = QLineEdit('x'), QSpinBox(), QDoubleSpinBox()
        for w in (le, sb, dsb):
            form.addRow('f', w)
        host.show()
        process_events()
        self.assertEqual({le.height(), sb.height(), dsb.height()}, {le.height()})

    def test_rich_text_editor_is_one_field_with_one_toolbar_line(self):
        from qt.core import QGroupBox, QToolBar, QVBoxLayout

        from calibre.gui2.comments_editor import Editor

        box = QGroupBox('My review')
        self.addCleanup(box.deleteLater)
        ed = Editor(box)
        QVBoxLayout(box).addWidget(ed)
        box.resize(700, 400)
        box.show()
        process_events()
        self.assertIsInstance(ed.toolbar, QToolBar, 'the toolbar still wraps onto several rows')
        self.assertLessEqual(ed.toolbar.iconSize().width(), 16)
        self.assertTrue(ed.property('zenRichText'))
        self.assertTrue(box.property('zenRichTextBox'))
        # No border of its own: the text area's edge is the field's fill, not
        # a line. (frameWidth() counts the sheet's padding, so it cannot say.)
        img = ed.editor.grab().toImage()
        edge = {QColor(img.pixel(0, y)).name() for y in range(4, img.height() - 4)}
        self.assertEqual(edge, {ed.editor.viewport().palette().base().color().name()}, f'the text area has a border: {edge}')

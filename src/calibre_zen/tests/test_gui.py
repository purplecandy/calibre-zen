#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
End to end: the real main window, offscreen, on a real library.

This builds `calibre.gui2.ui.Main` the way `GuiRunner.start_gui` does, with the
overlay installed, opens a three-book library and drives it: search, select,
read the preview, read the status bar, quit. It is the closest a headless run
gets to a person using the app, and it is where a change to filters/, centre/
or status/ shows up as behaviour rather than as a look.

One window per class: startup is a few seconds, so the tests share it and
each puts the search box back the way it found it.
"""

import os

from calibre_zen.tests import base
from calibre_zen.tests.base import ZenTestCase, process_events, wait_until


class TestMainWindow(ZenTestCase):
    gui = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from calibre.db.legacy import LibraryDatabase
        from calibre.gui2 import gprefs
        from calibre.gui2.main import option_parser
        from calibre.gui2.ui import Main
        from calibre.utils.config import prefs

        cls.library = base.make_library(os.path.join(cls.tmp, 'library'))
        prefs.set('library_path', cls.library)
        # A first run adds the Quick Start Guide to the library; the tests
        # want exactly the books they made.
        gprefs['quick_start_guide_added'] = True
        gprefs['welcome_wizard_was_run'] = True
        opts, _args = option_parser().parse_args(['calibre-zen-test', '--no-update-check'])
        from calibre.constants import ismacos

        # As run_gui_ does: macOS keeps a native menu bar that the bars
        # manager reads back, so it has to exist before initialize().
        actions = tuple(Main.create_application_menubar() if ismacos else Main.get_menubar_actions())
        db = LibraryDatabase(cls.library)
        cls.gui = Main(opts)
        with gprefs:
            cls.gui.initialize(cls.library, db, actions)
        cls.gui.set_exception_handler()
        # Startup finishes on the event loop: the book list fills, the
        # panels attach, the status bar reads the counts.
        ok = wait_until(lambda: cls.model().count() == len(base.BOOKS), timeout_ms=15000)
        if not ok:
            raise RuntimeError(f'the book list never filled: {cls.model().count()} rows')
        process_events(200)

    @classmethod
    def tearDownClass(cls):
        try:
            if cls.gui is not None:
                cls.gui.shutdown(write_settings=False)
                process_events(200)
        finally:
            super().tearDownClass()

    @classmethod
    def model(cls):
        return cls.gui.library_view.model()

    def tearDown(self):
        self.gui.search.clear()
        wait_until(lambda: self.model().count() == len(base.BOOKS))

    # ------------------------------------------------------------ the shell

    def test_window_shows_the_display_name(self):
        from calibre.constants import __appname__, zen_display_name

        title = self.gui.windowTitle()
        self.assertTrue(title.startswith(zen_display_name), title)
        self.assertFalse(title.startswith(__appname__), title)

    def test_overlay_parts_are_in_place(self):
        from calibre_zen.centre.layout import ZenCentre
        from calibre_zen.filters.panel import FilterPanel
        from calibre_zen.status.bar import ZenStatusBar

        panel = getattr(self.gui.tags_view, 'zen_filter_panel', None)
        self.assertIsInstance(panel, FilterPanel, 'the filter panel did not install')
        self.assertFalse(self.gui.tags_view.isVisibleTo(self.gui), 'the tag browser tree is still visible')
        self.assertIsInstance(getattr(self.gui, 'zen_centre', None), ZenCentre, 'the centre did not install')
        self.assertIsInstance(getattr(self.gui, 'zen_status', None), ZenStatusBar, 'the status bar did not install')

    def test_app_sheet_and_palette_are_applied(self):
        from qt.core import QPalette

        sheet = base.app().styleSheet()
        self.assertGreater(len(sheet), 1000)
        # The overlay's palette, not Fusion's: Window and Base are distinct roles in every scheme.
        pal = base.app().palette()
        self.assertNotEqual(pal.color(QPalette.ColorRole.Window).name(), pal.color(QPalette.ColorRole.Base).name())

    # ------------------------------------------------------------ the books

    def test_library_loaded_every_book(self):
        titles = sorted(self.model().db.title(r) for r in range(self.model().count()))
        self.assertEqual(titles, sorted(b[0] for b in base.BOOKS))

    def test_status_bar_reads_the_count(self):
        counts = self.gui.zen_status.counts
        self.assertTrue(wait_until(lambda: str(len(base.BOOKS)) in counts.text()), counts.text())
        self.assertIn('book', counts.text())

    def test_search_narrows_the_list_and_the_status(self):
        self.gui.search.set_search_string('title:Alpha')
        self.assertTrue(wait_until(lambda: self.model().count() == 1), f'{self.model().count()} rows after search')
        self.assertEqual(self.model().db.title(0), 'Alpha')
        counts = self.gui.zen_status.counts
        self.assertTrue(wait_until(lambda: '1 of 3' in counts.text()), counts.text())

    def test_search_by_tag(self):
        self.gui.search.set_search_string('tags:fiction')
        self.assertTrue(wait_until(lambda: self.model().count() == 2), f'{self.model().count()} rows')

    def test_selecting_a_book_fills_the_preview(self):
        view = self.gui.library_view
        preview = self.gui.zen_centre.preview
        view.set_current_row(0)
        expected = self.model().db.title(0)
        self.assertTrue(wait_until(lambda: preview.title.text() == expected), f'preview shows {preview.title.text()!r}, wanted {expected!r}')
        self.assertTrue(preview.authors.text())
        view.set_current_row(1)
        expected = self.model().db.title(1)
        self.assertTrue(wait_until(lambda: preview.title.text() == expected), f'preview did not follow the selection: {preview.title.text()!r}')

    def test_filter_panel_lists_the_tags(self):
        "The panel reads the same TagsModel as the tree: the library's tags are in it."
        from qt.core import QAbstractItemModel

        panel = self.gui.tags_view.zen_filter_panel
        panel.attach()
        process_events(100)
        model = self.gui.tags_view.model()
        self.assertIsInstance(model, QAbstractItemModel)
        texts = set()

        def walk(parent):
            for r in range(model.rowCount(parent)):
                idx = model.index(r, 0, parent)
                texts.add(idx.data() or '')
                walk(idx)

        from qt.core import QModelIndex

        walk(QModelIndex())
        for tag in ('fiction', 'history'):
            self.assertTrue(any(t.startswith(tag) for t in texts), f'{tag!r} not in the tag model: {sorted(texts)[:20]}')

    # ---------------------------------------------------- the metadata editor

    def editor_dialog(self, rows=None):
        """Open the real editor without entering its blocking exec() loop."""
        from calibre_zen.editor.dialog import MetadataSingleDialogZen

        db = self.gui.current_db
        if rows is None:
            rows = range(self.model().count())
        d = MetadataSingleDialogZen(db, self.gui, editing_multiple=False)

        def cleanup():
            d.done(0)
            d.break_cycles()
            d.deleteLater()
            process_events()

        self.addCleanup(cleanup)
        d.id_list = [db.id(row) for row in rows]
        d.current_row = 0
        d.set_current_callback = None
        d.do_one(apply_changes=False)
        d.show()
        process_events()
        return d

    def test_editor_registration(self):
        from calibre.gui2 import gprefs
        from calibre.gui2.metadata import single
        from calibre_zen.editor.dialog import MetadataSingleDialogZen

        self.assertIs(single.editors['zen'], MetadataSingleDialogZen)
        self.assertEqual(gprefs.defaults['edit_metadata_single_layout'], 'zen')

    def test_editor_tabs_and_default_tab(self):
        d = self.editor_dialog()
        self.assertEqual(d.objectName(), 'zenMetadataEditor')
        self.assertIs(d.zen_tabs, d.central_widget)
        self.assertEqual(d.zen_tabs.count(), 3)
        labels = [' '.join(d.zen_tabs.tabText(i).replace('&', '').split()) for i in range(3)]
        self.assertEqual(labels, ['Details', 'Description', 'Cover files'])
        self.assertEqual(d.zen_tabs.currentIndex(), d.DETAILS)

    def test_editor_every_field_is_on_a_tab(self):
        d = self.editor_dialog()
        fields = (
            'title',
            'authors',
            'series',
            'series_index',
            'tags',
            'rating',
            'publisher',
            'pubdate',
            'languages',
            'identifiers',
            'cover',
            'comments',
            'formats_manager',
            'title_sort',
            'author_sort',
            'timestamp',
        )
        pages = [d.zen_tabs.widget(i) for i in range(d.zen_tabs.count())]
        for name in fields:
            with self.subTest(field=name):
                widget = getattr(d, name)
                self.assertTrue(any(page.isAncestorOf(widget) for page in pages), f'{name} is outside the editor tabs')

    def test_editor_no_stray_widgets_or_clear_buttons(self):
        from qt.core import Qt, QWidget

        d = self.editor_dialog()
        footer = d.findChild(QWidget, 'zenEditorFooter')
        self.assertIsNotNone(footer)
        for widget in d.findChildren(QWidget, '', Qt.FindChildOption.FindDirectChildrenOnly):
            with self.subTest(widget=widget.objectName() or type(widget).__name__):
                if widget.isVisible():
                    self.assertTrue(widget is d.zen_tabs or widget is footer or footer.isAncestorOf(widget))
        for button in (
            d.clear_series_button,
            d.clear_ratings_button,
            d.clear_tags_button,
            d.clear_identifiers_button,
            d.publisher.clear_button,
        ):
            with self.subTest(button=button.toolTip()):
                self.assertFalse(button.isVisible())

    def test_editor_sorts_fold(self):
        d = self.editor_dialog()
        self.assertFalse(d.zen_sorts_body.isVisible())
        self.assertFalse(d.zen_sorts_toggle.isChecked())
        d.zen_sorts_toggle.click()
        process_events()
        self.assertTrue(d.zen_sorts_body.isVisible())

    def test_editor_position_and_navigation(self):
        d = self.editor_dialog()
        titles = [self.gui.current_db.new_api.field_for('title', book_id) for book_id in d.id_list]
        self.assertEqual(d.zen_position.text(), '1 of 3')
        self.assertEqual(d.title.current_val, titles[0])
        d.next_button.click()
        process_events()
        self.assertEqual(d.current_row, 1)
        self.assertEqual(d.title.current_val, titles[1])
        self.assertEqual(d.zen_position.text(), '2 of 3')
        d.prev_button.click()
        process_events()
        self.assertEqual(d.current_row, 0)
        self.assertEqual(d.title.current_val, titles[0])
        self.assertEqual(d.zen_position.text(), '1 of 3')

    def test_editor_cover_files_and_save_button(self):
        from qt.core import QDialogButtonBox

        d = self.editor_dialog(rows=[0])
        self.assertFalse(d.zen_position.isVisible())
        self.assertTrue(d.zen_tabs.widget(d.FILES).isAncestorOf(d.data_files_button))
        self.assertIsNotNone(d.zen_cover_menu_button.menu())
        self.assertIsNotNone(d.zen_formats_label)
        self.assertEqual(d.button_box.button(QDialogButtonBox.StandardButton.Ok).text().replace('&', ''), 'Save')
        hint = d.sizeHint()
        screen_size = d.screen().availableSize()
        self.assertEqual((hint.width(), hint.height()), (min(880, screen_size.width()), min(640, screen_size.height())))

    def test_editor_save_round_trip(self):
        db = self.gui.current_db
        alpha_row = next(row for row in range(self.model().count()) if db.title(row) == 'Alpha')
        d = self.editor_dialog(rows=[alpha_row])
        book_id = d.id_list[0]
        try:
            d.title.current_val = 'Alpha Edited'
            d.accept()
            self.assertEqual(db.new_api.field_for('title', book_id), 'Alpha Edited')
        finally:
            db.new_api.set_field('title', {book_id: 'Alpha'})
            self.model().refresh_ids([book_id])
            process_events()

    def test_editor_preferences_choice(self):
        from qt.core import QComboBox

        from calibre.gui2 import gprefs
        from calibre.gui2.preferences.look_feel_tabs.edit_metadata import EditMetadataTab

        class FakeTab:
            def __init__(self):
                self.opt_edit_metadata_single_layout = QComboBox()
                self.settings = {}

            def register_setting(self, setting):
                self.settings[setting.name] = setting
                return setting

        fake = FakeTab()
        setting = EditMetadataTab.register(fake, 'edit_metadata_single_layout', gprefs, choices=[('Default', 'default')])
        self.assertIs(setting, fake.settings['edit_metadata_single_layout'])
        self.assertIn(('Compact (calibre-zen)', 'zen'), setting.choices)
        self.assertIn(('Default', 'default'), setting.choices)

    def test_no_unhandled_exception_reached_the_dialog(self):
        "Startup and the tests above raised nothing the app had to report."
        from calibre_zen.report import guard

        self.assertEqual(guard.failed(), [], 'overlay parts that failed to install')

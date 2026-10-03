#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The header and footer sheets' Python half, and the book at the top of the
contents: what the page is told, what the page can ask, and that the reader's
own entry points are the ones used. No reader is opened; the viewer is a
stand-in with the attributes these read.
"""

import json
import os
import tempfile
import types

from calibre_zen.tests.base import ZenTestCase


class FakeSignal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)


class FakePage:
    def __init__(self):
        self.ran = []

    def runJavaScript(self, src, world=None, callback=None):  # noqa: N802
        self.ran.append(src)


class FakeWebView:
    def __init__(self):
        self.bridge = types.SimpleNamespace()
        self._page = FakePage()
        self.update_last_read_position = FakeSignal()
        self.update_current_toc_nodes = FakeSignal()
        self.cfi_requests = []
        self.shortcuts = []

    def page(self):
        return self._page

    def get_current_cfi(self, callback):
        self.cfi_requests.append(callback)

    def trigger_shortcut(self, which):
        self.shortcuts.append(which)


class FakeViewer:
    def __init__(self):
        self.web_view = FakeWebView()
        self.current_book_data = {'pos_frac': 0.25}
        self.actions_toolbar = types.SimpleNamespace(
            default_color_schemes={
                'black': {'name': 'Black', 'foreground': '#ffffff', 'background': '#000000'},
                'white': {'name': 'White', 'foreground': '#000000', 'background': '#ffffff'},
                'system': {'name': 'System', 'foreground': '#000000', 'background': '#ffffff'},
                'sepia-light': {'name': 'Sepia light', 'foreground': '#39322B', 'background': '#F6F3E9'},
            }
        )
        self.toc_model = types.SimpleNamespace(zen_current=types.SimpleNamespace(title='Chapter Seven'))
        self.cfis, self.positions = [], []

    def cfi_changed(self, cfi):
        self.cfis.append(cfi)

    def _on_last_read_pos_data(self, cfi, frac):
        self.positions.append((cfi, frac))


def pushed(viewer) -> list:
    "Every state the page was sent, decoded."
    prefix = 'window.zenReader && window.zenReader.receive('
    return [json.loads(src[len(prefix) : -1]) for src in viewer.web_view.page().ran if src.startswith(prefix)]


class TestReaderSheets(ZenTestCase):
    def test_themes_light_to_dark_with_the_system_one_first(self):
        from calibre_zen.reader.look import sheets

        keys = [s['key'] for s in sheets.schemes(FakeViewer())]
        self.assertEqual(keys[:4], ['system', 'white', 'sepia-light', 'black'])

    def test_the_page_can_ask_for_the_state(self):
        from calibre_zen.reader.look import sheets

        v = FakeViewer()
        sheets.attach(v)
        # calibre's bridge looks a message's name up on itself and calls emit.
        getattr(v.web_view.bridge, sheets.INBOX).emit({'want': 'state'})
        state = pushed(v)[-1]
        self.assertEqual(state['pos_frac'], 0.25)
        self.assertEqual(state['chapter'], 'Chapter Seven')
        self.assertIn('labels', state)
        self.assertTrue(state['schemes'])

    def test_moves_are_recorded_by_calibres_own_handlers(self):
        from calibre_zen.reader.look import sheets

        v = FakeViewer()
        sheets.attach(v)
        v.web_view.bridge.zen_message.emit({'want': 'sync'})
        self.assertEqual(len(v.web_view.cfi_requests), 1)
        v.web_view.cfi_requests[0]({'cfi': 'epubcfi(/6/4)', 'progress_frac': 0.5})
        self.assertEqual(v.cfis, ['epubcfi(/6/4)'])
        self.assertEqual(v.positions, [('epubcfi(/6/4)', 0.5)])
        self.assertEqual(v.web_view.current_cfi, 'epubcfi(/6/4)')

    def test_nonsense_from_the_page_is_ignored(self):
        from calibre_zen.reader.look import sheets

        v = FakeViewer()
        sheets.attach(v)
        for junk in (None, 'state', {'want': 'rm -rf'}, 42, {}):
            v.web_view.bridge.zen_message.emit(junk)
        self.assertEqual(pushed(v), [])
        self.assertEqual(v.web_view.cfi_requests, [])

    def test_position_updates_are_pushed(self):
        from calibre_zen.reader.look import sheets

        v = FakeViewer()
        sheets.attach(v)
        for signal in (v.web_view.update_last_read_position, v.web_view.update_current_toc_nodes):
            self.assertEqual(len(signal.slots), 1)
            signal.slots[0]('x', 0.3)
        self.assertEqual(len(pushed(v)), 2)

    def test_the_script_is_added_to_the_profile_once(self):
        from calibre_zen.reader.look import sheets

        inserted = []
        profile = types.SimpleNamespace(scripts=lambda: types.SimpleNamespace(insert=inserted.append))
        module = types.SimpleNamespace(create_profile=lambda: profile)
        self.assertTrue(sheets.wrap_profile(module, lambda: '/* js */'))
        self.assertFalse(sheets.wrap_profile(module, lambda: '/* js */'))
        module.create_profile()
        module.create_profile()
        self.assertEqual(len(inserted), 1)
        self.assertEqual(inserted[0].name(), sheets.SCRIPT_NAME)

    def test_the_sheets_script_uses_calibres_entry_points(self):
        from calibre_zen.reader import look

        js = look.scripts()
        for needle in ("'trigger_shortcut'", "'goto_frac'", "name: 'zen_message'", 'window.zenReader'):
            self.assertIn(needle, js)
        # Every shortcut it fires is one calibre has.
        import re

        with open(os.path.join(os.environ['CALIBRE_DEVELOP_FROM'], 'pyj', 'read_book', 'shortcuts.pyj')) as f:
            known = set(re.findall(r"^    '([a-z_]+)': desc\(", f.read(), re.M))
        used = set(re.findall(r"(?:shortcut|navigate)\('([a-z_]+)'\)", js))
        self.assertTrue(used)
        self.assertEqual(sorted(used - known), [])


class TestBookHeader(ZenTestCase):
    def test_reads_a_prepared_book(self):
        from calibre_zen.reader.look import book_header

        d = tempfile.mkdtemp(dir=self.tmp)
        os.makedirs(os.path.join(d, 'images'))
        with open(os.path.join(d, 'images', 'cover.jpg'), 'wb') as f:
            f.write(b'not really a jpeg')
        with open(os.path.join(d, book_header.METADATA), 'w') as f:
            json.dump({'title': 'A Book', 'authors': ['Ann Author', 'Bob Writer']}, f)
        with open(os.path.join(d, book_header.MANIFEST), 'w') as f:
            json.dump({'raster_cover_name': 'images/cover.jpg'}, f)
        book = book_header.read_book(d)
        self.assertEqual(book['title'], 'A Book')
        self.assertEqual(book['authors'], 'Ann Author & Bob Writer')
        self.assertEqual(book['cover'], os.path.join(d, 'images', 'cover.jpg'))

    def test_missing_pieces_are_empty(self):
        from calibre_zen.reader.look import book_header

        self.assertEqual(book_header.read_book(''), {'title': '', 'authors': '', 'cover': ''})
        self.assertEqual(book_header.read_book(tempfile.mkdtemp(dir=self.tmp)), {'title': '', 'authors': '', 'cover': ''})

    def test_a_long_title_is_two_lines_and_an_ellipsis(self):
        from qt.core import QApplication, QFontMetrics

        from calibre_zen.reader.look import book_header

        fm = QFontMetrics(QApplication.font())
        text = book_header.elide_lines('word ' * 60, fm, 120, 2)
        lines = text.split('\n')
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[-1].endswith('…'))
        for line in lines:
            self.assertLessEqual(fm.horizontalAdvance(line), 120)
        self.assertEqual(book_header.elide_lines('Short', fm, 120, 2), 'Short')

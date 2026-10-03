#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The reader's Qt chrome: its sheet reaches nothing but the reader, the
delegates still match the calibre classes they subclass, the panel header
follows its dock, and the loading screen swaps its spinner.

None of this opens a reader: the pieces are built on their own, with no web
engine, so these run wherever the rest of the suite does.
"""

import inspect
import os
import re

from calibre_zen.tests.base import ZenTestCase

SHEET = '22-reader.qss'


def selectors(text: str) -> list:
    "Every selector in a sheet, comments and `${token}` braces out of the way."
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    text = re.sub(r'\$\{(\w+)\}', r'$\1', text)
    return [s.strip() for m in re.finditer(r'([^{}]+)\{[^{}]*\}', text) for s in m.group(1).split(',')]


class TestReaderQt(ZenTestCase):
    def test_the_sheet_reaches_only_the_reader(self):
        "The app sheet is the main window's too. Every rule here starts at the reader's window or names a reader-only object."
        from calibre_zen.theme import generate

        with open(os.path.join(generate.QSS_DIR, 'app', SHEET)) as f:
            found = selectors(f.read())
        self.assertTrue(found)
        stray = [s for s in found if not (s.startswith('EbookViewer') or re.match(r'#zen(Dock|Loading)', s))]
        self.assertEqual(stray, [])
        # And they wait for the window to say it is dressed, so with the
        # reader look off calibre's own look is left alone.
        ungated = [s for s in found if s.startswith('EbookViewer') and '[zenReader="true"]' not in s]
        self.assertEqual(ungated, [])

    def test_the_sheet_renders_with_no_placeholder_left(self):
        from calibre_zen.theme import generate

        sheet = generate.stylesheet(generate.light_palette(), False)
        self.assertIn('EbookViewer', sheet)
        reader = sheet[sheet.index('The e-book reader') :]
        self.assertIsNone(re.search(r'\$\{?[A-Za-z_]', reader))

    def test_the_results_delegate_draws_a_match_with_calibres_arguments(self):
        "draw_match is written out in qt.py, so a change to its signature upstream has to be noticed here."
        from calibre.gui2.viewer.widgets import ResultsDelegate
        from calibre_zen.reader.look import qt

        ours = qt.make_results_delegate(ResultsDelegate)
        self.assertEqual(list(inspect.signature(ours.draw_match).parameters), list(inspect.signature(ResultsDelegate.draw_match).parameters))
        self.assertTrue(issubclass(ours, ResultsDelegate))

    def test_the_contents_delegate_keeps_calibres_tooltip(self):
        from calibre.gui2.viewer.toc import Delegate
        from calibre_zen.reader.look import qt

        ours = qt.make_toc_delegate(Delegate)
        self.assertTrue(issubclass(ours, Delegate))
        self.assertIs(ours.helpEvent, Delegate.helpEvent)

    def test_the_header_follows_its_dock(self):
        from qt.core import QDockWidget, QMainWindow

        from calibre_zen.reader.look import qt

        win = QMainWindow()
        dock = QDockWidget('Table of Contents', win)
        title = qt.DockTitle(dock)
        dock.setTitleBarWidget(title)
        self.assertEqual(title.label.text(), 'Table of Contents')
        dock.setWindowTitle('Search :: 3 matches')
        self.assertEqual(title.label.text(), 'Search :: 3 matches')
        # QDockWidget reserves what the header's sizeHint says, not what its
        # fixed height says.
        from calibre_zen.theme.tokens import components

        self.assertEqual(title.sizeHint().height(), components.READER_TITLE_HEIGHT)
        win.deleteLater()

    def test_the_loading_screen_gets_the_quiet_spinner(self):
        from calibre.gui2.viewer import overlay
        from calibre_zen.download.chrome import Spinner
        from calibre_zen.reader.look import qt

        orig = overlay.LoadingOverlay.__init__
        try:
            qt.wrap_overlay(overlay)
            lo = overlay.LoadingOverlay()
            self.assertIsInstance(lo.pi, Spinner)
            self.assertEqual(lo.objectName(), 'zenLoadingOverlay')
            self.assertEqual(lo.label.objectName(), 'zenLoadingLabel')
            lo.deleteLater()
        finally:
            if not getattr(orig, qt.MARK, False):
                overlay.LoadingOverlay.__init__ = orig

    def test_one_contents_entry_is_current(self):
        "calibre reports every heading on screen; one of them is the one being read, the first and deepest."
        from calibre.gui2.viewer.toc import TOC
        from calibre_zen.reader.look import qt

        ids = iter(range(100))

        def node(title, *children):
            return {'id': next(ids), 'title': title, 'dest': 'x.html', 'frag': title, 'children': list(children)}

        toc = node('', node('Part', node('One'), node('Two'), node('Three')), node('Four'))
        model = TOC(toc)
        by_title = {i.title: i for i in model.all_items}
        from calibre.gui2.viewer import toc as toc_module

        qt.wrap_toc_model(toc_module)
        model.update_current_toc_nodes([by_title['Two'].node_id, by_title['Three'].node_id, by_title['Four'].node_id])
        self.assertIs(model.zen_current, by_title['Two'])
        self.assertEqual(model.zen_path, frozenset({id(by_title['Part'])}))
        model.update_current_toc_nodes([])
        self.assertIsNone(model.zen_current)

#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The welcome wizard's offer to bring calibre's settings over.

The copy is tested against directories made here, never against the run's
own config directory: the other tests in this process read gprefs, and an
import under them would be a different app by the time they ran.
"""

import json
import os
from unittest import mock

from calibre_zen.tests.base import ZenTestCase


def write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f)


def read_json(path: str):
    with open(path) as f:
        return json.load(f)


class TestImporter(ZenTestCase):
    def make_calibre(self) -> str:
        src = self.mkdtemp()
        write_json(
            os.path.join(src, 'global.py.json'),
            {'library_path': '/books/Calibre Library', 'installation_uuid': 'calibre-own-id', 'output_format': 'azw3'},
        )
        write_json(os.path.join(src, 'gui.json'), {'toolbar_icon_size': 'small', 'edit_metadata_single_layout': 'alt1'})
        write_json(
            os.path.join(src, 'customize.py.json'),
            {'plugins': {'DeDRM': os.path.join(src, 'plugins', 'DeDRM.zip')}},
        )
        os.makedirs(os.path.join(src, 'plugins'))
        with open(os.path.join(src, 'plugins', 'DeDRM.zip'), 'wb') as f:
            f.write(b'not really a zip')
        os.makedirs(os.path.join(src, 'caches', 'thumbnails'))
        with open(os.path.join(src, 'caches', 'thumbnails', 'big.jpg'), 'wb') as f:
            f.write(b'x')
        with open(os.path.join(src, 'gui.lock'), 'wb') as f:
            f.write(b'')
        return src

    def test_find_reports_the_library_and_plugins(self):
        src = self.make_calibre()
        with mock.patch.dict(os.environ, {'CALIBRE_ZEN_IMPORT_FROM': src}):
            from calibre_zen.onboarding import importer

            found = importer.find()
        self.assertIsNotNone(found)
        self.assertEqual(found.path, src)
        self.assertEqual(found.library, '/books/Calibre Library')
        self.assertEqual(found.plugins, ('DeDRM',))

    def test_nothing_to_find_without_settings(self):
        from calibre_zen.onboarding import importer

        with mock.patch.dict(os.environ, {'CALIBRE_ZEN_IMPORT_FROM': self.mkdtemp()}):
            self.assertIsNone(importer.find())
        with mock.patch.dict(os.environ, {'CALIBRE_ZEN_IMPORT_FROM': '0'}):
            self.assertIsNone(importer.find())

    def test_our_own_directory_is_never_a_source(self):
        from calibre.constants import config_dir
        from calibre_zen.onboarding import importer

        marker = os.path.join(config_dir, importer.MARKERS[1])
        if not os.path.exists(marker):
            write_json(marker, {})
            self.addCleanup(os.remove, marker)
        with mock.patch.dict(os.environ, {'CALIBRE_ZEN_IMPORT_FROM': config_dir}):
            self.assertEqual(importer.source(), '')

    def test_copy_merges_repaths_and_skips(self):
        from calibre_zen.onboarding import importer

        src = self.make_calibre()
        dst = self.mkdtemp()
        # What this process wrote before the import: one key calibre also has,
        # one it does not.
        write_json(os.path.join(dst, 'global.py.json'), {'output_format': 'epub', 'language': 'en'})
        write_json(os.path.join(dst, 'gui.json'), {'zen_grid_density': 'compact'})

        importer.copy(src, dst)

        prefs = read_json(os.path.join(dst, 'global.py.json'))
        self.assertEqual(prefs['library_path'], '/books/Calibre Library')
        self.assertEqual(prefs['output_format'], 'azw3', "calibre's value wins")
        self.assertEqual(prefs['language'], 'en', 'a key only we had is kept')
        self.assertNotIn('installation_uuid', prefs)

        gui = read_json(os.path.join(dst, 'gui.json'))
        self.assertEqual(gui, {'zen_grid_density': 'compact', 'toolbar_icon_size': 'small'}, 'the editor layout stays ours')

        plugins = read_json(os.path.join(dst, 'customize.py.json'))['plugins']
        self.assertEqual(plugins['DeDRM'], os.path.join(dst, 'plugins', 'DeDRM.zip'))
        self.assertTrue(os.path.isfile(os.path.join(dst, 'plugins', 'DeDRM.zip')))

        self.assertFalse(os.path.exists(os.path.join(dst, 'caches')))
        self.assertFalse(os.path.exists(os.path.join(dst, 'gui.lock')))
        # The source is only ever read.
        self.assertIn('installation_uuid', read_json(os.path.join(src, 'global.py.json')))

    def test_loaded_settings_are_read_again(self):
        from calibre.utils.config import JSONConfig
        from calibre_zen.onboarding import importer

        base = self.mkdtemp()
        loaded = JSONConfig('probe', base_path=base)
        loaded['kept'] = 1
        write_json(os.path.join(base, 'probe.json'), {'kept': 1, 'imported': 2})
        self.assertIsNone(loaded.get('imported'))
        importer.refresh_loaded(base)
        self.assertEqual(loaded.get('imported'), 2)
        # And a change after it writes the import back, not the stale dict.
        loaded['later'] = 3
        self.assertEqual(read_json(os.path.join(base, 'probe.json')), {'kept': 1, 'imported': 2, 'later': 3})


class TestImportPage(ZenTestCase):
    def wizard(self, src: str):
        from calibre.gui2.wizard import Wizard

        with mock.patch.dict(os.environ, {'CALIBRE_ZEN_IMPORT_FROM': src}):
            w = Wizard(None)
        self.addCleanup(w.deleteLater)
        return w

    def test_no_calibre_means_no_page(self):
        from calibre.gui2.wizard import LibraryPage
        from calibre_zen.onboarding import import_page

        w = self.wizard('0')
        self.assertIsNone(w.page(import_page.ID))
        self.assertEqual(w.startId(), LibraryPage.ID)

    def test_the_wizard_opens_on_the_offer(self):
        from calibre.gui2.wizard import FinishPage, LibraryPage
        from calibre_zen import forms
        from calibre_zen.onboarding import import_page

        src = TestImporter.make_calibre(self)
        w = self.wizard(src)
        self.assertEqual(w.startId(), import_page.ID)
        page = w.page(import_page.ID)
        self.assertEqual(page.library_value.text(), '/books/Calibre Library')
        self.assertEqual(page.plugins_value.text(), 'DeDRM')
        self.assertIsInstance(page.form, forms.Form)

        page.fresh.setChecked(True)
        self.assertEqual(page.nextId(), LibraryPage.ID)
        self.assertTrue(page.validatePage())

        page.bring.setChecked(True)
        self.assertEqual(page.nextId(), FinishPage.ID, 'the library and device came across')
        with mock.patch.object(import_page.importer, 'run') as run:
            self.assertTrue(page.validatePage())
            run.assert_called_once_with(src)
            # Back and Next again does not copy twice.
            self.assertTrue(page.validatePage())
            run.assert_called_once()
        self.assertFalse(page.bring.isEnabled())
        self.assertFalse(page.fresh.isEnabled())
        self.assertTrue(page.status.text())

    def test_a_failed_copy_stays_on_the_page(self):
        from calibre_zen.onboarding import import_page

        w = self.wizard(TestImporter.make_calibre(self))
        page = w.page(import_page.ID)
        page.bring.setChecked(True)
        with mock.patch.object(import_page.importer, 'run', side_effect=OSError('disk full')), mock.patch('calibre.gui2.error_dialog') as dialog:
            self.assertFalse(page.validatePage())
        dialog.assert_called_once()
        self.assertTrue(page.bring.isEnabled())

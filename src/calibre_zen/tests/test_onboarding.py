#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The welcome wizard's offer to bring calibre's settings over, and the library
page's question about a folder that is not empty.

The copy is tested against directories made here, never against the run's
own config directory: the other tests in this process read gprefs, and an
import under them would be a different app by the time they ran.
"""

import json
import os
import re
from unittest import mock

from calibre_zen.tests.base import ZenTestCase


def write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f)


def read_json(path: str):
    with open(path) as f:
        return json.load(f)


def touch(path: str, data: bytes = b'') -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)


class Fixtures:
    def make_calibre(self, library='/books/Calibre Library') -> str:
        "A calibre settings folder, as a used install leaves one."
        src = self.mkdtemp()
        write_json(
            os.path.join(src, 'global.py.json'),
            {'library_path': library, 'installation_uuid': 'calibre-own-id', 'output_format': 'azw3', 'language': 'fr'},
        )
        write_json(
            os.path.join(src, 'gui.json'),
            {
                'action-layout-toolbar': ['Add Books', None, 'View'],
                'toolbar_icon_size': 'small',
                'font': ['Comic Sans', 14],
                'color_palette': 'dark',
                'cover_grid_height': 12.5,
                'edit_metadata_single_layout': 'alt1',
            },
        )
        write_json(os.path.join(src, 'gui.py.json'), {'disable_animations': True, 'new_version_notification': False})
        write_json(os.path.join(src, 'customize.py.json'), {'plugins': {'DeDRM': os.path.join(src, 'plugins', 'DeDRM.zip')}})
        write_json(os.path.join(src, 'tweaks.json'), {'sort_dates_using_visible_fields': True})
        touch(os.path.join(src, 'plugins', 'DeDRM.zip'), b'not really a zip')
        touch(os.path.join(src, 'caches', 'thumbnails', 'big.jpg'), b'x')
        touch(os.path.join(src, 'gui.lock'))
        touch(os.path.join(src, 'icons-dark.rcc'), b'a theme')
        touch(os.path.join(src, 'resources', 'images', 'book.png'), b'an icon')
        touch(os.path.join(src, 'resources', 'templates', 'x.html'), b'a template')
        return src

    def make_library(self) -> str:
        path = self.mkdtemp()
        touch(os.path.join(path, 'metadata.db'))
        return path

    def with_files(self) -> str:
        path = self.mkdtemp()
        touch(os.path.join(path, 'notes.txt'))
        return path

    def settings_holder(self, **config) -> str:
        "A folder like .calibre-zen/: the settings are in config/ inside it."
        outer = self.mkdtemp()
        write_json(os.path.join(outer, 'config', 'gui.json'), {})
        for name, data in config.items():
            write_json(os.path.join(outer, 'config', name.replace('_', '.') + '.json'), data)
        return outer


class TestImporter(Fixtures, ZenTestCase):
    def test_find_reports_the_library_and_plugins(self):
        from calibre_zen.onboarding import importer

        src = self.make_calibre()
        with mock.patch.dict(os.environ, {'CALIBRE_ZEN_IMPORT_FROM': src}):
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
            self.assertFalse(importer.offered())

    def test_a_folder_with_config_inside_is_a_settings_folder(self):
        "Pointing at a folder like .calibre-zen/ finds the settings in its config/."
        from calibre_zen.onboarding import importer

        outer = self.settings_holder()
        self.assertEqual(importer.settings_folder(outer), os.path.join(outer, 'config'))
        self.assertEqual(importer.find(outer).path, os.path.join(outer, 'config'))
        self.assertEqual(importer.settings_folder(self.mkdtemp()), '')

    def test_our_own_directory_is_never_a_source(self):
        from calibre.constants import config_dir
        from calibre_zen.onboarding import importer

        marker = os.path.join(config_dir, importer.MARKERS[1])
        if not os.path.exists(marker):
            write_json(marker, {})
            self.addCleanup(os.remove, marker)
        with mock.patch.dict(os.environ, {'CALIBRE_ZEN_IMPORT_FROM': config_dir}):
            self.assertEqual(importer.source(), '')

    def test_our_own_settings_are_told_apart(self):
        "Under the dev launcher, .calibre-zen/ holds the running app's config/."
        from calibre.constants import config_dir
        from calibre_zen.onboarding import folders, importer

        parent = os.path.dirname(config_dir)
        self.assertTrue(importer.own_settings(config_dir))
        if os.path.basename(config_dir) == 'config':
            self.assertTrue(importer.own_settings(parent))
        self.assertFalse(importer.own_settings(self.make_calibre()))
        self.assertEqual(folders.kind(config_dir), folders.SETTINGS, 'never offered as a library')

    def test_copy_merges_repaths_and_skips(self):
        from calibre_zen.onboarding import importer

        src = self.make_calibre()
        dst = self.mkdtemp()
        # What this process wrote before the import: one key calibre also has,
        # one it does not.
        write_json(os.path.join(dst, 'global.py.json'), {'output_format': 'epub', 'zen_probe': 1})

        importer.copy(src, dst)

        prefs = read_json(os.path.join(dst, 'global.py.json'))
        self.assertEqual(prefs['library_path'], '/books/Calibre Library')
        self.assertEqual(prefs['output_format'], 'azw3', "calibre's value wins")
        self.assertEqual(prefs['zen_probe'], 1, 'a key only we had is kept')
        self.assertEqual(prefs['language'], 'fr', 'the language is a person, not a look')
        self.assertNotIn('installation_uuid', prefs)

        plugins = read_json(os.path.join(dst, 'customize.py.json'))['plugins']
        self.assertEqual(plugins['DeDRM'], os.path.join(dst, 'plugins', 'DeDRM.zip'))
        self.assertTrue(os.path.isfile(os.path.join(dst, 'plugins', 'DeDRM.zip')))
        self.assertTrue(os.path.isfile(os.path.join(dst, 'tweaks.json')))
        self.assertTrue(os.path.isfile(os.path.join(dst, 'resources', 'templates', 'x.html')))

        for skipped in ('caches', 'gui.lock'):
            self.assertFalse(os.path.exists(os.path.join(dst, skipped)), skipped)
        # The source is only ever read.
        self.assertIn('installation_uuid', read_json(os.path.join(src, 'global.py.json')))

    def test_look_and_feel_stays_behind(self):
        from calibre_zen.onboarding import importer

        src = self.make_calibre()
        dst = self.mkdtemp()
        write_json(os.path.join(dst, 'gui.json'), {'toolbar_icon_size': 'medium', 'zen_grid_density': 'compact'})
        importer.copy(src, dst)

        gui = read_json(os.path.join(dst, 'gui.json'))
        self.assertEqual(gui['action-layout-toolbar'], ['Add Books', None, 'View'], 'the toolbar is not look & feel')
        self.assertEqual(gui['toolbar_icon_size'], 'medium', "ours, not calibre's")
        self.assertEqual(gui['zen_grid_density'], 'compact')
        for key in ('font', 'color_palette', 'cover_grid_height', 'edit_metadata_single_layout'):
            self.assertNotIn(key, gui)
        self.assertEqual(read_json(os.path.join(dst, 'gui.py.json')), {'new_version_notification': False})
        self.assertFalse(os.path.exists(os.path.join(dst, 'icons-dark.rcc')), 'an icon theme')
        self.assertFalse(os.path.exists(os.path.join(dst, 'resources', 'images')), 'icon overrides')

    def test_every_look_and_feel_setting_is_left_behind(self):
        """
        The rules against the Look & feel pages' own source: every setting they
        register or read is one the import leaves behind, bar the language.
        A setting upstream adds there fails this until it is sorted.
        """
        from calibre.gui2.preferences import look_feel
        from calibre_zen.onboarding import importer

        tabs = os.path.join(os.path.dirname(look_feel.__file__), 'look_feel_tabs')
        sources = [look_feel.__file__] + [os.path.join(tabs, f) for f in os.listdir(tabs) if f.endswith('.py') and not f.endswith('_ui.py')]
        files = {'gprefs': 'gui.json', 'config': 'gui.py.json'}
        found = set()
        for path in sources:
            with open(path) as f:
                text = f.read()
            for key, store in re.findall(r"r\(\s*'([^']+)'\s*,\s*(gprefs|config)\b", text):
                found.add((files[store], key))
            for store, key in re.findall(r"\b(gprefs|config)(?:\[|\.get\(|\.set\()'([^']+)'", text):
                found.add((files[store], key))
        self.assertGreater(len(found), 60, 'the pages were not read')
        missed = sorted(f'{rel}: {key}' for rel, key in found if not importer.look_and_feel(rel, key))
        self.assertEqual(missed, [], 'Look & feel settings the import would copy')

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

    def test_a_chosen_library_replaces_the_one_the_settings_name(self):
        from calibre.utils.config import prefs
        from calibre_zen.onboarding import importer

        before = prefs['library_path']
        self.addCleanup(prefs.set, 'library_path', before)
        library = self.make_library()
        with (
            mock.patch.object(importer, 'copy', return_value=1),
            mock.patch.object(importer, 'refresh_loaded'),
            mock.patch.object(importer, 'reload_plugins'),
        ):
            importer.run(self.make_calibre(), library=library)
        self.assertEqual(prefs['library_path'], library)


class TestFolders(Fixtures, ZenTestCase):
    def test_what_a_folder_is(self):
        from calibre_zen.onboarding import folders

        with_files = self.with_files()
        self.assertEqual(folders.kind(self.make_library()), folders.LIBRARY)
        self.assertEqual(folders.kind(self.mkdtemp()), folders.EMPTY)
        self.assertEqual(folders.kind(self.settings_holder()), folders.SETTINGS)
        self.assertEqual(folders.kind(with_files), folders.FILES)
        self.assertEqual(folders.kind(os.path.join(with_files, 'gone')), folders.MISSING)

    def library_page(self):
        from calibre.gui2.wizard import LibraryPage

        page = LibraryPage()
        self.addCleanup(page.deleteLater)
        return page

    def test_the_library_page_asks_about_a_folder_with_files(self):
        with_files = self.with_files()
        page = self.library_page()
        with mock.patch('calibre.gui2.question_dialog', return_value=True) as asked:
            self.assertTrue(page.is_library_dir_suitable(with_files))
            self.assertTrue(page.is_library_dir_suitable(with_files), 'Next does not ask again')
        asked.assert_called_once()
        self.assertEqual(os.listdir(with_files), ['notes.txt'], 'nothing is written by asking')

    def test_no_means_no_and_no_second_message(self):
        with_files = self.with_files()
        page = self.library_page()
        with mock.patch('calibre.gui2.question_dialog', return_value=False), mock.patch('calibre.gui2.wizard.error_dialog') as upstream_error:
            self.assertFalse(page.is_library_dir_suitable(with_files))
            page.show_library_dir_error(with_files)
        upstream_error.assert_not_called()

    def test_a_settings_folder_is_not_a_library(self):
        page = self.library_page()
        with mock.patch('calibre.gui2.error_dialog') as told, mock.patch('calibre.gui2.question_dialog') as asked:
            self.assertFalse(page.is_library_dir_suitable(self.settings_holder()))
        told.assert_called_once()
        asked.assert_not_called()

    def test_a_library_is_taken_without_a_question(self):
        page = self.library_page()
        with mock.patch('calibre.gui2.question_dialog') as asked:
            self.assertTrue(page.is_library_dir_suitable(self.make_library()))
        asked.assert_not_called()


class TestImportPage(Fixtures, ZenTestCase):
    def wizard(self, src: str, rerun: bool = False):
        from calibre.gui2.wizard import Wizard
        from calibre.utils.config import dynamic

        real_get = dynamic.get

        def get(key, default=None):
            return rerun if key == 'welcome_wizard_was_run' else real_get(key, default)

        with mock.patch.dict(os.environ, {'CALIBRE_ZEN_IMPORT_FROM': src}), mock.patch.object(dynamic, 'get', get):
            w = Wizard(None)
        self.addCleanup(w.deleteLater)
        return w

    def page(self, w):
        from calibre_zen.onboarding import import_page

        return w.page(import_page.ID)

    def test_no_calibre_on_a_first_run_means_no_page(self):
        from calibre.gui2.wizard import LibraryPage

        w = self.wizard(self.mkdtemp())
        self.assertIsNone(self.page(w))
        self.assertEqual(w.startId(), LibraryPage.ID)
        self.assertIsNone(self.page(self.wizard('0', rerun=True)), 'switched off')

    def test_a_rerun_offers_to_choose_even_without_calibre(self):
        from calibre_zen.onboarding import import_page

        page = self.page(self.wizard(self.mkdtemp(), rerun=True))
        self.assertIsNotNone(page)
        self.assertEqual(page.mode(), import_page.FRESH, 'keeping what is here comes first')
        self.assertFalse(page.buttons[import_page.BRING].isVisibleTo(page), 'nothing was found to bring')
        self.assertTrue(page.buttons[import_page.CHOOSE].isVisibleTo(page))

    def test_the_wizard_opens_on_the_offer(self):
        from calibre.gui2.wizard import FinishPage, LibraryPage
        from calibre_zen import forms
        from calibre_zen.onboarding import import_page

        src = self.make_calibre()
        w = self.wizard(src)
        self.assertEqual(w.startId(), import_page.ID)
        page = self.page(w)
        self.assertIsInstance(page.form, forms.Form)
        self.assertEqual(page.mode(), import_page.BRING)
        self.assertEqual(page.settings_value.text(), src)
        self.assertEqual(page.library_value.text(), '/books/Calibre Library')
        self.assertEqual(page.plugins_value.text(), 'DeDRM')

        page.buttons[import_page.FRESH].setChecked(True)
        self.assertEqual(page.nextId(), LibraryPage.ID)
        self.assertTrue(page.validatePage())

        page.buttons[import_page.BRING].setChecked(True)
        self.assertEqual(page.nextId(), FinishPage.ID, 'the library and device came across')
        with mock.patch.object(import_page.importer, 'run') as run:
            self.assertTrue(page.validatePage())
            run.assert_called_once_with(src, library='')
            # Back and Next again does not copy twice.
            self.assertTrue(page.validatePage())
            run.assert_called_once()
        self.assertFalse(page.buttons[import_page.BRING].isEnabled())
        self.assertFalse(page.pick_library.isEnabled())
        self.assertTrue(page.status.text())

    def test_choosing_the_settings_and_library(self):
        "The folder buttons: a .calibre-zen-like folder for settings, and a library."
        from calibre.gui2.wizard import FinishPage
        from calibre_zen.onboarding import import_page

        page = self.page(self.wizard(self.make_calibre()))
        library = self.make_library()
        outer = self.settings_holder(global_py={'library_path': library}, customize_py={'plugins': {'Quality Check': 'x.zip'}})
        config = os.path.join(outer, 'config')
        with mock.patch('calibre.gui2.choose_dir', return_value=outer):
            page.pick_settings.click()
        self.assertEqual(page.mode(), import_page.CHOOSE, 'a folder button chooses this option')
        self.assertEqual(page.settings_value.text(), config)
        self.assertEqual(page.library_value.text(), library, 'the library the settings name')
        self.assertEqual(page.plugins_value.text(), 'Quality Check')
        self.assertTrue(page.isComplete())

        other = self.make_library()
        with mock.patch('calibre.gui2.choose_dir', return_value=other):
            page.pick_library.click()
        self.assertEqual(page.library_value.text(), other)
        self.assertEqual(page.nextId(), FinishPage.ID)
        with mock.patch.object(import_page.importer, 'run') as run:
            self.assertTrue(page.validatePage())
        run.assert_called_once_with(config, library=other)

    def test_a_folder_with_files_can_be_the_library_when_agreed(self):
        from calibre_zen.onboarding import import_page

        page = self.page(self.wizard(self.make_calibre()))
        with_files = self.with_files()
        with mock.patch('calibre.gui2.choose_dir', return_value=with_files), mock.patch('calibre.gui2.question_dialog', return_value=False):
            page.pick_library.click()
        self.assertNotEqual(page.library_value.text(), with_files, 'said no')
        with mock.patch('calibre.gui2.choose_dir', return_value=with_files), mock.patch('calibre.gui2.question_dialog', return_value=True):
            page.pick_library.click()
        self.assertEqual(page.library_value.text(), with_files)
        self.assertEqual(page.mode(), import_page.CHOOSE)

    def test_picking_our_own_settings_says_so(self):
        from calibre.constants import config_dir
        from calibre_zen.onboarding import import_page

        page = self.page(self.wizard(self.make_calibre()))
        with mock.patch('calibre.gui2.choose_dir', return_value=config_dir):
            page.pick_settings.click()
        self.assertFalse(page.isComplete())
        self.assertIn('using now', page.problem.text())
        self.assertEqual(page.mode(), import_page.CHOOSE)

    def test_a_folder_without_settings_holds_next(self):
        from calibre_zen.onboarding import import_page

        page = self.page(self.wizard(self.make_calibre()))
        with mock.patch('calibre.gui2.choose_dir', return_value=self.mkdtemp()):
            page.pick_settings.click()
        self.assertFalse(page.isComplete())
        self.assertFalse(page.problem.isHidden())
        page.buttons[import_page.FRESH].setChecked(True)
        self.assertTrue(page.isComplete(), 'starting fresh needs no folder')

    def test_a_failed_copy_stays_on_the_page(self):
        from calibre_zen.onboarding import import_page

        page = self.page(self.wizard(self.make_calibre()))
        with mock.patch.object(import_page.importer, 'run', side_effect=OSError('disk full')), mock.patch('calibre.gui2.error_dialog') as dialog:
            self.assertFalse(page.validatePage())
        dialog.assert_called_once()
        self.assertTrue(page.buttons[import_page.BRING].isEnabled())

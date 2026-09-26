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

    def test_advanced_brings_only_what_is_picked(self):
        from calibre_zen.onboarding import importer

        src = self.make_calibre()
        touch(os.path.join(src, 'conversion', 'epub_output.py'), b'x')
        touch(os.path.join(src, 'shortcuts', 'main.json'), b'{}')
        touch(os.path.join(src, 'plugins', 'Other.zip'), b'z')
        write_json(
            os.path.join(src, 'customize.py.json'),
            {'plugins': {'DeDRM': os.path.join(src, 'plugins', 'DeDRM.zip'), 'Other': os.path.join(src, 'plugins', 'Other.zip')}, 'disabled_plugins': []},
        )
        dst = self.mkdtemp()
        importer.copy(src, dst, groups=frozenset({'conversion', 'toolbar'}), plugins=frozenset({'DeDRM.zip'}))

        self.assertTrue(os.path.isfile(os.path.join(dst, 'conversion', 'epub_output.py')))
        self.assertFalse(os.path.exists(os.path.join(dst, 'shortcuts')))
        self.assertFalse(os.path.exists(os.path.join(dst, 'global.py.json')), 'General was not picked')
        self.assertEqual(read_json(os.path.join(dst, 'gui.json')), {'action-layout-toolbar': ['Add Books', None, 'View']})
        self.assertEqual(sorted(os.listdir(os.path.join(dst, 'plugins'))), ['DeDRM.zip'])
        customize = read_json(os.path.join(dst, 'customize.py.json'))
        self.assertEqual(customize, {'plugins': {'DeDRM': os.path.join(dst, 'plugins', 'DeDRM.zip')}}, 'registered only with its file')

    def test_plugin_entries_are_the_folder_as_it_is(self):
        from calibre_zen.onboarding import importer

        src = self.make_calibre()
        touch(os.path.join(src, 'plugins', 'DeDRM', 'kindlekey.k4i'))
        touch(os.path.join(src, 'plugins', 'dedrm.json'), b'{}')
        self.assertEqual(importer.plugin_entries(src), ['DeDRM', 'dedrm.json', 'DeDRM.zip'])

    def test_a_toolbar_that_came_across_gets_our_additions(self):
        from calibre.gui2 import gprefs
        from calibre_zen import hooks

        self.assertEqual(hooks.with_toolbar_additions(('Add Books', 'View')), ('Add Books', 'View', None, 'Preferences'))
        self.assertEqual(hooks.with_toolbar_additions(('Preferences', 'View')), ('Preferences', 'View'), 'nothing moves')
        key = hooks.TOOLBAR_KEYS[0]
        before = gprefs.get(key) if key in gprefs else None
        self.addCleanup(lambda: gprefs.set(key, before) if before is not None else gprefs.__delitem__(key))
        gprefs[key] = ['Add Books', None, 'View']
        self.assertIn(key, hooks.merge_toolbar_additions())
        self.assertEqual(list(gprefs[key]), ['Add Books', None, 'View', None, 'Preferences'])

    def test_backup_copies_beside_and_leaves_caches(self):
        from calibre_zen.onboarding import importer

        config = os.path.join(self.mkdtemp(), 'calibre-zen')
        write_json(os.path.join(config, 'gui.json'), {'a': 1})
        touch(os.path.join(config, 'caches', 'big.jpg'), b'x')
        touch(os.path.join(config, 'gui.lock'))
        path = importer.backup(config)
        self.assertTrue(os.path.basename(path).startswith('calibre-zen-backup-'))
        self.assertEqual(read_json(os.path.join(path, 'gui.json')), {'a': 1})
        self.assertFalse(os.path.exists(os.path.join(path, 'caches')))
        self.assertFalse(os.path.exists(os.path.join(path, 'gui.lock')))
        self.assertNotEqual(importer.backup(config), path, 'a second backup does not overwrite the first')

    def test_reset_clears_all_but_the_caches(self):
        from calibre_zen.onboarding import importer

        config = self.mkdtemp()
        write_json(os.path.join(config, 'gui.json'), {'a': 1})
        touch(os.path.join(config, 'plugins', 'DeDRM.zip'))
        touch(os.path.join(config, 'caches', 'big.jpg'))
        with mock.patch.object(importer, '_settle') as settle:
            importer.reset(config)
        settle.assert_called_once_with(config)
        self.assertEqual(os.listdir(config), ['caches'])


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


class TestSetupPage(Fixtures, ZenTestCase):
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

    def pages(self, w):
        from calibre_zen.onboarding import advanced_page, import_page

        return w.page(import_page.ID), w.page(advanced_page.ID)

    def next_text(self, page) -> str:
        from qt.core import QWizard

        # As it reads on screen: a lone & marks the shortcut, && is an ampersand.
        return page.buttonText(QWizard.WizardButton.NextButton).replace('&&', '\0').replace('&', '').replace('\0', '&')

    def test_the_setup_page_always_comes_first(self):
        "It is where the library is picked now, so calibre's library page is out of the flow."
        from calibre.gui2.wizard import LibraryPage
        from calibre_zen.onboarding import import_page

        w = self.wizard(self.mkdtemp())
        page, _advanced = self.pages(w)
        self.assertEqual(w.startId(), import_page.ID)
        self.assertEqual(page.mode(), import_page.FRESH, 'nothing found to bring')
        self.assertFalse(page.buttons[import_page.BRING].isVisibleTo(page))
        self.assertNotIn(page.nextId(), (LibraryPage.ID,))
        off = self.wizard('0')
        self.assertIsNone(self.pages(off)[0], 'switched off')
        self.assertEqual(off.startId(), LibraryPage.ID)

    def test_bring_over(self):
        from calibre.gui2.wizard import FinishPage
        from calibre_zen import forms
        from calibre_zen.onboarding import import_page

        src = self.make_calibre()
        page, _advanced = self.pages(self.wizard(src))
        self.assertIsInstance(page.form, forms.Form)
        self.assertEqual(page.mode(), import_page.BRING)
        self.assertEqual(page.bring_settings.text(), src)
        self.assertEqual(page.bring_library.text(), '/books/Calibre Library')
        self.assertEqual(page.bring_plugins.text(), 'DeDRM')
        self.assertEqual(self.next_text(page), 'Apply & Continue', 'Next does the work, so it says so')
        self.assertTrue(page.backup_card.isHidden(), 'a first run has nothing to back up')
        self.assertEqual(page.nextId(), FinishPage.ID, 'the library and device came across')
        with mock.patch.object(import_page.importer, 'run') as run, mock.patch.object(import_page.importer, 'backup') as backup:
            self.assertTrue(page.validatePage())
            self.assertTrue(page.validatePage(), 'Back and Next again')
        run.assert_called_once_with(src)
        backup.assert_not_called()
        self.assertFalse(page.buttons[import_page.FRESH].isEnabled())
        self.assertEqual(self.next_text(page), 'Next >')
        self.assertTrue(page.status.text())

    def test_bring_over_on_a_rerun_backs_up_first(self):
        from calibre_zen.onboarding import import_page

        page, _advanced = self.pages(self.wizard(self.make_calibre(), rerun=True))
        self.assertEqual(page.mode(), import_page.FRESH, 'a re-run starts on keeping what is here')
        page.buttons[import_page.BRING].setChecked(True)
        self.assertFalse(page.backup_card.isHidden())
        self.assertTrue(page.backup.isChecked(), 'on by default')
        with mock.patch.object(import_page.importer, 'run'), mock.patch.object(import_page.importer, 'backup', return_value='/b') as backup:
            self.assertTrue(page.validatePage())
        backup.assert_called_once()
        self.assertIn('/b', page.status.text())

    def test_a_first_fresh_start_sets_the_library_and_picks_a_device(self):
        from calibre.gui2.wizard import DevicePage
        from calibre_zen.onboarding import import_page

        page, _advanced = self.pages(self.wizard(self.mkdtemp()))
        library = self.make_library()
        with mock.patch('calibre.gui2.choose_dir', return_value=library):
            page.pick_library.click()
        self.assertEqual(page.fresh_library.text(), library)
        self.assertEqual(self.next_text(page), 'Apply & Continue')
        self.assertEqual(page.nextId(), DevicePage.ID)
        with mock.patch.object(import_page.importer, 'use_library') as use, mock.patch.object(import_page.importer, 'reset') as reset:
            self.assertTrue(page.validatePage())
        use.assert_called_once_with(library)
        reset.assert_not_called()

    def test_a_rerun_keeps_what_is_here_unless_reset_is_picked(self):
        from calibre.gui2.wizard import DevicePage, FinishPage
        from calibre_zen.onboarding import import_page

        page, _advanced = self.pages(self.wizard(self.mkdtemp(), rerun=True))
        self.assertFalse(page.settings_row.isHidden())
        self.assertEqual(page.settings_action(), import_page.KEEP)
        self.assertEqual(self.next_text(page), 'Next >', 'keeping and the same library changes nothing')
        self.assertEqual(page.nextId(), FinishPage.ID)
        self.assertTrue(page.backup_card.isHidden())
        with mock.patch.object(import_page.importer, 'reset') as reset, mock.patch.object(import_page.importer, 'use_library') as use:
            self.assertTrue(page.validatePage())
        reset.assert_not_called()
        use.assert_not_called()

        page, _advanced = self.pages(self.wizard(self.mkdtemp(), rerun=True))
        page.settings_choice.setCurrentIndex(page.settings_choice.findData(import_page.RESET))
        self.assertEqual(self.next_text(page), 'Apply & Continue')
        self.assertFalse(page.backup_card.isHidden())
        self.assertEqual(page.nextId(), DevicePage.ID)
        page.backup.setChecked(False)
        with (
            mock.patch.object(import_page.importer, 'reset') as reset,
            mock.patch.object(import_page.importer, 'use_library'),
            mock.patch.object(import_page.importer, 'backup') as backup,
        ):
            self.assertTrue(page.validatePage())
        reset.assert_called_once()
        backup.assert_not_called()

    def test_advanced_goes_on_to_its_page(self):
        from calibre_zen.onboarding import advanced_page, import_page

        page, _advanced = self.pages(self.wizard(self.make_calibre()))
        page.buttons[import_page.ADVANCED].setChecked(True)
        self.assertEqual(page.nextId(), advanced_page.ID)
        self.assertEqual(self.next_text(page), 'Next >', 'nothing happens until the next page')
        with mock.patch.object(import_page.importer, 'run') as run:
            self.assertTrue(page.validatePage())
        run.assert_not_called()

    def test_a_failed_apply_stays_on_the_page(self):
        from calibre_zen.onboarding import import_page

        page, _advanced = self.pages(self.wizard(self.make_calibre()))
        with mock.patch.object(import_page.importer, 'run', side_effect=OSError('disk full')), mock.patch('calibre.gui2.error_dialog') as dialog:
            self.assertFalse(page.validatePage())
        dialog.assert_called_once()
        self.assertTrue(page.buttons[import_page.BRING].isEnabled())
        self.assertEqual(self.next_text(page), 'Apply & Continue')

    def test_the_language_button_drives_calibres_box(self):
        w = self.wizard(self.make_calibre())
        button = w.zen_language_button
        box = w.library_page.language
        self.assertEqual(button.text(), box.currentText())
        button.build_menu()
        self.assertEqual([a.text() for a in button.menu_.actions()], [box.itemText(i) for i in range(box.count())])
        if box.count() > 1:
            # Blocked, so the process does not really switch language under
            # the other tests; the box is what changes.
            box.blockSignals(True)
            self.addCleanup(box.blockSignals, False)
            self.addCleanup(box.setCurrentIndex, box.currentIndex())
            button.choose(1)
            self.assertEqual(box.currentIndex(), 1)
            self.assertEqual(button.text(), box.itemText(1))


class TestAdvancedPage(Fixtures, ZenTestCase):
    wizard = TestSetupPage.wizard
    pages = TestSetupPage.pages
    next_text = TestSetupPage.next_text

    def test_it_starts_from_what_was_found(self):
        page = self.pages(self.wizard(self.make_calibre()))[1]
        self.assertEqual(page.library_value.text(), '/books/Calibre Library')
        self.assertEqual(set(page.group_checks), {g.key for g in page_groups()})
        self.assertTrue(all(b.isChecked() for b in page.group_checks.values()))
        self.assertEqual(list(page.plugin_checks), ['DeDRM.zip'])
        self.assertEqual(self.next_text(page), 'Apply & Continue')
        self.assertTrue(page.backup.isHidden())

    def test_choosing_folders_and_what_comes(self):
        from calibre.gui2.wizard import FinishPage
        from calibre_zen.onboarding import advanced_page

        page = self.pages(self.wizard(self.make_calibre()))[1]
        library = self.make_library()
        outer = self.settings_holder(global_py={'library_path': library})
        touch(os.path.join(outer, 'config', 'plugins', 'Quality Check.zip'))
        config = os.path.join(outer, 'config')
        with mock.patch('calibre.gui2.choose_dir', return_value=outer):
            page.pick_settings.click()
        self.assertEqual(page.settings_value.text(), config)
        self.assertEqual(page.library_value.text(), library, 'the library those settings name')
        self.assertEqual(list(page.plugin_checks), ['Quality Check.zip'], "the new folder's plugins")
        page.group_checks['windows'].setChecked(False)
        page.plugin_checks['Quality Check.zip'].setChecked(False)
        self.assertTrue(page.isComplete())
        self.assertEqual(page.nextId(), FinishPage.ID)
        with mock.patch.object(advanced_page.importer, 'run') as run:
            self.assertTrue(page.validatePage())
        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertEqual(args, (config,))
        self.assertEqual(kwargs['library'], library)
        self.assertNotIn('windows', kwargs['groups'])
        self.assertIn('general', kwargs['groups'])
        self.assertEqual(kwargs['plugins'], frozenset())

    def test_switches_survive_a_new_settings_folder(self):
        page = self.pages(self.wizard(self.make_calibre()))[1]
        page.group_checks['sharing'].setChecked(False)
        with mock.patch('calibre.gui2.choose_dir', return_value=self.settings_holder()):
            page.pick_settings.click()
        self.assertFalse(page.group_checks['sharing'].isChecked())

    def test_bad_folders_hold_apply(self):
        from calibre.constants import config_dir

        page = self.pages(self.wizard(self.make_calibre()))[1]
        with mock.patch('calibre.gui2.choose_dir', return_value=self.mkdtemp()):
            page.pick_settings.click()
        self.assertFalse(page.isComplete())
        self.assertFalse(page.problem.isHidden())
        with mock.patch('calibre.gui2.choose_dir', return_value=config_dir):
            page.pick_settings.click()
        self.assertIn('using now', page.problem.text())

    def test_a_folder_with_files_is_the_library_only_when_agreed(self):
        page = self.pages(self.wizard(self.make_calibre()))[1]
        with_files = self.with_files()
        with mock.patch('calibre.gui2.choose_dir', return_value=with_files), mock.patch('calibre.gui2.question_dialog', return_value=False):
            page.pick_library.click()
        self.assertNotEqual(page.library_value.text(), with_files)
        with mock.patch('calibre.gui2.choose_dir', return_value=with_files), mock.patch('calibre.gui2.question_dialog', return_value=True):
            page.pick_library.click()
        self.assertEqual(page.library_value.text(), with_files)

    def test_a_rerun_backs_up_first(self):
        from calibre_zen.onboarding import advanced_page

        page = self.pages(self.wizard(self.make_calibre(), rerun=True))[1]
        self.assertFalse(page.backup.isHidden())
        with mock.patch.object(advanced_page.importer, 'run'), mock.patch.object(advanced_page.importer, 'backup', return_value='/b') as backup:
            self.assertTrue(page.validatePage())
        backup.assert_called_once()
        self.assertIn('/b', page.status.text())


def page_groups():
    from calibre_zen.onboarding import importer

    return importer.GROUPS

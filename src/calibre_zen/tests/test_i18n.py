#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The fork's own translations, added to calibre's as a fallback.

Whether a language is *complete* is deliberately not tested: a new string
should not fail the suite for want of a Hebrew line. What is tested is that
what is there is sound -- every file compiles, keeps the placeholders of the
string it translates, still translates a string that exists -- and that it is
added behind calibre's catalog, not in front of it, and survives a language
change.
"""

import ast
import os
import re
import unittest
from unittest import mock

from calibre_zen import i18n

PLACEHOLDER = re.compile(r'%(?:\([a-z]+\))?[sd]|\{[a-z0-9]*\}')

# msgfmt keeps a plural entry as one key and one value, each its forms joined by NUL.
NUL = chr(0)


def parse(path: str) -> dict[str, str]:
    "msgid -> msgstr of a .po, as calibre's own compiler reads it."
    from calibre.translations import msgfmt

    if i18n.compile_po(path) is None:
        raise AssertionError(f'{path} does not compile')
    return {k.decode('utf-8'): v.decode('utf-8') for k, v in msgfmt.MESSAGES.items() if k}


def forms(msgid: str, msgstr: str) -> list[tuple[str, str]]:
    """
    The (source, translation) pairs one entry holds. The singular form of a
    plural entry may drop the number ("one book"); the plural has to keep it.
    """
    if NUL not in msgid:
        return [(msgid, msgstr)]
    singular, plural = msgid.split(NUL)
    first, *rest = msgstr.split(NUL)
    return [(singular, first), *[(plural, r) for r in rest]]


def msgids_in_source() -> set[str]:
    "Every literal handed to `_()`, `__()` or `ngettext()` in the package, tests excepted."
    found = set()
    root = os.path.dirname(i18n.__file__)
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ('tests', '__pycache__')]
        for name in files:
            if not name.endswith('.py'):
                continue
            with open(os.path.join(folder, name), encoding='utf-8') as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and node.args):
                    continue
                if isinstance(node.func, ast.Attribute) and node.func.attr == 'override':  # i18n.override()
                    wanted = node.args[:1]
                elif not isinstance(node.func, ast.Name):
                    continue
                elif node.func.id in ('_', '__'):
                    wanted = node.args[:1]
                elif node.func.id == 'ngettext':
                    wanted = node.args[:2]
                else:
                    continue
                parts = [a.value for a in wanted if isinstance(a, ast.Constant) and isinstance(a.value, str)]
                if len(parts) == len(wanted):
                    found.add(NUL.join(parts))
    return found


class Catalogs(unittest.TestCase):
    def catalogs(self):
        names = [n for n in os.listdir(i18n.LOCALES) if n.endswith('.po')]
        self.assertTrue(names, 'no catalogs under locales/')
        return [os.path.join(i18n.LOCALES, n) for n in names]

    def test_every_entry_is_translated_and_keeps_its_placeholders(self):
        for path in self.catalogs():
            for entry, translated in parse(path).items():
                for msgid, msgstr in forms(entry, translated):
                    with self.subTest(file=os.path.basename(path), msgid=msgid):
                        self.assertNotEqual(msgstr, msgid, 'empty or copied translation')
                        have = sorted(PLACEHOLDER.findall(msgstr))
                        want = sorted(PLACEHOLDER.findall(msgid))
                        if NUL in entry and msgid == entry.split(NUL)[0]:
                            self.assertTrue(set(have) <= set(want), 'a placeholder the source does not have')
                        else:
                            self.assertEqual(want, have)

    def test_no_entry_outlives_its_string(self):
        live = msgids_in_source()
        for path in self.catalogs():
            for entry in parse(path):
                with self.subTest(file=os.path.basename(path), msgid=entry.replace(NUL, ' | ')):
                    self.assertIn(entry, live, 'no _() or ngettext() in calibre_zen has this string any more')

    def test_catalog_lookup(self):
        self.assertTrue(i18n.catalog_for('he').endswith('he.po'))
        self.assertTrue(i18n.catalog_for('he_IL').endswith('he.po'))
        self.assertIsNone(i18n.catalog_for('en'))
        self.assertIsNone(i18n.catalog_for(None))


class Fallback(unittest.TestCase):
    def setUp(self):
        from calibre.utils import localization

        self.localization = localization
        self.assertTrue(i18n.install())

    def tearDown(self):
        self.localization.set_translators()  # back to the language the process started in

    def switch_to(self, lang: str):
        with mock.patch.dict(os.environ, {'CALIBRE_OVERRIDE_LANG': lang}):
            self.localization.set_translators()

    def test_ours_answer_where_calibre_has_nothing(self):
        self.switch_to('he')
        _ = self.localization._
        self.assertEqual(_('Reset all filters'), 'אפס את כל המסננים')

    def test_plurals_follow_the_number(self):
        self.switch_to('he')
        ngettext = self.localization.ngettext
        self.assertEqual(ngettext('{} job', '{} jobs', 1), 'משימה אחת')
        self.assertEqual(ngettext('{} job', '{} jobs', 3).format(3), '3 משימות')

    def test_calibres_own_translation_is_not_overridden(self):
        self.switch_to('he')
        _ = self.localization._
        # calibre has 'Cover' in its Hebrew catalog; ours must never answer for it.
        self.assertEqual(_('Cover'), 'כריכה')
        self.assertNotIn('Cover', parse(os.path.join(i18n.LOCALES, 'he.po')))

    def test_a_language_with_no_catalog_is_left_alone(self):
        self.switch_to('de')
        self.assertEqual(self.localization._('Reset all filters'), 'Reset all filters')

    def test_a_language_switch_gets_them_again(self):
        self.switch_to('de')
        self.switch_to('he')
        self.assertEqual(self.localization._('Reset all filters'), 'אפס את כל המסננים')

    def test_override_answers_for_a_string_calibre_has_too(self):
        self.switch_to('he')
        self.assertEqual(i18n.override('Save to disk'), 'שמירה לדיסק')
        self.assertEqual(self.localization._('Save to disk'), 'שמור לדיסק הקשיח', "calibre's own is untouched")

    def test_override_leaves_a_language_with_no_catalog_to_calibre(self):
        self.switch_to('de')
        self.assertEqual(i18n.override('Save to disk'), self.localization._('Save to disk'))

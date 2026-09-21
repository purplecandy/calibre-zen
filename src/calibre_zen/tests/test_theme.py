#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The theme renders: every scheme, both polarities, both darknesses, with no
placeholder left for Qt to drop silently and no unbalanced brace.
"""

import glob
import os
import re

from calibre_zen.tests.base import ZenTestCase

PLACEHOLDER = re.compile(r'\$\{?[A-Za-z_]')


def check_sheet(tc, sheet: str, label: str) -> None:
    left = [ln.strip() for ln in sheet.splitlines() if PLACEHOLDER.search(ln)]
    tc.assertEqual(left, [], f'{label}: unsubstituted tokens')
    tc.assertEqual(sheet.count('{'), sheet.count('}'), f'{label}: unbalanced braces')
    tc.assertGreater(len(sheet), 1000, f'{label}: sheet is suspiciously short')


class TestTheme(ZenTestCase):
    def setUp(self):
        from calibre_zen.theme.tokens import schemes

        self._scheme = schemes.active().name
        self._dark = schemes.darkness()

    def tearDown(self):
        from calibre_zen.theme.tokens import schemes

        schemes.set_active(self._scheme)
        schemes.set_darkness(self._dark)

    def test_every_scheme_renders(self):
        from calibre_zen.theme import generate
        from calibre_zen.theme.tokens import schemes

        for name in schemes.SCHEMES:
            schemes.set_active(name)
            for darkness in schemes.DARKNESS:
                schemes.set_darkness(darkness)
                for is_dark in (True, False):
                    label = f'{name}/{darkness}/{"dark" if is_dark else "light"}'
                    with self.subTest(label):
                        pal = generate.dark_palette() if is_dark else generate.light_palette()
                        check_sheet(self, generate.stylesheet(pal, is_dark), label)

    def test_local_sheets_render(self):
        from calibre_zen.theme import generate

        pal = generate.dark_palette()
        here = os.path.dirname(generate.__file__)
        names = [os.path.basename(p)[:-4] for p in glob.glob(os.path.join(here, 'qss', 'local', '*.qss'))]
        self.assertTrue(names)
        for name in names:
            with self.subTest(name):
                sheet = generate.local_stylesheet(name, pal, True)
                self.assertEqual([ln for ln in sheet.splitlines() if PLACEHOLDER.search(ln)], [])

    def test_templates_only_name_known_tokens(self):
        "A template may only name a semantic or component token."
        from calibre_zen.theme import generate

        known = set(generate.mapping(generate.dark_palette(), True))
        here = os.path.dirname(generate.__file__)
        for path in sorted(glob.glob(os.path.join(here, 'qss', '*', '*.qss'))):
            with open(path) as f:
                text = f.read()
            names = set(re.findall(r'\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?', text))
            with self.subTest(os.path.relpath(path, here)):
                self.assertEqual(sorted(names - known), [])

    def test_dark_and_light_palettes_differ(self):
        from qt.core import QPalette

        from calibre_zen.theme import generate

        d = generate.dark_palette().color(QPalette.ColorRole.Window)
        l = generate.light_palette().color(QPalette.ColorRole.Window)  # noqa: E741
        self.assertLess(d.lightness(), l.lightness())

    def test_overlay_is_installed_in_the_application(self):
        from calibre_zen import hooks

        self.assertTrue(hooks.install(), 'install() reports the overlay off')
        self.assertTrue(hooks.install(), 'a second install() is not idempotent')
        from calibre_zen.tests.base import app

        self.assertGreater(len(app().styleSheet()), 1000, 'the app sheet is not applied')

    def test_marks_render_to_files(self):
        from calibre_zen.theme import generate

        here = os.path.dirname(generate.__file__)
        names = [os.path.basename(p)[:-4] for p in glob.glob(os.path.join(here, 'marks', '*.svg'))]
        self.assertTrue(names)
        for name in names:
            with self.subTest(name):
                path = generate.mark_path(name, '#ff0000')
                self.assertTrue(path and os.path.exists(path), f'no rendered mark for {name}')

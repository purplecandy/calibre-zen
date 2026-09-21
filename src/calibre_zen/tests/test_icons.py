#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The icon packs: every mapped glyph is vendored, every vendored glyph is an SVG
Qt can render, and the registry answers through QIcon.ic.
"""

import os

from calibre_zen.tests.base import ZenTestCase


class TestIcons(ZenTestCase):
    def test_a_pack_is_active(self):
        from calibre_zen.icons import registry

        self.assertIn('tabler', registry.available())
        pack = registry.active()
        self.assertIsNotNone(pack, 'no active pack: is CALIBRE_ZEN_ICONS set?')

    def test_no_mapped_glyph_is_missing(self):
        from calibre_zen.icons import registry

        for name, pack in registry.available().items():
            with self.subTest(pack=name):
                self.assertEqual(pack.missing(), (), f'{name}: mapped glyphs not vendored')
                licences = [f for f in os.listdir(pack.directory) if f.upper().startswith('LICEN')]
                self.assertTrue(licences, f'{name}: no licence beside the glyphs')

    def test_every_vendored_glyph_renders(self):
        from qt.core import QByteArray, QSvgRenderer

        from calibre_zen.icons import registry

        for name, pack in registry.available().items():
            bad = []
            for f in sorted(os.listdir(pack.directory)):
                if not f.endswith('.svg'):
                    continue
                with open(os.path.join(pack.directory, f), 'rb') as fh:
                    if not QSvgRenderer(QByteArray(fh.read())).isValid():
                        bad.append(f)
            with self.subTest(pack=name):
                self.assertEqual(bad, [])

    def test_registry_serves_calibre_names(self):
        from qt.core import QIcon

        from calibre_zen.icons import registry

        pack = registry.active()
        for name in list(pack.mapping)[:20]:
            with self.subTest(name):
                icon = QIcon.ic(name)
                self.assertFalse(icon.isNull(), f'{name} rendered null')
                self.assertFalse(icon.pixmap(24, 24).isNull())
        # An unmapped name still falls through to calibre's own icon.
        self.assertFalse(QIcon.ic('mimetypes/epub.png').isNull())

    def test_the_map_is_not_shrinking(self):
        "179 top-level icons are mapped on purpose (README); a rewrite that drops half of them fails here."
        from calibre_zen.icons import registry

        self.assertGreaterEqual(len(registry.active().mapping), 170)

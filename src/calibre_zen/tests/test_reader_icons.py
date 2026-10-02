#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The reader's icon sprite, redrawn as line glyphs: every symbol keeps its id,
every glyph the map names is vendored, a mapped symbol comes out as a stroke
drawn in the text colour, an unmapped one is left byte for byte, and a page
that is not a page is handed back as it came.

The page is a small stand-in with a sprite in the shape imgsrc/srv/generate.py
makes. The real `viewer.html` is a build product and is not in the tree.
"""

import os
import re

from calibre_zen.tests.base import ZenTestCase

SYMBOL = re.compile(rb'<symbol\b[^>]*>.*?</symbol>', re.S)
ID = re.compile(rb'\bid="(icon-[^"]+)"')

SOLID = b'<path d="M1792 896q0 26-19 45l-256 256z"/>'


def sprite(*names: str) -> bytes:
    symbols = ''.join(f'\n  <symbol viewBox="0 0 1792 1792" id="icon-{n}">{SOLID.decode()}</symbol>' for n in names)
    return f'<svg style="display:none">{symbols}\n</svg>'.encode()


def page(*names: str) -> bytes:
    return b'<!DOCTYPE html><html><head><title>x</title></head><body>' + sprite(*names) + b'<p>text</p></body></html>'


def symbols_of(html: bytes) -> dict:
    return {ID.search(m.group()).group(1): m.group() for m in SYMBOL.finditer(html)}


class TestReaderIcons(ZenTestCase):
    def test_every_mapped_glyph_is_vendored(self):
        from calibre_zen.reader.look import icons

        missing = sorted({g for g in icons.MAP.values() if not os.path.exists(os.path.join(icons.GLYPH_DIR, f'{g}.svg'))})
        self.assertEqual(missing, [], 'mapped to a Tabler glyph that is not in icons/assets/tabler')
        for glyph in set(icons.MAP.values()):
            self.assertTrue(icons.glyph_body(glyph), f'{glyph}: no drawing in the file')

    def test_the_pack_requires_every_mapped_glyph(self):
        # So that the pack's own missing() notices if one is ever removed.
        from calibre_zen.icons.packs.tabler import pack
        from calibre_zen.reader.look.icons import MAP

        self.assertEqual(sorted(set(MAP.values()) - set(pack.required_glyphs())), [])

    def test_the_map_names_only_what_the_sprite_has(self):
        "A mapped name that is not a file in imgsrc/srv is a typo, and silently does nothing."
        from calibre_zen.reader.look import icons

        here = os.path.dirname(os.path.abspath(__file__))
        srv = os.path.normpath(os.path.join(here, '..', '..', '..', 'imgsrc', 'srv'))
        if not os.path.isdir(srv):
            self.skipTest('imgsrc/srv is not in this tree')
        have = {f[:-4] for f in os.listdir(srv) if f.endswith('.svg')}
        self.assertEqual(sorted(set(icons.MAP) - have), [])
        self.assertEqual(sorted(set(icons.UNMAPPED) - have), [])
        # Every glyph is either mapped or deliberately left: nothing is missed.
        self.assertEqual(sorted(have - set(icons.MAP) - set(icons.UNMAPPED)), [])

    def test_ids_are_kept(self):
        from calibre_zen.reader.look import icons

        names = ('close', 'cog', 'search', 'selection-handle', 'no-such-icon')
        before, after = page(*names), icons.rewrite(page(*names))
        self.assertEqual(sorted(symbols_of(before)), sorted(symbols_of(after)))
        self.assertEqual(after.count(b'<symbol'), len(names))
        # Everything outside the sprite is untouched.
        self.assertTrue(after.startswith(b'<!DOCTYPE html><html><head><title>x</title></head><body><svg style="display:none">'))
        self.assertTrue(after.endswith(b'<p>text</p></body></html>'))

    def test_a_mapped_symbol_is_a_line_in_the_text_colour(self):
        from calibre_zen.reader.look import icons

        out = symbols_of(icons.rewrite(page('close', 'cog')))
        for key in (b'icon-close', b'icon-cog'):
            sym = out[key]
            self.assertIn(b'stroke="currentColor"', sym)
            self.assertIn(b'fill="none"', sym)
            self.assertIn(b'viewBox="0 0 24 24"', sym)
            self.assertIn(b'stroke-linecap="round"', sym)
            self.assertIn(b'stroke-linejoin="round"', sym)
            self.assertNotIn(SOLID, sym)
            self.assertNotIn(b'1792', sym)
        # The weight is the main window's own.
        from calibre_zen.theme.tokens import components

        self.assertIn(f'stroke-width="{components.ICON_STROKE}"'.encode(), out[b'icon-close'])

    def test_the_glyph_is_the_one_the_map_names(self):
        from calibre_zen.reader.look import icons

        out = symbols_of(icons.rewrite(page('close')))[b'icon-close']
        self.assertIn(icons.glyph_body(icons.MAP['close']).encode(), out)

    def test_an_unmapped_symbol_is_byte_identical(self):
        from calibre_zen.reader.look import icons

        before = symbols_of(page('selection-handle', 'selection-handle-vertical', 'no-such-icon'))
        after = symbols_of(icons.rewrite(page('selection-handle', 'selection-handle-vertical', 'no-such-icon', 'close')))
        for key, sym in before.items():
            self.assertEqual(after[key], sym)

    def test_it_is_stable_and_cheap_to_repeat(self):
        from calibre_zen.reader.look import icons

        once = icons.rewrite(page('close', 'cog', 'search'))
        # A second pass finds the symbols already drawn as lines and draws the same ones.
        self.assertEqual(icons.rewrite(once), once)

    def test_unusable_input_comes_back_unchanged(self):
        from calibre_zen.reader.look import icons

        for raw in (
            b'',
            b'<html><head></head><body>no sprite here</body></html>',
            b'<svg><symbol id="icon-close" viewBox="0 0 1 1"><path d="M0 0"/>',  # never closed
            b'<symbol id="icon-close"',  # cut off
            b'<symbol>no id</symbol>',
            b'\xff\xfe\x00 not text, no sprite \x80\xff',
        ):
            self.assertEqual(icons.rewrite(raw), raw)
        self.assertEqual(icons.rewrite(None), None)  # type: ignore[arg-type]
        self.assertEqual(icons.rewrite('text'), 'text')  # type: ignore[arg-type]

    def test_a_glyph_that_is_missing_leaves_the_symbol_as_it_was(self):
        from calibre_zen.reader.look import icons

        saved = icons.MAP['close']
        icons.MAP['close'] = 'no-such-glyph-anywhere'
        try:
            raw = page('close')
            self.assertEqual(icons.rewrite(raw), raw)
        finally:
            icons.MAP['close'] = saved

    def test_a_failure_returns_the_page(self):
        from calibre_zen.reader.look import icons

        saved = icons.stroke_width
        icons.stroke_width = lambda: 1 / 0
        try:
            raw = page('close')
            self.assertEqual(icons.rewrite(raw), raw)
        finally:
            icons.stroke_width = saved

    def test_off_means_off(self):
        from calibre_zen.reader.look import icons

        saved = icons.wanted
        icons.wanted = lambda: False
        try:
            raw = page('close')
            self.assertEqual(icons.rewrite(raw), raw)
        finally:
            icons.wanted = saved

#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The reader's web look: its stylesheet renders for every scheme and darkness,
it replaces every colour variable calibre's web UI defines, it is injected
into the page before </head>, and it is installed only in a reader process.

None of this opens a reader: the page is a byte string and the module that
serves it is a stand-in, so importing QtWebEngine is never needed.
"""

import os
import re
import sys
import types

from calibre_zen.tests.base import ZenTestCase

PLACEHOLDER = re.compile(r'\$\{?[A-Za-z_]')
PAGE = b'<!DOCTYPE html>\n<html><head><style>a { color: red }</style></head><body>hi</body></html>'


def pyj_default_colours() -> list[str]:
    "The names calibre's web UI gives a --calibre-color-*, read from its source so an upstream addition is caught."
    from calibre_zen.reader import look

    path = os.path.normpath(os.path.join(os.path.dirname(look.__file__), '..', '..', '..', 'pyj', 'book_list', 'theme.pyj'))
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        src = f.read()
    body = src.split('DEFAULT_COLORS = {', 1)[1].split('\n}', 1)[0]
    names = re.findall(r"^\s*'([a-z0-9-]+)':\s*c\(", body, re.MULTILINE)
    # The three that theme_variables() writes before it walks the table.
    return ['primary', 'primary-light', 'primary-light-2', *names]


class TestReaderLook(ZenTestCase):
    def setUp(self):
        from calibre_zen.theme.tokens import schemes

        self._scheme = schemes.active().name
        self._dark = schemes.darkness()
        self._font = os.environ.get('CALIBRE_ZEN_FONT')

    def tearDown(self):
        from calibre_zen.theme.tokens import schemes

        schemes.set_active(self._scheme)
        schemes.set_darkness(self._dark)
        if self._font is None:
            os.environ.pop('CALIBRE_ZEN_FONT', None)
        else:
            os.environ['CALIBRE_ZEN_FONT'] = self._font

    def test_every_scheme_renders(self):
        from calibre_zen.reader import look
        from calibre_zen.theme.tokens import schemes

        for name in schemes.SCHEMES:
            schemes.set_active(name)
            for darkness in schemes.DARKNESS:
                schemes.set_darkness(darkness)
                label = f'{name}/{darkness}'
                with self.subTest(label):
                    m = look.mapping()
                    for css in look.templates():
                        sheet = look.render(css, m)
                        left = [ln.strip()[:80] for ln in sheet.splitlines() if PLACEHOLDER.search(ln)]
                        self.assertEqual(left, [], f'{label}/{css}: unsubstituted tokens')
                        self.assertEqual(sheet.count('{'), sheet.count('}'), f'{label}/{css}: unbalanced braces')

    def test_templates_only_name_known_tokens(self):
        from calibre_zen.reader import look

        known = set(look.mapping())
        for name in look.templates():
            with open(os.path.join(look.CSS_DIR, name), encoding='utf-8') as f:
                text = f.read()
            names = set(re.findall(r'\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?', text))
            with self.subTest(name):
                self.assertEqual(sorted(names - known), [])

    def test_alpha_is_css_alpha(self):
        "Chrome writes alpha 0-255 for QSS; CSS clamps anything over 1 to a solid colour."
        from calibre_zen.reader import look

        sheet = look.stylesheet()
        bad = [m.group(0) for m in re.finditer(r'rgba\([^)]*\)', sheet) if float(m.group(0).rstrip(')').rsplit(',', 1)[1]) > 1]
        self.assertEqual(bad, [])

    def test_every_calibre_colour_is_replaced(self):
        from calibre_zen.reader import look

        names = pyj_default_colours()
        if not names:
            self.skipTest('src/pyj is not here')
        self.assertGreater(len(names), 20, 'did not read the colour table')
        sheet = look.stylesheet()
        missing = [n for n in names if not re.search(rf'--calibre-color-{re.escape(n)}:[^;]*!important;', sheet)]
        self.assertEqual(missing, [], 'calibre colours the sheet does not take over')

    def test_light_and_dark_differ(self):
        from calibre_zen.reader import look

        m = look.mapping()
        self.assertNotEqual(m['light_page'], m['dark_page'])
        self.assertNotEqual(m['light_fg'], m['dark_fg'])
        sheet = look.stylesheet()
        self.assertIn(':root[style*="color-scheme: dark"]', sheet)

    def test_dark_honours_dim(self):
        from calibre_zen.reader import look
        from calibre_zen.theme.tokens import schemes

        schemes.set_active('neutral')
        schemes.set_darkness('dark')
        dark = look.mapping()['dark_page']
        schemes.set_darkness('dim')
        dim = look.mapping()['dark_page']
        self.assertNotEqual(dark, dim)

    def test_the_variables_every_agent_reads_exist(self):
        from calibre_zen.reader import look

        sheet = look.stylesheet()
        wanted = (
            'window page surface surface-hover raised fg muted border border-weak border-strong accent accent-text '
            'accent-hover accent-pressed hover pressed selected-soft selection danger danger-bg danger-bg-hover link '
            'tooltip-bg tooltip-fg scrim track scroll scroll-hover ring ring-color ring-glow shadow-sm shadow-lg '
            'radius-row radius-control radius-panel radius-groove radius-mark radius-scroll font font-size font-size-caption '
            'font-size-title line-height weight-regular weight-medium weight-semibold duration duration-fast duration-slow ease'
        ).split()
        missing = [n for n in wanted if f'--zen-{n}:' not in sheet]
        self.assertEqual(missing, [])
        # A colour that is set for light must be set again for dark.
        light, dark = sheet.split(':root[style*="color-scheme: dark"]', 1)
        dark = dark.split('\n}', 1)[0]
        for n in ('window', 'page', 'surface', 'fg', 'muted', 'border', 'accent', 'hover', 'shadow-lg', 'ring-glow'):
            self.assertIn(f'--zen-{n}:', dark, f'{n} has no dark value')

    def test_font_is_inline_and_private(self):
        from calibre_zen.reader import look

        css = look.font_faces()
        self.assertEqual(css.count('@font-face'), 3)
        self.assertEqual(sorted(re.findall(r'font-weight: (\d+)', css)), ['400', '500', '600'])
        self.assertIn('font-family: "Zen UI"', css)
        self.assertNotIn('Inter"', css)
        self.assertNotIn('url(file', css)
        self.assertIn('url("data:font/ttf;base64,', css)
        self.assertIn('system-ui', look.mapping()['font_fallback'])

    def test_font_follows_the_environment(self):
        from calibre_zen.reader import look

        os.environ['CALIBRE_ZEN_FONT'] = 'droid-sans'
        css = look.font_faces()
        self.assertEqual(sorted(re.findall(r'font-weight: (\d+)', css)), ['400', '700'])

    def test_inject_goes_before_head_end(self):
        from calibre_zen.reader import look

        out = look.inject(PAGE, 'b { color: blue }')
        self.assertEqual(out.count(b'id="zen-reader-look"'), 1)
        style = out.index(b'<style id="zen-reader-look">')
        self.assertLess(out.index(b'a { color: red }'), style)
        self.assertLess(style, out.index(b'</head>'))
        self.assertTrue(out.endswith(b'<body>hi</body></html>'))
        # Everything upstream sent is still there, in order.
        ours = look.style_element('b { color: blue }') + look.script_element(look.scripts())
        self.assertEqual(out.replace(ours, b''), PAGE)

    def test_scripts_are_injected_after_the_style(self):
        from calibre_zen.reader import look

        js = look.scripts()
        self.assertIn('--zen-progress', js)
        out = look.inject(PAGE, 'b { color: blue }')
        script = out.index(b'<script id="zen-reader-look-js">')
        self.assertLess(out.index(b'<style id="zen-reader-look">'), script)
        self.assertLess(script, out.index(b'</head>'))

    def test_script_element_cannot_be_closed_early(self):
        from calibre_zen.reader import look

        el = look.script_element('var s = "</script><b>";')
        self.assertEqual(el.count(b'</script>'), 1)

    def test_inject_without_a_head(self):
        from calibre_zen.reader import look

        out = look.inject(b'<p>no head</p>', 'x {}')
        self.assertTrue(out.startswith(b'<style id="zen-reader-look">'))
        self.assertTrue(out.endswith(b'<p>no head</p>'))

    def test_wrap_serves_the_page_once(self):
        from calibre_zen.reader import look

        calls = []

        def viewer_html():
            calls.append(1)
            return PAGE

        module = types.ModuleType('fake_web_view')
        module.viewer_html = viewer_html
        self.assertTrue(look.wrap(module))
        first = module.viewer_html()
        self.assertIn(b'zen-reader-look', first)
        self.assertIs(module.viewer_html(), first, 'built once per process')
        self.assertEqual(len(calls), 1)
        self.assertFalse(look.wrap(module), 'a second wrap must not stack')
        self.assertIs(module.viewer_html.__wrapped__, viewer_html)

    def test_wrap_falls_back_to_the_upstream_page(self):
        from calibre_zen.reader import look

        module = types.ModuleType('fake_web_view')
        module.viewer_html = lambda: PAGE
        orig = look.inject

        def broken(html, css=None):
            raise ValueError('boom')

        look.inject = broken
        self.addCleanup(setattr, look, 'inject', orig)
        look.wrap(module)
        import contextlib
        import io

        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(module.viewer_html(), PAGE)

    def test_a_bad_placeholder_costs_one_file(self):
        from calibre_zen.reader import look

        d = self.mkdtemp()
        with open(os.path.join(d, '10-good.css'), 'w') as f:
            f.write('a { color: $light_fg }')
        with open(os.path.join(d, '20-bad.css'), 'w') as f:
            f.write('b { color: $no_such_token; margin: ${radius_row}px }\na[href$=".pdf"] { top: 0 }')
        with open(os.path.join(d, '30-plain.css'), 'w') as f:
            f.write('c { color: var(--zen-fg) }')
        orig = look.CSS_DIR
        look.CSS_DIR = d
        self.addCleanup(setattr, look, 'CSS_DIR', orig)
        self.assertEqual(look.templates(), ('10-good.css', '20-bad.css', '30-plain.css'))
        sheet = look.stylesheet()
        self.assertIn('a { color: #', sheet)
        self.assertIn('$no_such_token', sheet)
        self.assertRegex(sheet, r'margin: \d+px')
        self.assertIn('a[href$=".pdf"]', sheet)
        self.assertIn('c { color: var(--zen-fg) }', sheet)

    def test_a_new_file_is_picked_up(self):
        from calibre_zen.reader import look

        names = look.templates()
        self.assertEqual(names[:2], ('00-variables.css', '01-base.css'))
        self.assertEqual(list(names), sorted(names))

    def test_install_does_nothing_in_the_main_window(self):
        "This process is not a reader: install() must not wrap anything or import the web engine."
        from calibre_zen.reader import look

        if look.VIEWER_MODULE in sys.modules:
            self.skipTest('this process has the viewer loaded')
        had = look.WEB_VIEW_MODULE in sys.modules
        self.assertFalse(look.install())
        self.assertEqual(look.WEB_VIEW_MODULE in sys.modules, had)

    def test_install_wraps_in_a_reader_and_not_when_off(self):
        from calibre_zen import features
        from calibre_zen.reader import look

        web = types.ModuleType('fake_web_view')
        web.viewer_html = lambda: PAGE
        for name, mod in (('fake_viewer_main', types.ModuleType('fake_viewer_main')), ('fake_web_view', web)):
            sys.modules[name] = mod
            self.addCleanup(sys.modules.pop, name, None)
        orig = (look.VIEWER_MODULE, look.WEB_VIEW_MODULE)
        look.VIEWER_MODULE, look.WEB_VIEW_MODULE = 'fake_viewer_main', 'fake_web_view'
        self.addCleanup(lambda: (setattr(look, 'VIEWER_MODULE', orig[0]), setattr(look, 'WEB_VIEW_MODULE', orig[1])))

        features._at_start['reader-look'] = False
        self.addCleanup(features._at_start.pop, 'reader-look', None)
        self.assertFalse(look.install())
        self.assertFalse(getattr(web.viewer_html, 'zen_reader_look', False))

        features._at_start['reader-look'] = True
        self.assertTrue(look.install())
        self.assertTrue(web.viewer_html.zen_reader_look)
        self.assertIn(b'zen-reader-look', web.viewer_html())
        self.assertTrue(look.install(), 'install() is idempotent')
        self.assertEqual(web.viewer_html.__wrapped__.__name__, '<lambda>')

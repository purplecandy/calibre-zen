#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Tokens in, QPalette and QSS out.

QSS has no variables, so the templates under qss/ are written with `$name`
placeholders and substituted here. `$name` is chosen over `{name}` because QSS
is nothing but braces: a `.format()` template would have to double every one of
them and would stop being readable as a stylesheet.

A template may name any attribute of `semantic.Chrome`, any token in
`components`, and the mark images. Nothing else -- and a name that is not
one of those is a bug in the template, reported rather than silently dropped.
"""

import hashlib
import os
from functools import cache
from string import Template

from qt.core import QColor, QIcon, QPalette

from calibre_zen.theme.tokens import components, primitives, semantic

HERE = os.path.dirname(os.path.abspath(__file__))
QSS_DIR = os.path.join(HERE, 'qss')
MARKS_DIR = os.path.join(HERE, 'marks')
FONTS_DIR = os.path.join(HERE, 'fonts')


# Palette {{{


def palette(spec: dict) -> QPalette:
    "Build a QPalette from one of the semantic maps."
    p = QPalette()
    disabled = QColor(spec['Disabled'])
    for name, value in spec.items():
        if name == 'Disabled':
            continue
        p.setColor(getattr(QPalette.ColorRole, name), QColor(value))
    for name in semantic.DISABLED_ROLES:
        p.setColor(QPalette.ColorGroup.Disabled, getattr(QPalette.ColorRole, name), disabled)
    return p


def dark_palette() -> QPalette:
    return palette(semantic.palette_spec(True))


def light_palette() -> QPalette:
    return palette(semantic.palette_spec(False))


# }}}


# Fonts {{{

# Inter's four faces share one typographic-family name record, so Qt's font
# database groups them under one family and a template names only the family,
# picking the weight with a plain number -- confirmed against this build's Qt
# with QFontInfo.exactMatch, since that grouping is a font-database behaviour,
# not a guarantee. A family CALIBRE_ZEN_FONT selects with fewer real weights
# just gets Qt's nearest match for the ones it lacks.

_fonts_installed = False


def install_fonts() -> bool:
    """
    Register the vendored faces of both selected families with Qt -- the UI
    family (CALIBRE_ZEN_FONT) and the serif (CALIBRE_ZEN_SERIF), which are
    loaded together because the serif is used for one element rather than
    instead of the other. Naming the same family twice loads it once.
    Idempotent, safe to call before a QApplication has finished constructing.
    A face that fails to load costs that weight, not the app -- Qt falls back
    to the nearest weight it has.
    """
    global _fonts_installed
    if _fonts_installed:
        return True
    from qt.core import QFontDatabase

    seen = set()
    for font in (primitives.active_font(), primitives.active_serif()):
        if font['dir'] in seen:
            continue
        seen.add(font['dir'])
        for name in font['faces']:
            QFontDatabase.addApplicationFont(os.path.join(FONTS_DIR, font['dir'], name))
    _fonts_installed = True
    return True


# }}}


# Mark images {{{

# Qt stops drawing a subcontrol natively the moment you style it, so a rounded
# accent-filled checkbox has to supply its own tick. QSS url() wants a real
# file, so the marks are written to the cache directory once per colour and
# reused. They are a few hundred bytes each.


def mark_path(name: str, color: str) -> str | None:
    """
    The mark as a file on disk, written on demand. None if unwritable.

    A path rather than only a url() because the filter panel paints its
    chevrons and marks itself, with a QIcon, rather than asking QSS for them.
    """
    from calibre.constants import cache_dir

    try:
        with open(os.path.join(MARKS_DIR, f'{name}.svg')) as f:
            data = Template(f.read()).safe_substitute(color=color)
    except OSError:
        return None
    d = os.path.join(cache_dir(), 'zen-style')
    digest = hashlib.sha256(data.encode('utf-8')).hexdigest()[:12]
    path = os.path.join(d, f'{name}-{digest}.svg')
    try:
        if not os.path.exists(path):
            os.makedirs(d, exist_ok=True)
            with open(path, 'w') as f:
                f.write(data)
    except OSError:
        return None
    return path


def mark_icon(name: str, color: str) -> QIcon:
    "The mark as a QIcon, for whoever is painting rather than styling."
    path = mark_path(name, color)
    return QIcon() if path is None else QIcon(path)


def mark_url(name: str, color: str) -> str:
    "Path to the mark, written on demand. Falls back to no image if unwritable."
    path = mark_path(name, color)
    if path is None:
        return 'none'
    # QSS url() takes forward slashes on every platform.
    return f'url("{path.replace(os.sep, "/")}")'


# }}}


# Templates {{{


@cache
def template(relpath: str) -> Template:
    with open(os.path.join(QSS_DIR, relpath)) as f:
        return Template(f.read())


@cache
def app_templates() -> tuple:
    "Every app sheet, in filename order. The numeric prefixes are that order."
    d = os.path.join(QSS_DIR, 'app')
    return tuple(os.path.join('app', n) for n in sorted(os.listdir(d)) if n.endswith('.qss'))


def mapping(pal: QPalette, is_dark: bool) -> dict:
    # The radii belong to the active scheme and are plain module attributes, so
    # something has to re-read them when the scheme changes. Doing it here
    # means every re-theme picks them up, whatever asked for the re-theme.
    components.refresh()
    chrome = semantic.Chrome(pal, is_dark)
    m = components.as_mapping()
    m.update(chrome.as_mapping())
    m.update(
        mark_check=mark_url('check', chrome.accent_text),
        mark_dash=mark_url('dash', chrome.accent_text),
        mark_dot=mark_url('dot', chrome.accent_text),
        # Qt draws every arrow as a filled triangle. Chevrons are what the rest
        # of the UI is drawn in, and muted because an indicator is never the
        # thing you are looking at.
        mark_chevron_down=mark_url('chevron-down', chrome.muted),
        mark_chevron_left=mark_url('chevron-left', chrome.muted),
        mark_chevron_right=mark_url('chevron-right', chrome.muted),
        mark_chevron_up=mark_url('chevron-up', chrome.muted),
    )
    return m


def render(relpath: str, m: dict) -> str:
    t = template(relpath)
    try:
        return t.substitute(m)
    except (KeyError, ValueError) as err:
        # A bad placeholder should cost one rule, not the whole UI.
        from calibre.constants import DEBUG

        if DEBUG:
            print(f'calibre-zen: {relpath}: bad placeholder: {err}')
        return t.safe_substitute(m)


def stylesheet(pal: QPalette, is_dark: bool) -> str:
    "The one application-wide sheet."
    m = mapping(pal, is_dark)
    return '\n'.join(render(rel, m) for rel in app_templates())


def local_stylesheet(name: str, pal: QPalette, is_dark: bool) -> str:
    "A sheet calibre applies to one widget rather than to the application."
    return render(os.path.join('local', f'{name}.qss'), mapping(pal, is_dark))


# }}}

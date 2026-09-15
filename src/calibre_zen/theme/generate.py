#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Tokens in, QPalette and QSS out.

QSS has no variables, so the templates under qss/ are written with `$name`
placeholders and substituted here. `$name` is chosen over `{name}` because QSS
is nothing but braces: a `.format()` template would have to double every one of
them and would stop being readable as a stylesheet.

A template may name any attribute of `semantic.Chrome`, any token in
`components`, and the three mark images. Nothing else -- and a name that is not
one of those is a bug in the template, reported rather than silently dropped.
"""

import hashlib
import os
from functools import cache
from string import Template

from qt.core import QColor, QPalette

from calibre_zen.theme.tokens import components, semantic

HERE = os.path.dirname(os.path.abspath(__file__))
QSS_DIR = os.path.join(HERE, 'qss')
MARKS_DIR = os.path.join(HERE, 'marks')


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
    return palette(semantic.PALETTE_DARK)


def light_palette() -> QPalette:
    return palette(semantic.PALETTE_LIGHT)


# }}}


# Mark images {{{

# Qt stops drawing a subcontrol natively the moment you style it, so a rounded
# accent-filled checkbox has to supply its own tick. QSS url() wants a real
# file, so the marks are written to the cache directory once per colour and
# reused. They are a few hundred bytes each.


def mark_url(name: str, color: str) -> str:
    "Path to the mark, written on demand. Falls back to no image if unwritable."
    from calibre.constants import cache_dir

    try:
        with open(os.path.join(MARKS_DIR, f'{name}.svg')) as f:
            data = Template(f.read()).safe_substitute(color=color)
    except OSError:
        return 'none'
    d = os.path.join(cache_dir(), 'zen-style')
    digest = hashlib.sha256(data.encode('utf-8')).hexdigest()[:12]
    path = os.path.join(d, f'{name}-{digest}.svg')
    try:
        if not os.path.exists(path):
            os.makedirs(d, exist_ok=True)
            with open(path, 'w') as f:
                f.write(data)
    except OSError:
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
    chrome = semantic.Chrome(pal, is_dark)
    m = components.as_mapping()
    m.update(chrome.as_mapping())
    m.update(
        mark_check=mark_url('check', chrome.accent_text),
        mark_dash=mark_url('dash', chrome.accent_text),
        mark_dot=mark_url('dot', chrome.accent_text),
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

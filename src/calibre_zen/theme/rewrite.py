#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Containment for widget-local stylesheets.

A sheet set on a widget beats the application sheet for that widget and its
children, so one `setStyleSheet('QComboBox { color: black }')` upstream punches
a hole straight through the overlay -- and on a dark palette that particular
hole is black text on a near-black field.

The fix could be an edit upstream. It is here instead, because the whole point
of the overlay is that `git pull` stays boring: a rule that stops matching
because upstream reworded its sheet costs us that one fix and nothing else.

`PATCHES` is matched on the exact sheet text with runs of whitespace collapsed,
not by pattern, so nothing is rewritten by accident. Set
CALIBRE_ZEN_STYLE_AUDIT=1 to print every widget-local sheet that hard-codes a
colour, which is how the next hole gets found.
"""

import os
import re

from qt.core import QWidget

_WS = re.compile(r'\s+')
_HARDCODED = re.compile(r'(?<!-)\b(?:black|white|gray|grey|red|blue|green|yellow)\b|#[0-9a-fA-F]{3,8}')

_installed = False
_orig_set_stylesheet = None


def normalize(sheet: str) -> str:
    return _WS.sub(' ', sheet).strip()


# Each value takes the live Chrome tokens and returns the sheet to use instead.
# calibre/gui2/widgets.py, EnComboBox.set_state(): the placeholder row is drawn
# in a hard-coded grey and every other row in a hard-coded black, which on a
# dark palette is invisible.
PATCHES = {
    normalize('QComboBox { color: gray }'): lambda t: f'QComboBox {{ color: {t.muted} }}',
    normalize('QComboBox { color: black }'): lambda t: 'QComboBox { color: palette(text) }',
}


def auditing() -> bool:
    return os.environ.get('CALIBRE_ZEN_STYLE_AUDIT', '') not in ('', '0', 'false', 'no', 'off')


def chrome():
    from calibre.gui2 import qapplication_or_fail
    from calibre_zen.theme.tokens.semantic import Chrome

    app = qapplication_or_fail()
    return Chrome(app.palette(), bool(app.property('is_dark_theme')))


def rewrite(sheet: str) -> str:
    if not sheet:
        return sheet
    patch = PATCHES.get(normalize(sheet))
    if patch is not None:
        try:
            return patch(chrome())
        except Exception:
            return sheet
    if auditing() and _HARDCODED.search(sheet):
        print('calibre-zen: widget-local sheet hard-codes a colour:', normalize(sheet))
    return sheet


def install() -> bool:
    """
    Wrap QWidget.setStyleSheet. Returns False if Qt will not allow it, which is
    not fatal: without the wrapper the listed holes come back, nothing else
    changes.
    """
    global _installed, _orig_set_stylesheet
    if _installed:
        return True
    orig = QWidget.setStyleSheet

    def setStyleSheet(self, sheet):  # noqa: N802  (matching the Qt name is the point)
        return orig(self, rewrite(sheet))

    try:
        QWidget.setStyleSheet = setStyleSheet
    except AttributeError, TypeError:
        return False
    _orig_set_stylesheet = orig
    _installed = True
    return True

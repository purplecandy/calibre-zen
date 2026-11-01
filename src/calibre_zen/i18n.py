#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Translations for the strings this fork adds.

calibre's translations are one compiled catalog per language, inside the binary
this fork is laid on top of, and it knows nothing of a string only we wrote. So
those stayed English in an otherwise translated window. Ours live beside the
code, as `locales/<lang>.po`, and are added to calibre's translator as a
*fallback*: calibre's own catalog is asked first and keeps every string it has,
and ours answer only for the ones it has no entry for.

Two things make "add them once" not enough:

* calibre changes language while running -- the welcome wizard's language box
  calls `set_translators()` again, which builds a new translator and drops the
  fallback. The call is wrapped, so the new translator gets ours too.
* some of our modules translate at import (`STEPS` in onboarding/page.py), so
  `hooks.py` installs this before it imports them.

A `.po` is compiled with calibre's own `msgfmt`, in memory, when the language
is picked; nothing is written to the install directory, which a package may
have installed read-only. A language with no file here is left alone.
"""

import io
import os
import sys
import traceback
from functools import wraps

LOCALES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'locales')

_installed = False
_attached_to = None  # the translator the catalog was last added to
_own = None  # our catalog alone, for override()


def catalog_for(lang: str | None) -> str | None:
    "The .po for a language code like `he` or `pt_BR`: exact match, then the bare language."
    if not lang:
        return None
    for code in (lang, lang.split('_')[0].lower()):
        path = os.path.join(LOCALES, code + '.po')
        if os.path.exists(path):
            return path
    return None


def compile_po(path: str) -> bytes | None:
    """
    A .po as the bytes of a .mo, or None if calibre's compiler gives up on it.

    `make_with_stats`, not `make`: msgfmt keeps its messages in a module-level
    dict that `make` only ever adds to, so a second catalog would arrive with
    the first one's strings in it. It also exits the process on a malformed
    file, which is not an `Exception`.
    """
    from calibre.translations import msgfmt

    buf = io.BytesIO()
    try:
        msgfmt.make_with_stats(path, buf)
    except (Exception, SystemExit):
        traceback.print_exc()
        return None
    return buf.getvalue()


def attach() -> bool:
    "Add our catalog to calibre's current translator. Returns whether one was added."
    global _attached_to
    from calibre_extensions.translator import Translator

    from calibre.utils import localization

    global _own
    current = localization.default_translator
    if current is _attached_to:
        return False
    _own = None
    path = catalog_for(localization.get_lang())
    if path is None:
        return False
    compiled = compile_po(path)
    if compiled is None:
        return False
    _own = Translator(compiled)
    current.add_fallback(Translator(compiled))
    _attached_to = current
    return True


def override(msgid: str) -> str:
    """
    `msgid` as our catalog has it, else as calibre's does.

    The fallback above never answers for a string calibre already translates,
    which is right for ours and wrong for the few of calibre's we word
    differently ("Save to disk" is a line long in Hebrew). The source has to
    spell the string out as the argument, so the tests can see it is in use.
    """
    if _own is not None:
        ans = _own.gettext(msgid)
        if ans != msgid:
            return ans
    return _(msgid)  # noqa: F821  (calibre installs it)


def install() -> bool:
    "Attach now and after every language switch. Safe to call twice; never raises."
    global _installed
    if _installed:
        return True
    try:
        from calibre.utils import localization

        cls = type(localization.set_translators)
        orig = cls.__call__
        if not hasattr(orig, '__wrapped__'):  # an earlier call got as far as wrapping

            @wraps(orig)
            def __call__(self, *args, **kwargs):
                result = orig(self, *args, **kwargs)
                try:
                    attach()
                except Exception:
                    traceback.print_exc()
                return result

            cls.__call__ = __call__
        attach()
    except Exception:
        # Untranslated strings are an acceptable Tuesday; a window that does not
        # open is not.
        traceback.print_exc()
        print('calibre-zen: translations did not install and are off for this session', file=sys.stderr)
        return False
    _installed = True
    return True

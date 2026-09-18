#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Whose exception is it?

Zen sits between calibre and its user, so when something breaks the first
question is where. The traceback answers it: a frame under `calibre_zen/`
means our code was on the stack, including the case that matters most --
upstream code called from inside one of our wraps, which is exactly where a
renamed upstream method surfaces. No frame of ours means the bug is calibre's
or a third-party plugin's, and it is not ours to collect.
"""

import os

ZEN = 'zen'
UPSTREAM = 'upstream'
PLUGIN = 'plugin'

_ZEN_MARK = os.sep + 'calibre_zen' + os.sep
_CALIBRE_MARK = os.sep + 'calibre' + os.sep
_PLUGIN_MODULE_PREFIX = 'calibre_plugins.'


def frames(exc: BaseException | None, tb=None):
    """
    Every traceback frame of an exception and its chain, oldest first.

    Yields (frame, lineno, module_name) for the chain `__cause__`/`__context__`
    leads to, then for `exc` itself, the order Sentry expects.
    """
    seen = set()

    def walk(e, t):
        if e is None or id(e) in seen:
            return
        seen.add(id(e))
        nxt = e.__cause__ or (None if e.__suppress_context__ else e.__context__)
        yield from walk(nxt, getattr(nxt, '__traceback__', None))
        t = t if t is not None else e.__traceback__
        while t is not None:
            f = t.tb_frame
            yield f, t.tb_lineno, f.f_globals.get('__name__', '')
            t = t.tb_next

    yield from walk(exc, tb)


def frame_origin(filename: str, module: str) -> str:
    if _ZEN_MARK in filename or filename.startswith('calibre_zen' + os.sep):
        return ZEN
    if module.startswith(_PLUGIN_MODULE_PREFIX) or module == 'calibre_plugins' or filename.endswith('.zip'):
        return PLUGIN
    return UPSTREAM


def origin(exc: BaseException | None, tb=None) -> str:
    """
    ZEN if any frame is ours, else PLUGIN if any frame is a third-party
    plugin's, else UPSTREAM. A plugin calling into a method we wrapped is ZEN:
    the wrap is on the stack, and whether it broke under the plugin's use is
    a judgement for the person reading the report, not for the classifier.
    """
    ans = UPSTREAM
    for f, _lineno, module in frames(exc, tb):
        o = frame_origin(f.f_code.co_filename, module)
        if o == ZEN:
            return ZEN
        if o == PLUGIN:
            ans = PLUGIN
    return ans


def has_plugin_frames(exc: BaseException | None, tb=None) -> bool:
    return any(frame_origin(f.f_code.co_filename, m) == PLUGIN for f, _l, m in frames(exc, tb))

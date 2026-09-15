#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Icon packs, discovered rather than listed.

A new provider is one module in this directory exposing a module-level `pack`.
Nothing else has to be edited to make it selectable with CALIBRE_ZEN_ICONS.
"""

import importlib
import os

HERE = os.path.dirname(os.path.abspath(__file__))
_found = None


def discover() -> dict:
    global _found
    if _found is None:
        _found = {}
        for fname in sorted(os.listdir(HERE)):
            if not fname.endswith('.py') or fname.startswith('_'):
                continue
            mod = importlib.import_module(f'{__name__}.{fname[:-3]}')
            pack = getattr(mod, 'pack', None)
            if pack is not None:
                _found[pack.name] = pack
    return _found

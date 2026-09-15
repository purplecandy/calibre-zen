#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
An icon pack: calibre's icon names mapped onto a directory of monochrome SVGs.

The only thing a pack has to answer is `svg(name)`. Everything else -- colour,
size, caching, when to fall back to calibre's own icons -- belongs to the
registry, so a second pack is a map and a directory of glyphs and no logic.
"""

import os

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')

# Roles a pack may ask for. All but 'success' resolve against the live palette.
ROLES = ('text', 'accent', 'danger', 'success')


class Pack:
    def __init__(self, name: str, title: str, mapping: dict, extras: tuple = (), directory: str = ''):
        self.name = name
        self.title = title
        self.mapping = mapping
        # Glyphs the overlay asks for by name rather than through a calibre icon
        # name. Without listing them, vendoring -- which follows the map -- would
        # never copy them, and a glyph that is not on disk fails silently.
        self.extras = tuple(extras)
        self.directory = directory or os.path.join(ASSETS, name)

    def glyph(self, icon_name: str) -> tuple:
        "(glyph, role) for a calibre icon name, or (None, None) if unmapped."
        spec = self.mapping.get(icon_name)
        if spec is None:
            return None, None
        if isinstance(spec, tuple):
            glyph, role = spec
        else:
            glyph, role = spec, 'text'
        return glyph, role

    def svg(self, icon_name: str) -> tuple:
        """
        (svg source, role) for a calibre icon name.

        (None, None) means this pack does not cover that icon -- including when
        the glyph is mapped but not vendored, so a half-finished map degrades to
        calibre's own icon rather than to a blank button.
        """
        glyph, role = self.glyph(icon_name)
        if glyph is None:
            return None, None
        try:
            with open(os.path.join(self.directory, f'{glyph}.svg')) as f:
                return f.read(), role
        except OSError:
            return None, None

    def glyph_svg(self, glyph: str) -> str:
        "A glyph by its own name, for chrome calibre has no icon name for."
        try:
            with open(os.path.join(self.directory, f'{glyph}.svg')) as f:
                return f.read()
        except OSError:
            return ''

    def required_glyphs(self) -> tuple:
        "Every glyph this pack needs on disk, mapped or asked for by name."
        glyphs = {self.glyph(name)[0] for name in self.mapping}
        glyphs.update(self.extras)
        return tuple(sorted(g for g in glyphs if g))

    def missing(self) -> tuple:
        "Required glyphs that are not vendored. Empty is the healthy answer."
        return tuple(g for g in self.required_glyphs() if not os.path.exists(os.path.join(self.directory, f'{g}.svg')))

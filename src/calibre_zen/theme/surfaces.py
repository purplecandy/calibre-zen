#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
A bar lifted off the page, the way the title bar sits over its window.

A dialog's footer is drawn on `raised` (semantic.py) with a hairline above it
in the sheet; what the sheet cannot draw is the soft shadow it casts up over
the page. That is a QGraphicsDropShadowEffect, which follows the widget's
shape, stronger in a dark palette where a faint one would not show at all.
Every footer the overlay builds goes through `lift()`, so they all agree.
"""


def lift(widget) -> None:
    from qt.core import QColor, QGraphicsDropShadowEffect

    from calibre.gui2 import qapplication_or_fail
    from calibre_zen.theme.tokens import components

    dark = bool(qapplication_or_fail().property('is_dark_theme'))
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(components.FOOTER_SHADOW_BLUR)
    effect.setOffset(0, -1)
    color = QColor(0, 0, 0)
    color.setAlphaF(components.FOOTER_SHADOW_DARK if dark else components.FOOTER_SHADOW_LIGHT)
    effect.setColor(color)
    widget.setGraphicsEffect(effect)

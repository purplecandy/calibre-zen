#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
A stand-in cover for a cover-grid book that has none.

calibre writes such a book's title and authors straight onto the grid, in a
colour it picks for its own dark grey background (`GridView.do_set_color`).
The app sheet paints the grid in the theme's base colour instead, so in a
light scheme that text was near-white on white and the tile looked empty.

Rather than only fix the ink, the book gets a cover: a card the size of the
tile's cover box in the theme's own colours, its title in the serif the
preview uses and its authors under it. It is handed to calibre as the book's
thumbnail (`grid.attach` wraps the cache), so calibre draws it exactly as it
draws any cover -- the corner radius, the ring, the hover bar, the Natural and
Uniform shapes and the emblems all apply without being told.

Nothing is written to the library. A real cover replaces the stand-in the
moment it exists, because calibre's cache stops returning a null thumbnail.

Made once per book, size and palette, and kept in a small cache keyed on the
title and authors too, so an edit or a scheme switch shows on the next paint.
"""

from qt.core import QColor, QFont, QFontMetrics, QPainter, QPalette, QPixmap, QRectF, Qt

from calibre_zen.theme.tokens import components

_made: dict = {}
MADE_CACHE = 600  # stand-ins held at once; a screenful is a fraction of this


def forget() -> None:
    _made.clear()


def wrap(text: str, metrics: QFontMetrics, width: float, max_lines: int) -> list[str]:
    """
    `text` broken into lines no wider than `width`, at most `max_lines` of them.
    The last line is elided when the text runs on, and so is any single word
    too long for a line of its own.
    """
    words = text.split()
    lines: list[str] = []
    line = ''
    for i, word in enumerate(words):
        trial = f'{line} {word}' if line else word
        if metrics.horizontalAdvance(trial) <= width or not line:
            line = trial
            continue
        lines.append(line)
        line = word
        if len(lines) == max_lines:
            line = ' '.join([lines.pop()] + words[i:])
            break
    if line:
        lines.append(line)
    lines = lines[:max_lines]
    elide = Qt.TextElideMode.ElideRight
    return [metrics.elidedText(one, elide, int(width)) for one in lines]


def colours() -> tuple[QColor, QColor, QColor]:
    "The card, its title and its authors, from the live palette."
    from calibre.gui2 import qapplication_or_fail
    from calibre_zen.centre.table import colors

    chrome = colors()
    text = qapplication_or_fail().palette().color(QPalette.ColorRole.Text)
    return QColor(chrome.track), text, QColor(chrome.muted)


def font(family: str, share: float, width: float, bold: bool = False) -> QFont:
    f = QFont(family)
    f.setPixelSize(max(components.GRID_PLACEHOLDER_MIN_PX, round(width * share)))
    if bold:
        f.setWeight(QFont.Weight.DemiBold)
    return f


def render(title: str, authors: str, width: int, height: int, dpr: float) -> QPixmap:
    """
    The stand-in itself, `width` x `height` device pixels. Painted in logical
    pixels, so the type is the same size on a Retina screen as off one.
    """
    card, ink, soft = colours()
    out = QPixmap(width, height)
    out.setDevicePixelRatio(dpr)
    out.fill(card)
    w, h = width / dpr, height / dpr
    pad = w * components.GRID_PLACEHOLDER_PAD
    inner = QRectF(pad, pad, w - 2 * pad, h - 2 * pad)

    title_font = font(components.FONT_FAMILY_SERIF, components.GRID_PLACEHOLDER_TITLE, w, bold=True)
    author_font = font(components.FONT_FAMILY, components.GRID_PLACEHOLDER_AUTHOR, w)
    tm, am = QFontMetrics(title_font), QFontMetrics(author_font)
    author_lines = wrap(authors, am, inner.width(), components.GRID_PLACEHOLDER_AUTHOR_LINES) if authors else []
    # The title gets whatever height the authors leave, a line's gap between.
    room = inner.height() - len(author_lines) * am.lineSpacing() - (am.lineSpacing() if author_lines else 0)
    fits = max(1, int(room // tm.lineSpacing()))
    title_lines = wrap(title, tm, inner.width(), min(fits, components.GRID_PLACEHOLDER_TITLE_LINES))

    painter = QPainter(out)
    try:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        centre = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        painter.setFont(title_font)
        painter.setPen(ink)
        y = inner.top()
        for line in title_lines:
            painter.drawText(QRectF(inner.left(), y, inner.width(), tm.lineSpacing()), centre, line)
            y += tm.lineSpacing()
        painter.setFont(author_font)
        painter.setPen(soft)
        y = inner.bottom() - len(author_lines) * am.lineSpacing()
        for line in author_lines:
            painter.drawText(QRectF(inner.left(), y, inner.width(), am.lineSpacing()), centre, line)
            y += am.lineSpacing()
    finally:
        painter.end()
    return out


def for_book(db, book_id: int, width: int, height: int, dpr: float) -> QPixmap:
    "The stand-in for one book, from the cache when nothing about it has changed."
    from calibre.ebooks.metadata import authors_to_string

    title = db.field_for('title', book_id, default_value='') or ''
    authors = authors_to_string(db.field_for('authors', book_id, default_value=()) or ())
    card, ink, soft = colours()
    key = (book_id, title, authors, width, height, dpr, card.rgba(), ink.rgba(), soft.rgba())
    ans = _made.get(key)
    if ans is None:
        if len(_made) > MADE_CACHE:
            _made.clear()
        ans = _made[key] = render(title, authors, width, height, dpr)
    return ans

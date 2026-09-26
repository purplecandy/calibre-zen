#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The selected match, beside the list.

calibre shows the selected match as one block of HTML in a `Comments`
browser: a centred title, the authors in italics, star characters, a "See at"
line of links, the tags run together with commas, then the description.
`MatchPanel` shows the same facts as the preview above the book list shows
a book: the title in the serif, the authors under it, a line of facts, the
tags as pills, then the summary and the links under small headings. It reads
the same `Metadata` calibre's HTML was built from, and calibre's `Comments`
widget is kept, hidden, so its wait timer and its signal still have a home.

Above the summary, when the dialog was opened from the Edit metadata dialog,
"What changes": each field this match would change, with the value it has now. It
is read-only and only describes what calibre's `update_from_mi` will do with
the match -- tags are added to the ones already there, identifiers are merged
in, the fields in "ignore fields" are left out -- it does not decide any of
it.
"""

from html import escape

from qt.core import QFrame, QGridLayout, QLabel, QScrollArea, QSizePolicy, Qt, QVBoxLayout, QWidget

from calibre_zen.download.chrome import colors, styled
from calibre_zen.theme.tokens import components


def fmt_series_index(value) -> str:
    from calibre.ebooks.metadata import fmt_sidx

    try:
        return fmt_sidx(float(value))
    except Exception:
        return str(value)


def fmt_date(d) -> str:
    from calibre.utils.date import format_date, is_date_undefined

    if d is None or is_date_undefined(d):
        return ''
    return format_date(d, 'd MMM yyyy')


def fmt_rating(stars) -> str:
    "A rating out of five, as a number: the UI font is not promised a star glyph."
    try:
        value = float(stars)
    except TypeError, ValueError:
        return ''
    if value <= 0:
        return ''
    return _('{} out of 5').format(f'{value:g}')


def language_names(codes) -> str:
    from calibre.utils.localization import calibre_langcode_to_name, canonicalize_lang

    out = []
    for code in codes or ():
        c = canonicalize_lang(code)
        if c:
            out.append(calibre_langcode_to_name(c))
    return ', '.join(out)


def facts(book) -> list:
    "Rating, publisher, date and language: the preview's facts line, for a match."
    parts = []
    if not book.is_null('rating'):
        parts.append('★ ' + f'{float(book.rating):g}')
    if book.publisher:
        parts.append(book.publisher)
    d = fmt_date(book.pubdate)
    if d:
        parts.append(d)
    langs = language_names(book.languages)
    if langs:
        parts.append(langs)
    return parts


# What changes {{{

FIELD_TITLES = {
    'title': 'Title',
    'authors': 'Authors',
    'series': 'Series',
    'publisher': 'Publisher',
    'pubdate': 'Published',
    'languages': 'Languages',
    'rating': 'Rating',
    'tags': 'Tags',
    'identifiers': 'Identifiers',
    'comments': 'Summary',
}


def _current(editor, field):
    widget = getattr(editor, field, None)
    return getattr(widget, 'current_val', None)


def changes(book, editor) -> list:
    """
    [(field, title, now, after)] for every field this match would change.

    `now` is the text of what the field holds and `after` of what it will
    hold, both plain text. A field whose read fails is left out rather than
    guessed at, and so is one the reader has told calibre to ignore.
    """
    from calibre.ebooks.metadata import authors_to_string
    from calibre.ebooks.metadata.sources.prefs import msprefs

    ignored = {f for f in (msprefs['ignore_fields'] or ()) if ':' not in f}
    out = []

    def add(field, now, after):
        now, after = (now or '').strip(), (after or '').strip()
        if field in ignored or not after or now == after:
            return
        out.append((field, _(FIELD_TITLES[field]), now, after))

    def attempt(field, fn):
        if field in ignored:
            return
        try:
            fn()
        except Exception:
            # One field that cannot be read is not a reason to hide the rest.
            pass

    if editor is None:
        return out

    attempt('title', lambda: add('title', _current(editor, 'title'), '' if book.is_null('title') else book.title))
    attempt(
        'authors',
        lambda: add('authors', authors_to_string(_current(editor, 'authors') or []), '' if book.is_null('authors') else authors_to_string(book.authors)),
    )

    def series():
        if book.is_null('series') or not book.series.strip():
            return
        now = _current(editor, 'series') or ''
        if now:
            now = f'{now} [{fmt_series_index(_current(editor, "series_index"))}]'
        after = book.series if book.series_index is None else f'{book.series} [{fmt_series_index(book.series_index)}]'
        add('series', now, after)

    attempt('series', series)
    attempt('publisher', lambda: add('publisher', _current(editor, 'publisher'), '' if book.is_null('publisher') else book.publisher))
    attempt('pubdate', lambda: add('pubdate', fmt_date(_current(editor, 'pubdate')), '' if book.is_null('pubdate') else fmt_date(book.pubdate)))
    attempt('languages', lambda: add('languages', language_names(_current(editor, 'languages')), language_names(book.languages)))

    def rating():
        if book.is_null('rating'):
            return
        now = _current(editor, 'rating') or 0
        add('rating', fmt_rating(float(now) / 2), fmt_rating(book.rating))

    attempt('rating', rating)

    def tags():
        # update_from_mi merges: the new ones go in front of those already there.
        if book.is_null('tags'):
            return
        now = list(_current(editor, 'tags') or [])
        have = {t.lower() for t in now}
        new = [t for t in book.tags if t.lower() not in have]
        if not new:
            return
        # Nothing is struck through: the tags already there stay.
        text = ', '.join(new) if not now else _('Adds {}').format(', '.join(new))
        out.append(('tags', _(FIELD_TITLES['tags']), '', text))

    attempt('tags', tags)

    def identifiers():
        # And identifiers are merged in, key by key.
        if book.is_null('identifiers'):
            return
        now = dict(_current(editor, 'identifiers') or {})
        new = {k: v for k, v in book.identifiers.items() if now.get(k) != v}
        if new:
            text = ', '.join(f'{k}:{v}' for k, v in sorted(new.items()))
            out.append(('identifiers', _(FIELD_TITLES['identifiers']), '', _('Adds {}').format(text)))

    attempt('identifiers', identifiers)

    def comments():
        after = (book.comments or '').strip()
        if not after:
            return
        now = (_current(editor, 'comments') or '').strip()
        if now == after:
            return
        if not now:
            text = _('Adds the downloaded summary')
        elif msprefs['append_comments']:
            text = _('Adds the downloaded summary after yours')
        else:
            text = _('Replaces your summary')
        out.append(('comments', _(FIELD_TITLES['comments']), '', text))

    attempt('comments', comments)
    return out


# }}}


class Section(QLabel):
    """
    A small heading over one part of the panel. The air above it is the
    sheet's padding rather than a spacer, so a hidden section takes its gap
    with it.
    """

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName('zenMatchSection')
        # A label with sheet padding counts as framed, and a framed label
        # indents its text by half an x unless told not to.
        self.setIndent(0)


class Pill(QLabel):
    "One tag. A dynamic property rather than an objectName -- there are many."

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setProperty('zenPill', True)


def tag_flow(parent):
    """
    calibre's FlowLayout, spaced by its own spacing. Stock it asks the style
    for a layout spacing first, and under the app sheet the answer overlapped
    the second line of pills with the first.
    """
    from calibre.gui2.widgets2 import FlowLayout

    class TagFlow(FlowLayout):
        def smart_spacing(self, horizontal=True):
            return self.spacing()

    return TagFlow(parent)


class MatchPanel(QFrame):
    def __init__(self, editor_of=None, parent=None):
        super().__init__(parent)
        styled(self, 'zenMatchDetails')
        self.editor_of = editor_of or (lambda: None)
        self.setMinimumWidth(components.DOWNLOAD_PANEL_MIN_WIDTH)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        self.scroll = QScrollArea(self)
        self.scroll.setObjectName('zenMatchDetailsScroll')
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        outer.addWidget(self.scroll)

        body = styled(QWidget(), 'zenMatchDetailsBody')
        self.body = body
        col = QVBoxLayout(body)
        pad = components.DOWNLOAD_PANEL_PAD
        col.setContentsMargins(pad, pad, pad, pad)
        col.setSpacing(components.DOWNLOAD_LINE_GAP)

        def label(name, wrap=True):
            w = QLabel(body)
            w.setObjectName(name)
            w.setWordWrap(wrap)
            w.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            w.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            col.addWidget(w)
            return w

        self.series = label('zenMatchSeries')
        self.title = label('zenMatchTitle')
        self.authors = label('zenMatchAuthors')
        self.facts = label('zenMatchFacts')
        col.addSpacing(components.DOWNLOAD_GAP)
        self.tags_host = QWidget(body)
        self.tags = tag_flow(self.tags_host)
        self.tags.setContentsMargins(0, 0, 0, 0)
        self.tags.setSpacing(5)
        col.addWidget(self.tags_host)

        self.changes_heading = Section(_('What changes'), body)
        col.addWidget(self.changes_heading)
        self.changes_host = styled(QWidget(body), 'zenMatchChanges')
        self.changes_grid = QGridLayout(self.changes_host)
        self.changes_grid.setContentsMargins(0, 2, 0, 0)
        self.changes_grid.setHorizontalSpacing(components.DOWNLOAD_GAP)
        self.changes_grid.setVerticalSpacing(components.DOWNLOAD_CHANGE_GAP)
        self.changes_grid.setColumnStretch(1, 1)
        col.addWidget(self.changes_host)
        self.summary_heading = Section(_('Summary'), body)
        col.addWidget(self.summary_heading)
        self.summary = label('zenMatchSummary')
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        self.summary.setOpenExternalLinks(False)
        self.summary.linkActivated.connect(open_link)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)

        self.links_heading = Section(_('Links'), body)
        col.addWidget(self.links_heading)
        self.links = label('zenMatchLinks')
        self.links.setTextFormat(Qt.TextFormat.RichText)
        self.links.linkActivated.connect(open_link)
        self.links.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)

        col.addStretch(1)
        self.scroll.setWidget(body)
        self.show_book(None)

    def show_book(self, book) -> None:
        if book is None:
            for w in (self.series, self.title, self.authors, self.facts, self.summary, self.links):
                w.setText('')
            for w in (self.series, self.summary_heading, self.summary, self.links_heading, self.links, self.changes_heading, self.changes_host):
                w.setVisible(False)
            self.set_tags([])
            return
        from calibre.ebooks.metadata import authors_to_string

        series = ''
        if not book.is_null('series') and book.series.strip():
            series = book.series if book.series_index is None else _('Book {0} of {1}').format(fmt_series_index(book.series_index), book.series)
        self.series.setText(series)
        self.series.setVisible(bool(series))
        self.title.setText(book.title or _('Unknown'))
        self.authors.setText(authors_to_string(book.authors) if book.authors else '')
        self.facts.setText(' · '.join(facts(book)))
        self.set_tags(list(book.tags or ()))

        summary = ''
        if book.comments:
            from calibre.library.comments import comments_to_html

            summary = comments_to_html(book.comments)
        self.summary.setText(summary)
        self.summary.setVisible(bool(summary))
        self.summary_heading.setVisible(bool(summary))

        links = self.links_html(book)
        self.links.setText(links)
        self.links.setVisible(bool(links))
        self.links_heading.setVisible(bool(links))

        self.set_changes(changes(book, self.editor_of()))
        self.scroll.verticalScrollBar().setValue(0)

    def links_html(self, book) -> str:
        if not book.identifiers:
            return ''
        from calibre.ebooks.metadata.sources.identify import urls_from_identifiers

        try:
            urls = urls_from_identifiers(book.identifiers)
        except Exception:
            return ''
        return ' · '.join(f'<a href="{escape(url, True)}">{escape(name)}</a>' for name, _k, _v, url in urls)

    def set_tags(self, tags: list) -> None:
        while self.tags.count():
            item = self.tags.takeAt(0)
            w = item.widget() if item is not None else None
            if w is not None:
                # Hidden now: deleteLater waits for the event loop, and until
                # then the old widget still paints where it was.
                w.hide()
                w.deleteLater()
        for tag in tags:
            pill = Pill(tag, self.tags_host)
            # FlowLayout places its items from their size hints, and a label's
            # hint only counts the sheet's padding once it has been polished.
            pill.ensurePolished()
            self.tags.addWidget(pill)
        self.tags_host.setVisible(bool(tags))

    def set_changes(self, rows: list) -> None:
        grid = self.changes_grid
        while grid.count():
            item = grid.takeAt(0)
            w = item.widget() if item is not None else None
            if w is not None:
                # Hidden now: deleteLater waits for the event loop, and until
                # then the old widget still paints where it was.
                w.hide()
                w.deleteLater()
        chrome = colors()
        for r, (field, title, now, after) in enumerate(rows):
            name = QLabel(title, self.changes_host)
            name.setObjectName('zenMatchChangeField')
            name.setIndent(0)
            name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            value = QLabel(self.changes_host)
            value.setObjectName('zenMatchChangeValue')
            value.setProperty('zenField', field)
            value.setWordWrap(True)
            value.setTextFormat(Qt.TextFormat.RichText)
            value.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            html = escape(after)
            if now:
                html += f'<br><span style="color:{chrome.muted}; text-decoration: line-through">{escape(now)}</span>'
            value.setText(html)
            grid.addWidget(name, r, 0)
            grid.addWidget(value, r, 1)
        self.changes_heading.setVisible(bool(rows))
        self.changes_host.setVisible(bool(rows))


def open_link(url: str) -> None:
    from qt.core import QUrl

    from calibre.gui2 import open_url

    q = QUrl(url)
    if q.scheme() in {'http', 'https'}:
        open_url(q)

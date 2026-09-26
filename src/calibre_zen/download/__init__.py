#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The Download metadata dialog, laid out like the rest of the overlay.

calibre's `single_download.FullFetch` is a two-page wizard: a table of matches
beside an HTML preview, then a grid of covers. `CoverFetch` is the second page
on its own, for "Download cover". Both are kept -- every thread, every signal,
what Next, Back, OK, Cancel and View log do, the covers' context menu, the
keyboard -- and dressed from outside by wrapping methods on calibre's classes
in `single_download`:

`FullFetch.__init__` / `CoverFetch.__init__`
    One footer line: View log and Back on the left, Cancel and the primary
    button on the right. On the first page the primary button says Next.

`IdentifyWidget.__init__` / `start` / `process_results`
    A page header with the step and a sort menu; a state panel while the
    sources search, and when they find nothing or fail -- in the dialog, with
    a View log button, instead of an error box that closes the dialog -- and
    `MatchPanel` in place of the HTML preview (panel.py).

`ResultsView.__init__` / `show_results` / `show_details`
    The table as a list of cards (matches.py), and the panel told which match
    is current.

`CoversWidget.__init__` / `start` / `process_results` / `cleanup`,
`CoversView.__init__`, `CoverDelegate.paint` / `sizeHint`
    A page header over the covers, with a spinner while they arrive, and the
    grid drawn as tiles (covers.py).

Off with `CALIBRE_ZEN_DOWNLOAD=0`.
"""

from calibre_zen import features

_installed = False


def enabled() -> bool:
    return features.enabled('download')


def _safe(fn, *args, **kwargs) -> None:
    "Dress a widget; if that fails, leave calibre's working widget as it was."
    try:
        fn(*args, **kwargs)
    except Exception:
        import traceback

        traceback.print_exc()


def install() -> bool:
    "Wrap calibre's Download metadata dialogs. Safe to call twice. Needs a QApplication."
    global _installed
    if _installed or not enabled():
        return _installed
    from calibre.gui2.metadata import single_download as sd
    from calibre_zen.download import covers, matches

    def wrap(cls, name, after):
        orig = getattr(cls, name)

        def wrapper(self, *args, **kwargs):
            ans = orig(self, *args, **kwargs)
            _safe(after, self, *args, **kwargs)
            return ans

        wrapper.__name__ = name
        wrapper.__wrapped__ = orig
        setattr(cls, name, wrapper)

    wrap(sd.ResultsView, '__init__', lambda self, *a, **k: matches.dress_view(self))
    wrap(sd.ResultsView, 'show_results', lambda self, *a, **k: matches.dress_model(self))
    wrap(sd.ResultsView, 'show_details', show_details)
    wrap(sd.IdentifyWidget, '__init__', lambda self, *a, **k: dress_identify(self))
    wrap(sd.IdentifyWidget, 'start', searching_started)
    wrap(sd.CoversView, '__init__', lambda self, *a, **k: covers.dress_view(self))
    wrap(sd.CoversWidget, '__init__', lambda self, *a, **k: dress_covers(self))
    wrap(sd.CoversWidget, 'start', lambda self, *a, **k: set_covers_busy(self, True))
    wrap(sd.CoversWidget, 'process_results', lambda self, *a, **k: set_covers_busy(self, False))
    wrap(sd.CoversWidget, 'cleanup', lambda self, *a, **k: set_covers_busy(self, False))
    wrap(sd.FullFetch, '__init__', lambda self, *a, **k: dress_full(self))
    wrap(sd.FullFetch, 'book_selected', lambda self, *a, **k: set_primary(self, 1))
    wrap(sd.FullFetch, 'back_clicked', lambda self, *a, **k: set_primary(self, 0))
    wrap(sd.CoverFetch, '__init__', lambda self, *a, **k: dress_cover_only(self))

    orig_process = sd.IdentifyWidget.process_results

    def process_results(self):
        # calibre answers "nothing found" and "failed" with an error box, and
        # then closes the dialog. Both are said on the page instead, beside a
        # View log button; the dialog stays until Cancel.
        worker = self.worker
        if getattr(self, 'zen_state', None) is None or (worker.error is None and worker.results):
            ans = orig_process(self)
            _safe(results_shown, self)
            return ans
        if worker.error is not None:
            self.log.error('Download failed:\n' + worker.error)
        show_empty(self, failed=worker.error is not None)

    process_results.__wrapped__ = orig_process
    sd.IdentifyWidget.process_results = process_results
    sd.CoverDelegate.paint = covers.paint
    sd.CoverDelegate.sizeHint = covers.size_hint

    # For the render script and the tests, which fill the dialog without
    # starting a worker.
    sd.IdentifyWidget.zen_show_searching = lambda self, title=None, authors=None, identifiers=None: searching_started(self, title, authors, identifiers)
    sd.IdentifyWidget.zen_show_empty = lambda self, failed=False: show_empty(self, failed)
    sd.IdentifyWidget.zen_results_shown = results_shown
    sd.CoversWidget.zen_set_busy = set_covers_busy
    _installed = True
    return True


# The matches page {{{


def configured_sources() -> list:
    from calibre.customize.ui import metadata_plugins

    return [p.name for p in metadata_plugins(['identify']) if p.is_configured()]


def describe(title, authors) -> str:
    from calibre.ebooks.metadata import authors_to_string

    if title and authors:
        return _('“{0}” by {1}').format(title, authors_to_string(authors))
    if title:
        return f'“{title}”'
    if authors:
        return authors_to_string(authors)
    return ''


def editor_for(widget):
    "The Edit metadata dialog this was opened from, or None -- for What changes."
    win = widget.window()
    parent = win.parent() if win is not None else None
    title = getattr(parent, 'title', None)
    return parent if title is not None and hasattr(title, 'current_val') else None


def view_log(widget) -> None:
    fn = getattr(widget.window(), 'view_log', None)
    if fn is not None:
        fn()


def dress_identify(iw) -> None:
    from qt.core import QComboBox, QStackedWidget

    from calibre_zen.download import matches
    from calibre_zen.download.chrome import PageHeader, StatePanel
    from calibre_zen.download.panel import MatchPanel
    from calibre_zen.theme.tokens import components

    iw.setObjectName('zenDownloadMatches')
    lay = iw.l
    pad = components.DOWNLOAD_PAD
    lay.setContentsMargins(pad, pad, pad, pad)
    lay.setSpacing(components.DOWNLOAD_SECTION_GAP)
    # calibre's two lines -- "downloading metadata from: ..." and the query --
    # are kept for the text calibre writes to them, and said by the header
    # and the state panel instead.
    iw.top.hide()
    iw.query.hide()

    header = PageHeader(_('Choose a match'), parent=iw)
    header.set_step(_('Step 1 of 2'))
    sort = QComboBox(header)
    sort.setObjectName('zenMatchSort')
    for label, _col, _order in matches.SORTS:
        sort.addItem(_(label))
    sort.setToolTip(_('Sort the matches'))
    sort.setVisible(False)
    sort.activated.connect(lambda i: matches.apply_sort(iw.results_view, i))
    header.trailing.addWidget(sort)
    lay.insertWidget(0, header)

    splitter = iw.splitter
    index = lay.indexOf(splitter)
    lay.removeWidget(splitter)
    body = QStackedWidget(iw)
    body.setObjectName('zenDownloadBody')
    state = StatePanel(body)
    state.log_button.clicked.connect(lambda: view_log(iw))
    body.addWidget(state)
    body.addWidget(splitter)
    lay.insertWidget(index, body, 100)

    panel = MatchPanel(editor_of=lambda: editor_for(iw))
    old = splitter.replaceWidget(1, panel)
    if old is not None:
        # calibre's HTML preview: kept, hidden, so its timer and the signal
        # that feeds it still have somewhere to go.
        old.setParent(iw)
        old.hide()
    iw.comments_view.wait_timer.stop()
    splitter.setHandleWidth(components.DOWNLOAD_SECTION_GAP)
    splitter.setStretchFactor(0, 3)
    splitter.setStretchFactor(1, 2)
    iw.results_view._zen_panel = panel

    iw.zen_header, iw.zen_sort, iw.zen_body, iw.zen_state, iw.zen_panel = header, sort, body, state, panel
    iw._zen_query = ''
    state.show_searching(configured_sources(), '')


def searching_started(iw, title=None, authors=None, identifiers=None) -> None:
    state = getattr(iw, 'zen_state', None)
    if state is None:
        return
    iw._zen_query = describe(title, authors)
    iw.zen_header.subtitle.setText(iw._zen_query)
    iw.zen_sort.setVisible(False)
    state.show_searching(configured_sources(), '')
    iw.zen_body.setCurrentWidget(state)


def show_empty(iw, failed: bool) -> None:
    state = getattr(iw, 'zen_state', None)
    if state is None:
        return
    state.show_empty(failed)
    iw.zen_sort.setVisible(False)
    iw.zen_body.setCurrentWidget(state)


def results_shown(iw) -> None:
    from calibre.utils.localization import ngettext

    body = getattr(iw, 'zen_body', None)
    if body is None:
        return
    model = iw.results_view.model()
    n = model.rowCount() if model is not None else 0
    body.setCurrentWidget(iw.splitter)
    iw.zen_state.spinner.stop()
    q = getattr(iw, '_zen_query', '')
    text = ngettext('{} match', '{} matches', n).format(n)
    iw.zen_header.subtitle.setText(f'{text} · {q}' if q else text)
    iw.zen_sort.setCurrentIndex(0)
    iw.zen_sort.setVisible(n > 1)
    iw.results_view.setFocus()


def show_details(view, index=None, *args) -> None:
    from qt.core import Qt

    panel = getattr(view, '_zen_panel', None)
    model = view.model()
    if panel is None or model is None or index is None:
        return
    panel.show_book(model.data(index, Qt.ItemDataRole.UserRole))


# }}}

# The covers page {{{


def dress_covers(cw) -> None:
    from calibre_zen.download.chrome import PageHeader
    from calibre_zen.theme.tokens import components

    cw.setObjectName('zenDownloadCovers')
    lay = cw.l
    pad = components.DOWNLOAD_PAD
    lay.setContentsMargins(pad, pad, pad, pad)
    lay.setVerticalSpacing(components.DOWNLOAD_SECTION_GAP)
    lay.removeWidget(cw.msg)
    # calibre writes its progress to `msg` -- "Downloading covers for...",
    # then "Found 3 covers..." -- so it is adopted as the header's subtitle
    # and goes on being written to.
    header = PageHeader(_('Choose a cover'), subtitle=cw.msg, parent=cw)
    lay.addWidget(header, 0, 0)
    # The tiles carry their own air for the ring, so the grid starts that
    # much further out and the first cover lines up with the header.
    tile = components.DOWNLOAD_TILE_PAD
    lay.setContentsMargins(pad - tile, pad, pad - tile, pad)
    header.setContentsMargins(tile, 0, tile, 0)
    cw.zen_header = header


def set_covers_busy(cw, busy: bool) -> None:
    header = getattr(cw, 'zen_header', None)
    if header is not None:
        header.set_busy(busy)


# }}}

# The dialogs {{{


def set_primary(d, page: int) -> None:
    "Next on the matches page, calibre's own OK on the covers page."
    from qt.core import QIcon, Qt

    ok = d.ok_button
    if not hasattr(d, '_zen_ok'):
        d._zen_ok = (ok.text(), ok.icon(), ok.layoutDirection())
    if page == 0:
        ok.setText(_('&Next'))
        ok.setIcon(QIcon.ic('forward.png'))
        # The arrow after the word, pointing where Next goes. A push button
        # puts its icon first in its layout direction, and nothing else.
        ok.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    else:
        text, icon, direction = d._zen_ok
        ok.setText(text)
        ok.setIcon(icon)
        ok.setLayoutDirection(direction)


def dress_full(d) -> None:
    from calibre_zen.download.chrome import dress_footer

    d.setObjectName('zenDownload')
    d.l.setContentsMargins(0, 0, 0, 0)
    d.l.setSpacing(0)
    d.prev_button.setObjectName('zenDownloadBack')
    dress_footer(d, d.h, extra_left=(d.prev_button,))
    header = getattr(d.covers_widget, 'zen_header', None)
    if header is not None:
        header.set_step(_('Step 2 of 2'))
    set_primary(d, 0)
    # The primary button stays the default even while it is disabled, so
    # Enter during a search does nothing rather than falling to Cancel --
    # and Cancel is not drawn as the primary button while Next waits.
    for button in d.bb.buttons():
        button.setAutoDefault(False)
    d.ok_button.setDefault(True)


def dress_cover_only(d) -> None:
    from calibre_zen.download.chrome import dress_footer

    d.setObjectName('zenDownload')
    d.l.setContentsMargins(0, 0, 0, 0)
    d.l.setSpacing(0)
    dress_footer(d, d.l)


# }}}

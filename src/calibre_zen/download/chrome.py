#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The pieces both pages share: a page header, a spinner, the searching and
empty states, and the footer.

Everything here is a widget laid out in code and coloured by
`19-download.qss`; the two painted parts, the match cards and the cover
tiles, are in matches.py and covers.py.
"""

from qt.core import QHBoxLayout, QLabel, QPainter, QPushButton, QSizePolicy, Qt, QVBoxLayout, QWidget

from calibre.utils.localization import ngettext
from calibre_zen.theme import rewrite
from calibre_zen.theme.tokens import components

# Chrome is two dozen blends, and the delegates paint a card at a time. Built
# once per palette: a theme change hands the application a new palette with a
# new cache key, so the next paint rebuilds from it without being told.
_chrome = None
_chrome_key = None


def colors():
    "The live Chrome, rebuilt only when the application palette changes."
    global _chrome, _chrome_key
    from calibre.gui2 import qapplication_or_fail

    key = qapplication_or_fail().palette().cacheKey()
    if _chrome is None or key != _chrome_key:
        _chrome, _chrome_key = rewrite.chrome(), key
    return _chrome


def styled(widget: QWidget, name: str) -> QWidget:
    "Name a plain container for the sheet and let the sheet paint its background."
    widget.setObjectName(name)
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    return widget


class Spinner(QWidget):
    """
    calibre's own spinning arc, at a size of our choosing.

    `SpinAnimator` is the thing calibre's cover delegate already draws while a
    source is still searching, so a spinner here and a spinner on a cover tile
    are the same mark.
    """

    def __init__(self, size: int, parent=None):
        super().__init__(parent)
        from calibre.gui2.progress_indicator import SpinAnimator

        self.setFixedSize(size, size)
        self.animator = SpinAnimator(self)
        self.animator.updated.connect(self.update)

    def start(self) -> None:
        self.animator.start()
        self.show()

    def stop(self) -> None:
        self.animator.stop()
        self.hide()

    def paintEvent(self, ev):  # noqa: N802  (matching the Qt name is the point)
        p = QPainter(self)
        draw_spinner(p, self.animator, self.rect())
        p.end()


def draw_spinner(painter, animator, rect, circle=None) -> None:
    """
    The arc on a faint full circle. The arc alone starts as a speck, and a
    speck does not read as "working"; the circle says where it will go.
    """
    from qt.core import QColor, QPen, QRectF

    chrome = colors()
    stroke = components.DOWNLOAD_SPINNER_STROKE
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = QRectF(rect).adjusted(stroke, stroke, -stroke, -stroke)
    painter.setPen(QPen(QColor(circle or chrome.track), stroke))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(r)
    animator.draw(painter, rect.adjusted(1, 1, -1, -1), QColor(chrome.muted), float(stroke))
    painter.restore()


class PageHeader(QWidget):
    """
    Which step this is, what to do in it, and one line of how it is going.

    The subtitle can be a label calibre already writes to -- the covers page's
    message is -- so it is adopted rather than copied, and calibre goes on
    setting its text.
    """

    def __init__(self, title: str, subtitle: QLabel | None = None, parent=None):
        super().__init__(parent)
        styled(self, 'zenDownloadHeader')
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(components.DOWNLOAD_GAP)

        column = QVBoxLayout()
        column.setSpacing(2)
        self.step = QLabel(self)
        self.step.setObjectName('zenDownloadStep')
        self.step.setVisible(False)
        self.title = QLabel(title, self)
        self.title.setObjectName('zenDownloadTitle')
        self.subtitle = subtitle if subtitle is not None else QLabel(self)
        self.subtitle.setParent(self)
        self.subtitle.setObjectName('zenDownloadSubtitle')
        self.subtitle.setWordWrap(True)
        self.subtitle.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        column.addWidget(self.step)
        column.addWidget(self.title)
        column.addWidget(self.subtitle)
        outer.addLayout(column, 1)

        self.spinner = Spinner(components.DOWNLOAD_SPINNER, self)
        self.spinner.hide()
        outer.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignVCenter)
        self.trailing = QHBoxLayout()
        self.trailing.setSpacing(components.DOWNLOAD_GAP)
        outer.addLayout(self.trailing)

    def set_step(self, text: str) -> None:
        self.step.setText(text)
        self.step.setVisible(bool(text))

    def set_busy(self, busy: bool) -> None:
        if busy:
            self.spinner.start()
        else:
            self.spinner.stop()


class StatePanel(QWidget):
    """
    What the matches page shows when there is no list to show: still
    searching, found nothing, or failed. One place, three faces, so the page
    never jumps between different layouts for the same job.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        styled(self, 'zenDownloadState')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(components.DOWNLOAD_PAD, components.DOWNLOAD_PAD, components.DOWNLOAD_PAD, components.DOWNLOAD_PAD)
        outer.addStretch(2)
        self.spinner = Spinner(components.DOWNLOAD_STATE_SPINNER, self)
        outer.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addSpacing(components.DOWNLOAD_GAP)
        self.title = QLabel(self)
        self.title.setObjectName('zenDownloadStateTitle')
        self.title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.body = QLabel(self)
        self.body.setObjectName('zenDownloadStateBody')
        self.body.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.body.setWordWrap(True)
        # A box layout gives an aligned item its size hint, not its height
        # for its width, so a wrapped label under an alignment flag is cut to
        # one line. It gets a fixed measure, and a height set from it.
        self.body.setFixedWidth(components.DOWNLOAD_STATE_WIDTH)
        self.body.setTextFormat(Qt.TextFormat.PlainText)
        outer.addWidget(self.title)
        outer.addWidget(self.body, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addSpacing(components.DOWNLOAD_GAP)
        self.log_button = QPushButton(_('View log'), self)
        self.log_button.setObjectName('zenDownloadStateLog')
        self.log_button.setVisible(False)
        outer.addWidget(self.log_button, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(3)
        self.kind = ''

    def set_body(self, text: str) -> None:
        self.body.ensurePolished()
        self.body.setText(text)
        self.body.setFixedHeight(self.body.heightForWidth(self.body.width()) if text else 0)

    def show_searching(self, sources: list, query: str) -> None:
        self.kind = 'searching'
        n = len(sources)
        self.title.setText(ngettext('Searching {} source…', 'Searching {} sources…', n).format(n) if n else _('Searching…'))
        lines = []
        if sources:
            lines.append(', '.join(sources))
        if query:
            lines.append(query)
        self.set_body('\n'.join(lines))
        self.log_button.setVisible(False)
        self.spinner.start()

    def show_empty(self, failed: bool) -> None:
        self.kind = 'failed' if failed else 'empty'
        self.spinner.stop()
        if failed:
            self.title.setText(_('The download did not work'))
            self.set_body(_('Something went wrong while searching. The log has the details.'))
        else:
            self.title.setText(_('No matches found'))
            self.set_body(_("Try a shorter search. The author's last name and one word from the title is often enough. The log shows what each source said."))
        self.log_button.setVisible(True)


def dress_footer(dialog, layout, extra_left=()) -> QWidget:
    """
    Put a dialog's buttons on one footer line: the log on the far left, the
    dialog's own buttons on the right with the primary one last.

    `layout` is whatever calibre put the buttons in; they are taken out of it
    and the footer is added at its end. The buttons are calibre's, with
    their connections, so nothing about what they do changes.
    """
    bb = dialog.bb
    log_button = dialog.log_button
    bb.removeButton(log_button)
    layout.removeWidget(bb)
    for w in extra_left:
        layout.removeWidget(w)
    footer = styled(QWidget(dialog), 'zenDownloadFooter')
    row = QHBoxLayout(footer)
    pad = components.DOWNLOAD_PAD
    row.setContentsMargins(pad, components.DOWNLOAD_FOOTER_PAD_Y, pad, components.DOWNLOAD_FOOTER_PAD_Y)
    row.setSpacing(components.DOWNLOAD_GAP)
    log_button.setParent(footer)
    log_button.setObjectName('zenDownloadLog')
    row.addWidget(log_button)
    for w in extra_left:
        w.setParent(footer)
        row.addWidget(w)
    row.addStretch(1)
    bb.setParent(footer)
    row.addWidget(bb)
    layout.addWidget(footer)
    from calibre_zen.theme import surfaces

    surfaces.lift(footer)
    return footer

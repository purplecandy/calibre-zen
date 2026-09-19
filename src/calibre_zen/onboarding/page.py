#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
One wizard page per layout change: a title, one line, and a recording.

`STEPS` is the whole content. Each entry is what the wizard's header says --
the page title and the one-line subtitle under it -- and the recording that
fills the page below. The first step takes the slot of calibre's finish page,
because that is the page every other page's `nextId` points at; the rest are
chained after it and the last one carries upstream's footer, the line that
says which button applies the settings. Adding a step is adding an entry.

The recording is an animated WebP or GIF under `assets/`, played by `QMovie`;
the bundled Qt decodes both. Until a step's recording exists the frame it
would fill says so, so a build without one is visibly a build without one.

Everything here is a plain widget under the app sheet. The only painting of
our own is the placeholder's dashed frame, which reads its colours from
`Chrome` for the same reason the preview's description does -- a `paintEvent`
does not go through the style.
"""

import os
from typing import NamedTuple

from qt.core import QColor, QLabel, QMovie, QPainter, QPen, QSize, QSizePolicy, Qt, QVBoxLayout, QWizardPage

from calibre.gui2.wizard import FinishPage
from calibre.utils.localization import _
from calibre_zen.theme import rewrite
from calibre_zen.theme.tokens import components

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')


class Step(NamedTuple):
    title: str  # the wizard header's title
    blurb: str  # the one line under it: what changed
    demo: str  # a file under assets/, or '' while there is none


STEPS = (
    Step(
        _('Updated menus'),
        _('A minimalist and elegant top menu: it takes less space and behaves consistently.'),
        'top-menu.gif',
    ),
    Step(
        _('Updated filters'),
        _('Filters that make it easy to see what is applied, and to toggle anything else quickly.'),
        'side-filters.gif',
    ),
)

# The first step reuses calibre's finish page id -- every other page's nextId
# points there. The rest count on from here; nothing upstream uses these ids.
FIRST_EXTRA_ID = 400


def step_id(index: int) -> int:
    return FinishPage.ID if index == 0 else FIRST_EXTRA_ID + index


def demo_path(name: str) -> str:
    """
    The recording to play for a step, or '' when there is none.

    CALIBRE_ZEN_ONBOARDING_DEMO names a file directly and plays it on the
    first step, for looking at a recording before it is put under assets/.
    """
    override = os.environ.get('CALIBRE_ZEN_ONBOARDING_DEMO', '')
    if override and name == STEPS[0].demo:
        return override if os.path.exists(override) else ''
    if not name:
        return ''
    path = os.path.join(ASSETS, name)
    return path if os.path.exists(path) else ''


class DemoPane(QLabel):
    """
    The recording, scaled to fit whatever the page gives it.

    `QMovie` renders at its own size unless told a scaled size, and a label
    does not scale a movie the way it scales a pixmap; the scale is recomputed
    on every resize from the recording's native frame, keeping its proportions.
    Frames are not cached: a ten-second screen recording is hundreds of frames
    of a full window, which decoded and kept would be gigabytes. Decoding on
    the way through is what the format is for. Playing is tied to the page
    being shown -- a movie decoding frames behind a page nobody is on is
    wasted work.
    """

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.setObjectName('zenOnboardingDemo')
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(components.ONBOARDING_DEMO_MIN_WIDTH, components.ONBOARDING_DEMO_MIN_HEIGHT)
        self.movie = None
        self.native = QSize()
        if path:
            movie = QMovie(path, b'', self)
            if movie.isValid():
                movie.jumpToFrame(0)
                self.native = movie.currentPixmap().size()
                self.movie = movie
                self.setMovie(movie)
        if self.movie is None:
            self.setText(_('Recording of the window goes here'))

    def start(self):
        if self.movie is not None:
            self.movie.start()

    def stop(self):
        if self.movie is not None:
            self.movie.stop()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if self.movie is not None and self.native.isValid():
            self.movie.setScaledSize(self.native.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio))

    def paintEvent(self, ev):
        if self.movie is not None:
            return super().paintEvent(ev)
        chrome = rewrite.chrome()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(chrome.border_strong))
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setWidthF(1.5)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        r = self.rect().adjusted(1, 1, -1, -1)
        p.drawRoundedRect(r, components.RADIUS_PANEL, components.RADIUS_PANEL)
        p.setPen(QColor(chrome.muted))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()


class StepMixin:
    """
    What every step page does, whichever base it has.

    The host page provides `layout()` -- empty, or emptied -- and a `footer`
    label. The footer is shown on the last step only: it is the line about the
    Finish button, and only the last page has one.
    """

    index: int
    step: Step
    demo: DemoPane
    footer: QLabel

    def build(self, index: int):
        self.index = index
        self.step = STEPS[index]
        self.setObjectName('zenOnboardingPage')
        layout = self.layout()
        layout.setSpacing(components.ONBOARDING_SPACING)
        self.demo = DemoPane(demo_path(self.step.demo), self)
        layout.addWidget(self.demo, 1)
        self.footer.setObjectName('zenOnboardingFooter')
        self.footer.setWordWrap(True)
        layout.addWidget(self.footer)
        self.footer.setVisible(self.is_last)
        self.apply_texts()

    @property
    def is_last(self) -> bool:
        return self.index == len(STEPS) - 1

    def apply_texts(self):
        # The form's setupUi calls retranslateUi before build() has run.
        if getattr(self, 'step', None) is None:
            return
        self.setTitle(self.step.title)
        self.setSubTitle(self.step.blurb)
        # Upstream's footer opens with a "Congratulations!" heading; ours is
        # the one line of it that tells the reader something. `%s` is filled
        # in by Wizard.set_finish_text with the Finish button's real label,
        # exactly as it was for upstream's text.
        if self.index == 0:
            self.footer.setText(_('Press the %s button to apply your settings.'))

    def nextId(self):
        return -1 if self.is_last else step_id(self.index + 1)

    def initializePage(self):
        self.demo.start()

    def cleanupPage(self):
        self.demo.stop()

    def showEvent(self, ev):
        self.demo.start()

    def hideEvent(self, ev):
        self.demo.stop()

    def commit(self):
        pass


class ZenFinishPage(StepMixin, FinishPage):
    """
    The first step, in calibre's finish page's slot.

    `FinishUI.setupUi` still runs, so `finish_text`, `demo_label` and
    `um_label` exist for the code upstream that reaches for them. The form's
    layout is emptied of all of it but `finish_text`, which is the footer:
    `Wizard.set_finish_text` writes the Finish button's real label into it,
    and when this is not the last step it is hidden here and copied to the
    page that is (see onboarding/__init__.py).
    """

    def __init__(self):
        FinishPage.__init__(self)
        layout = self.layout()
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None and w is not self.finish_text:
                w.setParent(None)
        self.footer = self.finish_text
        self.build(0)

    def retranslateUi(self, page):
        # Called by Wizard.retranslate after the library page changed the UI
        # language; the form resets every text it owns, so ours go back on.
        FinishPage.retranslateUi(self, page)
        self.apply_texts()

    def initializePage(self):
        FinishPage.initializePage(self)
        StepMixin.initializePage(self)

    def cleanupPage(self):
        StepMixin.cleanupPage(self)
        FinishPage.cleanupPage(self)

    def showEvent(self, ev):
        FinishPage.showEvent(self, ev)
        StepMixin.showEvent(self, ev)

    def hideEvent(self, ev):
        StepMixin.hideEvent(self, ev)
        FinishPage.hideEvent(self, ev)


class StepPage(StepMixin, QWizardPage):
    "Every step after the first: a plain page with the same body."

    def __init__(self, index: int):
        QWizardPage.__init__(self)
        QVBoxLayout(self)
        self.footer = QLabel(self)
        self.build(index)

    def retranslateUi(self, page):
        self.apply_texts()

    def initializePage(self):
        QWizardPage.initializePage(self)
        StepMixin.initializePage(self)

    def cleanupPage(self):
        StepMixin.cleanupPage(self)
        QWizardPage.cleanupPage(self)

    def showEvent(self, ev):
        QWizardPage.showEvent(self, ev)
        StepMixin.showEvent(self, ev)

    def hideEvent(self, ev):
        StepMixin.hideEvent(self, ev)
        QWizardPage.hideEvent(self, ev)

#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
One widget laid across calibre's status bar, holding every reading in it.

`QStatusBar` is not a layout so much as three of them -- a message area, a run
of ordinary widgets and a run of permanent ones -- and calibre fills the
permanent run from four unrelated places, in an order nobody chose. That is
why the bar cannot be made consistent by styling it: the spacing between two
buttons in it is decided by `QStatusBar::reformat`, not by us.

So the bar gets one child with one layout, and calibre's own widgets are
adopted into it: the update notice, the layout toggles, the Layout button and
the All-actions button keep their code, their preferences and their behaviour,
and only move house. `place_layout_buttons` still rebuilds that run whenever
the window changes shape, so it is wrapped and the adoption simply runs again.

The left of the bar is what you are looking at -- library, sort order, counts.
The right is what is going on without you: the content server, and the
background jobs with how far through they are. Transient messages land between
the two, which is the one thing here that is not a reading.
"""

from qt.core import QHBoxLayout, QTimer, QWidget

from calibre_zen.status.segments import CountsReading, JobsSegment, LibrarySegment, Reading, ReportSegment, ServerSegment, SortSegment
from calibre_zen.theme.tokens import components


class ZenStatusBar(QWidget):
    "Everything in the status bar, in one layout that we own."

    def __init__(self, gui, parent=None):
        super().__init__(parent)
        self.gui = gui
        self.setObjectName('zenStatusBar')

        row = QHBoxLayout(self)
        row.setContentsMargins(components.STATUS_MARGIN_X, components.STATUS_MARGIN_Y, components.STATUS_MARGIN_X, components.STATUS_MARGIN_Y)
        row.setSpacing(components.STATUS_GAP)

        self.library = LibrarySegment(gui, self)
        self.sort = SortSegment(gui, self)
        row.addWidget(self.library)
        row.addWidget(self.sort)
        row.addSpacing(components.STATUS_GROUP_GAP)

        self.counts = CountsReading(self)
        self.device = Reading('zenStatusDevice', self)
        self.message = Reading('zenStatusMessage', self)
        self.device.setVisible(False)
        self.message.setVisible(False)
        for widget in (self.counts, self.device, self.message):
            row.addWidget(widget)
        row.addStretch(1)

        # calibre's own widgets get a group of their own rather than being
        # interleaved with ours: they are a set (the layout toggles), and a set
        # reads as one thing only if nothing is inserted into the middle of it.
        self.tools = QWidget(self)
        self.tools_row = QHBoxLayout(self.tools)
        self.tools_row.setContentsMargins(0, 0, 0, 0)
        self.tools_row.setSpacing(components.STATUS_GAP)
        row.addWidget(self.tools)
        row.addSpacing(components.STATUS_GROUP_GAP)

        self.report = ReportSegment(gui, self)
        self.server = ServerSegment(gui, self)
        self.jobs = JobsSegment(gui, self)
        row.addWidget(self.report)
        row.addWidget(self.server)
        row.addWidget(self.jobs)

        self.message_timer = QTimer(self)
        self.message_timer.setSingleShot(True)
        self.message_timer.timeout.connect(self.clear_message)

        self.adopt_tools()

    # calibre's widgets {{{

    def adopt(self, widget) -> None:
        """
        Move one of calibre's status-bar widgets into our layout.

        `removeWidget` hides what it removes and does nothing at all to a
        widget the status bar does not hold, so the visibility it was given --
        by `place_layout_buttons`, or by a preference -- is read first and put
        back afterwards.
        """
        if widget is None:
            return
        shown = not widget.isHidden()
        bar = getattr(self.gui, 'status_bar', None)
        if bar is not None:
            bar.removeWidget(widget)
        self.tools_row.addWidget(widget)
        widget.setVisible(shown)

    def adopt_tools(self) -> None:
        "Re-take calibre's widgets, in our order. Safe to call any number of times."
        while self.tools_row.count():
            self.tools_row.takeAt(0)
        bar = getattr(self.gui, 'status_bar', None)
        self.adopt(getattr(bar, 'update_label', None))
        for button in getattr(self.gui, 'layout_buttons', None) or ():
            self.adopt(button)
        self.adopt(getattr(self.gui, 'layout_button', None))
        for button in getattr(self.gui, 'status_bar_extra_buttons', None) or ():
            self.adopt(button)
        # calibre's Jobs widget stays alive and keeps owning the Jobs window --
        # our segment asks it to open -- but it is not shown twice.
        jobs = getattr(self.gui, 'jobs_button', None)
        if jobs is not None and bar is not None:
            bar.removeWidget(jobs)

    # }}}

    def attach(self) -> None:
        "The window, or the library under it, has finished changing."
        import traceback

        for segment in (self.library, self.sort, self.report, self.server, self.jobs):
            try:
                segment.attach()
            except Exception:
                traceback.print_exc()

    def refresh(self) -> None:
        "Say what is true now, without re-connecting anything."
        import traceback

        for segment in (self.library, self.sort, self.report, self.server, self.jobs):
            try:
                segment.refresh()
            except Exception:
                traceback.print_exc()

    def update_state(self, library_total: int, total: int, current: int, selected: int, device: str = '') -> None:
        self.counts.update_state(library_total, total, current, selected)
        self.device.setText(device or '')
        self.device.setVisible(bool(device))

    # Transient messages {{{

    def show_message(self, msg: str, timeout: int = 0) -> None:
        """
        A message, shown beside the counts rather than instead of the bar.

        `QStatusBar` shows one by hiding every non-permanent widget it holds,
        which with one widget holding everything would blank the whole bar for
        as long as the message lasts. Routing it here is what makes taking the
        bar over survivable.
        """
        self.message_timer.stop()
        text = (msg or '').strip()
        self.message.setText(text)
        self.message.setVisible(bool(text))
        if text and timeout:
            self.message_timer.start(int(timeout))

    def clear_message(self) -> None:
        self.message_timer.stop()
        self.message.clear()
        self.message.setVisible(False)

    # }}}

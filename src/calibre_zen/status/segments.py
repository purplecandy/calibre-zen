#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The pieces the status bar is made of.

One rule, and it is the toolbar's rule: a chevron means this opens a menu, no
chevron means it does one thing, and text with neither is text. Nothing here
decides what a click *means* -- a segment opens the menu calibre already built
or triggers the control calibre already has, so the day upstream changes what
"choose a library" or "stop the server" involves, this follows instead of
drifting.

Every segment answers `attach()` (the library or the window changed under it)
and `refresh()` (say what is true now). Both have to survive being called
before the thing they report on exists: the bar is built while calibre is
still assembling itself, and a plugin that is switched off takes its action --
and therefore its segment -- with it.
"""

from qt.core import QColor, QLabel, QPainter, QSize, Qt, QToolButton

from calibre.utils.localization import ngettext
from calibre_zen.icons import registry
from calibre_zen.theme import rewrite
from calibre_zen.theme.tokens import components

# What separates two facts inside one segment. A middle dot rather than a
# comma: these are readings, not a sentence.
JOIN = ' · '


class Segment(QToolButton):
    "A status-bar item: a glyph, a short reading, and one behaviour."

    def __init__(self, gui, glyph: str = '', parent=None):
        super().__init__(parent)
        self.gui = gui
        self.setObjectName('zenStatusSegment')
        self.setAutoRaise(True)
        # A status bar must never be a tab stop: it is the furthest thing from
        # what the keyboard is for in a library window.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(components.STATUS_ICON, components.STATUS_ICON))
        self.set_glyph(glyph)

    def set_glyph(self, glyph: str, role: str = 'text') -> None:
        if not glyph:
            return
        icon = registry.glyph_icon(glyph, role)
        if icon is not None and not icon.isNull():
            self.setIcon(icon)

    def action(self, name: str):
        "One of calibre's interface actions, or None if that plugin is off."
        return (getattr(self.gui, 'iactions', None) or {}).get(name)

    def use_menu(self, name: str) -> bool:
        """
        Show the menu that already belongs to one of calibre's actions.

        The menu is not copied and not rebuilt here: it is the same QMenu the
        toolbar button opens, which is what keeps the two in step -- including
        the `aboutToShow` handlers upstream uses to fill them in.
        """
        ac = self.action(name)
        menu = None if ac is None else ac.qaction.menu()
        if menu is None:
            return False
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setMenu(menu)
        return True

    def attach(self) -> None:
        self.refresh()

    def refresh(self, *args) -> None:
        pass


class LibrarySegment(Segment):
    "Which library is open. The equivalent of the branch name in an editor."

    def __init__(self, gui, parent=None):
        super().__init__(gui, 'books', parent)

    def attach(self) -> None:
        self.setVisible(self.use_menu('Choose Library'))
        self.refresh()

    def refresh(self, *args) -> None:
        ac = self.action('Choose Library')
        name = ''
        if ac is not None:
            try:
                name = ac.library_name() or ''
            except Exception:
                # Between libraries there is a window where the view has no
                # database. A stale name for a moment beats an exception.
                return
        self.setText(name or _('Library'))
        self.setToolTip(_('Open library: {}\nClick to switch, rename or create one').format(name or '?'))


class SortSegment(Segment):
    """
    What the list is sorted by.

    Worth a segment mostly because of the cover grid, which has no column
    header to read the answer off -- in Grid mode this is the only place the
    sort order is written down.
    """

    # The direction is the glyph rather than an arrow in the text: next to the
    # segment's own chevron, a trailing arrow reads as a second one.
    GLYPH = {True: 'sort-ascending', False: 'sort-descending'}

    def __init__(self, gui, parent=None):
        super().__init__(gui, 'arrows-sort', parent)
        self.connected = False

    def attach(self) -> None:
        self.setVisible(self.use_menu('Sort By'))
        model = self.model()
        if model is not None and not self.connected:
            # The model outlives a library switch, so this is connected once
            # rather than on every attach.
            model.sorting_done.connect(self.refresh)
            self.connected = True
        self.refresh()

    def model(self):
        view = getattr(self.gui, 'library_view', None)
        return None if view is None else view.model()

    def refresh(self, *args) -> None:
        model = self.model()
        pair = None if model is None else getattr(model, 'sorted_on', None)
        if not pair:
            self.set_glyph('arrows-sort')
            self.setText(_('Unsorted'))
            return
        key, ascending = pair[0], bool(pair[1])
        name = self.field_name(key)
        self.set_glyph(self.GLYPH[ascending])
        self.setText(name)
        direction = _('ascending') if ascending else _('descending')
        self.setToolTip(_('Sorted by {0}, {1}\nClick to sort by something else').format(name, direction))

    def field_name(self, key: str) -> str:
        "The column's own display name, so it reads the way its header does."
        try:
            info = self.gui.current_db.field_metadata.get(key) or {}
        except Exception:
            return key
        return info.get('name') or key


class ServerSegment(Segment):
    """
    Whether the content server is up, and the switch for it.

    One click starts or stops it, which is precisely what the Connect/share
    menu's own entry does -- `toggle_content_server` is called, not
    reimplemented, so the confirmation calibre shows while the server winds
    down still appears.
    """

    def __init__(self, gui, parent=None):
        super().__init__(gui, 'server', parent)
        self.clicked.connect(self.toggle)

    def attach(self) -> None:
        self.setVisible(self.action('Connect Share') is not None)
        self.refresh()

    def running(self) -> bool:
        ac = self.action('Connect Share')
        return bool(ac is not None and getattr(ac, 'content_server_is_running', False))

    def port(self):
        return getattr(getattr(getattr(self.gui, 'content_server', None), 'opts', None), 'port', None)

    def refresh(self, *args) -> None:
        running = self.running()
        # Green is not decoration here. The registry keeps a green outside the
        # palette for exactly this: a reading whose whole content is on or off.
        self.set_glyph('server', 'success' if running else 'text')
        port = self.port() if running else None
        if not running:
            self.setText(_('Server off'))
            self.setToolTip(_('The content server is not running\nClick to start it'))
            return
        self.setText(_('Server') + (f' :{port}' if port else ''))
        where = _(' on port {}').format(port) if port else ''
        self.setToolTip(_('The content server is running{}\nClick to stop it').format(where))

    def toggle(self) -> None:
        ac = self.action('Connect Share')
        if ac is not None:
            ac.toggle_content_server()


class JobsSegment(Segment):
    """
    What calibre is doing in the background, and how far through it is.

    calibre's own button counts jobs and spins while any of them run; the
    percentage is in the tooltip and in the Jobs window. It is cheap to put on
    the bar -- the manager already recomputes `percent` on its own timer and
    emits `dataChanged` when it does -- and it is the difference between "a
    job is running" and "this will be a while".

    The reading is the mean across running jobs, because that is the only
    honest summary of several: the worst of them would say a two-second job
    had stalled, and the best would promise a conversion was nearly done.
    """

    def __init__(self, gui, parent=None):
        super().__init__(gui, 'progress', parent)
        self.percent = None
        self.connected = False
        self.clicked.connect(self.open_list)

    def attach(self) -> None:
        manager = getattr(self.gui, 'job_manager', None)
        if manager is not None and not self.connected:
            manager.job_added.connect(self.refresh)
            manager.job_done.connect(self.refresh)
            # The manager emits this for the running-time column on every tick
            # of its own timer, which is exactly when a percentage has moved.
            manager.dataChanged.connect(self.refresh)
            self.connected = True
        self.refresh()

    def open_list(self) -> None:
        "calibre's own button owns the Jobs window; ask it rather than the dialog."
        button = getattr(self.gui, 'jobs_button', None)
        if button is not None:
            button.toggle()

    def refresh(self, *args) -> None:
        manager = getattr(self.gui, 'job_manager', None)
        jobs = [] if manager is None else manager.unfinished_jobs()
        running = [j for j in jobs if j.run_state == j.RUNNING]
        shares = [j.percent for j in running if isinstance(j.percent, (int, float))]
        self.percent = (sum(shares) / len(shares)) if shares else None
        if not jobs:
            self.percent = None
            self.setText(_('No jobs'))
            self.setToolTip(_('Nothing is running in the background\nClick to open the Jobs window'))
        else:
            text = ngettext('{} job', '{} jobs', len(jobs)).format(len(jobs))
            if self.percent is not None:
                text += JOIN + f'{round(self.percent)}%'
            self.setText(text)
            try:
                self.setToolTip(manager.get_tooltip())
            except Exception:
                self.setToolTip(_('Click to open the Jobs window'))
        self.setProperty('zenBusy', 'yes' if jobs else '')
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()

    def paintEvent(self, a0) -> None:  # noqa: N802  (matching the Qt name is the point)
        super().paintEvent(a0)
        if self.percent is None:
            return
        # A rule along the bottom edge rather than a bar behind the text: the
        # segment has to stay readable as a label, and a fill creeping across
        # it turns the label into something that flickers between two colours.
        chrome = rewrite.chrome()
        inset = components.STATUS_PROGRESS_INSET
        thickness = components.STATUS_PROGRESS
        width = max(0, self.width() - 2 * inset)
        if width <= 0:
            return
        top = self.height() - thickness
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(inset, top, width, thickness, QColor(chrome.border))
        done = round(width * max(0.0, min(100.0, self.percent)) / 100.0)
        if done:
            painter.fillRect(inset, top, done, thickness, QColor(chrome.accent))
        painter.end()


class Reading(QLabel):
    "Text with no behaviour, and therefore nothing that looks like a button."

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.setObjectName(name)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)


class CountsReading(Reading):
    "How many books there are, and how much of that you are looking at."

    def __init__(self, parent=None):
        super().__init__('zenStatusCounts', parent)
        self.update_state(0, 0, 0, 0)

    def update_state(self, library_total: int, total: int, current: int, selected: int) -> None:
        if current != total:
            # A search is on: say what is hidden, because an empty-looking
            # library is otherwise indistinguishable from a broken one.
            base = _('{0} of {1} books').format(current, total)
        else:
            base = ngettext('{} book', '{} books', total).format(total)
        parts = [base]
        if selected > 0:
            parts.append(_('{} selected').format(selected))
        if library_total != total:
            # A Virtual library is narrowing the view; the real size is the
            # other number people want at that moment.
            parts.append(_('{} in library').format(library_total))
        self.setText(JOIN.join(parts))

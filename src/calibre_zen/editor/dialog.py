#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""A compact arrangement of calibre's existing single-book metadata editor.

The base dialog still owns loading, saving, navigation, and every field action.
This class only gives those widgets smaller, task-focused places to live.
"""

from itertools import pairwise

from qt.core import QDialogButtonBox, QGridLayout, QHBoxLayout, QIcon, QLabel, QMenu, QSize, Qt, QTimer, QToolButton, QVBoxLayout, QWidget

from calibre.gui2 import gprefs
from calibre.gui2.metadata.basic_widgets import BuddyLabel
from calibre.gui2.metadata.single import MetadataSingleDialogBase, ScrollArea
from calibre_zen.theme import surfaces
from calibre_zen.theme.tokens import components


class MetadataSingleDialogZen(MetadataSingleDialogBase):
    DETAILS = 0
    DESCRIPTION = 1
    FILES = 2
    COLUMNS = 3

    def use_two_columns_for_custom_metadata(self):
        return False

    def create_custom_metadata_widgets(self):
        # calibre builds every column's editor into its grid; the grid is then
        # traded for a grouped form holding the same widgets (columns.py). The
        # old page is kept, hidden, because it still owns the containers the
        # widgets came out of.
        super().create_custom_metadata_widgets()
        from calibre_zen.editor import columns

        old = self.custom_metadata_widgets_parent
        try:
            form = columns.build(self, self.custom_metadata_widgets)
        except Exception:
            import traceback

            traceback.print_exc()
            return
        old.hide()
        self._zen_old_columns_page = old
        self.custom_metadata_widgets_parent = form
        self.zen_columns_form = form

    def sizeHint(self):
        screen = self.screen()
        if screen is None:
            return QSize(880, 640)
        available = screen.availableSize()
        return QSize(min(880, available.width()), min(640, available.height()))

    def restore_geometry(self, prefs, name, get_legacy_saved_geometry=None):
        return super().restore_geometry(prefs, 'zen_metasingle_window_geometry')

    def save_geometry(self, prefs, name):
        return super().save_geometry(prefs, 'zen_metasingle_window_geometry')

    def do_layout(self):
        self.setObjectName('zenMetadataEditor')
        self.zen_tabs = self.central_widget
        self.zen_tabs.clear()

        details = QWidget(self)
        self.zen_tabs.addTab(details, _('&Details'))
        details_layout = QHBoxLayout(details)
        m = components.FORM_MARGIN
        details_layout.setContentsMargins(m, m, m, m)
        details_layout.setSpacing(12)

        cover_column = QWidget(details)
        cover_column.setObjectName('zenEditorCoverColumn')
        cover_column.setFixedWidth(160)
        cover_layout = QVBoxLayout(cover_column)
        cover_layout.setContentsMargins(0, 0, 0, 0)
        self.cover.setFixedSize(components.EDITOR_COVER_W, components.EDITOR_COVER_H)
        cover_layout.addWidget(self.cover)
        self._zen_details_cover_slot = cover_layout

        self.zen_cover_menu_button = QToolButton(cover_column)
        self.zen_cover_menu_button.setText(_('Change cover'))
        self.zen_cover_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.zen_cover_menu_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        cover_menu = QMenu(self.zen_cover_menu_button)
        for label, button in (
            (_('Browse'), self.cover.select_cover_button),
            (_('Download'), self.cover.download_cover_button),
            (_('Generate'), self.cover.generate_cover_button),
            (_('AI generate'), getattr(self.cover, 'ai_generate_cover_button', None)),
            (_('Trim'), self.cover.trim_cover_button),
            (_('Remove'), self.cover.remove_cover_button),
        ):
            if button is not None:
                cover_menu.addAction(label, button.click)
        generate_menu = self.cover.generate_cover_button.menu()
        if generate_menu is not None:
            cover_menu.addSeparator()
            for action in generate_menu.actions():
                cover_menu.addAction(action)
        self.zen_cover_menu_button.setMenu(cover_menu)
        cover_layout.addWidget(self.zen_cover_menu_button)

        self.zen_formats_label = QLabel(cover_column)
        self.zen_formats_label.setObjectName('zenEditorFormats')
        self.zen_formats_label.setWordWrap(True)
        self.zen_formats_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        cover_layout.addWidget(self.zen_formats_label)
        cover_layout.addStretch()
        details_layout.addWidget(cover_column)

        form_parent = QWidget(details)
        form_parent.setObjectName('zenEditorDetails')
        form_layout = QVBoxLayout(form_parent)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form = QGridLayout()
        form.setColumnStretch(1, 1)
        form_layout.addLayout(form)
        details_layout.addWidget(form_parent, 1)

        labels, trailers = [], []

        def row(number, field, trailing=None, field_layout=None):
            labels.append(BuddyLabel(field))
            form.addWidget(labels[-1], number, 0)
            if field_layout is None:
                form.addWidget(field, number, 1)
            else:
                form.addLayout(field_layout, number, 1)
            if trailing is not None:
                trailers.append(trailing)
                form.addWidget(trailing, number, 2)

        row(0, self.title, self.swap_title_author_button)
        row(1, self.authors, self.manage_authors_button)

        self.series_index.setMaximumWidth(80)
        series_layout = QHBoxLayout()
        series_layout.setContentsMargins(0, 0, 0, 0)
        series_layout.addWidget(self.series, 1)
        series_layout.addWidget(self.series_index)
        row(2, self.series, self.series_editor_button, series_layout)
        row(3, self.tags, self.tags_editor_button)

        rating_layout = QHBoxLayout()
        rating_layout.setContentsMargins(0, 0, 0, 0)
        rating_layout.addWidget(self.rating)
        rating_layout.addStretch()
        row(4, self.rating, field_layout=rating_layout)
        row(5, self.publisher, self.publisher_editor_button)

        published_layout = QHBoxLayout()
        published_layout.setContentsMargins(0, 0, 0, 0)
        published_layout.addWidget(self.pubdate)
        published_layout.addWidget(self.pubdate.clear_button)
        published_layout.addWidget(BuddyLabel(self.languages))
        published_layout.addWidget(self.languages, 1)
        row(6, self.pubdate, field_layout=published_layout)
        row(7, self.identifiers, self.paste_isbn_button)

        self.zen_sorts_toggle = QToolButton(form_parent)
        self.zen_sorts_toggle.setObjectName('zenEditorSortsToggle')
        self.zen_sorts_toggle.setText(_('Sort fields and dates'))
        self.zen_sorts_toggle.setCheckable(True)
        self.zen_sorts_toggle.setAutoRaise(True)
        self.zen_sorts_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        form.addWidget(self.zen_sorts_toggle, 8, 0, 1, 3)

        self.zen_sorts_body = QWidget(form_parent)
        self.zen_sorts_body.setObjectName('zenEditorSorts')
        sorts = QGridLayout(self.zen_sorts_body)
        sorts.setContentsMargins(0, 0, 0, 0)
        sorts.setColumnStretch(1, 1)
        self.deduce_title_sort_button.setIcon(QIcon.ic('auto_author_sort.png'))
        self.deduce_author_sort_button.setIcon(QIcon.ic('auto_author_sort.png'))
        for number, field, button in (
            (0, self.title_sort, self.deduce_title_sort_button),
            (1, self.author_sort, self.deduce_author_sort_button),
            (2, self.timestamp, self.timestamp.clear_button),
        ):
            labels.append(BuddyLabel(field))
            trailers.append(button)
            sorts.addWidget(labels[-1], number, 0)
            sorts.addWidget(field, number, 1)
            sorts.addWidget(button, number, 2)
        form.addWidget(self.zen_sorts_body, 9, 0, 1, 3)
        # The folded rows are a grid of their own, so they only line up with
        # the form above if both grids agree on the outer columns.
        for grid, column, widgets in ((form, 0, labels), (sorts, 0, labels), (form, 2, trailers), (sorts, 2, trailers)):
            grid.setColumnMinimumWidth(column, max(w.sizeHint().width() for w in widgets))
        sorts.setHorizontalSpacing(form.horizontalSpacing())
        self.zen_sorts_toggle.toggled.connect(self.set_sorts_open)
        self.set_sorts_open(False)
        form_layout.addStretch()

        description = QWidget(self)
        description_layout = QVBoxLayout(description)
        description_layout.setContentsMargins(m, m, m, m)
        description_layout.addWidget(self.comments)
        self.zen_tabs.addTab(description, _('D&escription'))

        from calibre_zen.editor import files as files_page

        self.zen_tabs.addTab(ScrollArea(files_page.build(self), self), _('Cover && &files'))
        self.zen_tabs.currentChanged.connect(lambda i: files_page.place_cover(self, i))

        custom_parent = getattr(self, 'custom_metadata_widgets_parent', None)
        if custom_parent is not None:
            count = len(self.custom_metadata_widgets)
            self.zen_tabs.addTab(ScrollArea(custom_parent, self), _('Your &columns ({0})').format(count))

        for widget in (
            self.clear_series_button,
            self.clear_ratings_button,
            self.clear_tags_button,
            self.clear_identifiers_button,
            self.publisher.clear_button,
        ):
            widget.hide()

        self._build_footer()
        self._connect_formats_summary()
        self.zen_tabs.setCurrentIndex(self.DETAILS)
        self._set_tab_order()
        self.set_custom_metadata_tab_order()

    def _build_footer(self):
        # Take the base layout's widgets before arranging them in one footer.
        while self.button_box_layout.count():
            self.button_box_layout.takeAt(0)
        for button, name in ((self.prev_button, 'zenEditorPrev'), (self.next_button, 'zenEditorNext')):
            self.button_box.removeButton(button)
            button.setParent(self)
            button.setText('')
            button.setObjectName(name)

        # The footer runs the dialog's full width on the surface colour, lifted
        # off the page by a hairline and a soft shadow the way the title bar is
        # at the top -- so the dialog loses its own margins, and each page
        # keeps FORM_MARGIN inside itself instead.
        self.l.setContentsMargins(0, components.EDITOR_TOP_GAP, 0, 0)
        self.l.setSpacing(0)
        self.button_box_layout.setContentsMargins(0, 0, 0, 0)
        footer = QWidget(self)
        footer.setObjectName('zenEditorFooter')
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(
            components.EDITOR_FOOTER_PAD_X, components.EDITOR_FOOTER_PAD_Y, components.EDITOR_FOOTER_PAD_X, components.EDITOR_FOOTER_PAD_Y
        )
        surfaces.lift(footer)
        layout.addWidget(self.prev_button)
        layout.addWidget(self.next_button)
        self.zen_position = QLabel(footer)
        self.zen_position.setObjectName('zenEditorPosition')
        layout.addWidget(self.zen_position)
        layout.addStretch()
        self.fetch_metadata_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        layout.addWidget(self.fetch_metadata_button)
        layout.addWidget(self.config_metadata_button)
        save_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if save_button is None:
            raise RuntimeError('The metadata editor has no Save button')
        save_button.setText(_('&Save'))
        layout.addWidget(self.button_box)
        self.button_box_layout.addWidget(footer)

    def _set_tab_order(self):
        fields = (
            self.title,
            self.swap_title_author_button,
            self.authors,
            self.manage_authors_button,
            self.series,
            self.series_index,
            self.series_editor_button,
            self.tags,
            self.tags_editor_button,
            self.rating,
            self.publisher,
            self.publisher_editor_button,
            self.pubdate,
            self.pubdate.clear_button,
            self.languages,
            self.identifiers,
            self.paste_isbn_button,
            self.zen_sorts_toggle,
            self.title_sort,
            self.deduce_title_sort_button,
            self.author_sort,
            self.deduce_author_sort_button,
            self.timestamp,
            self.timestamp.clear_button,
            self.prev_button,
            self.next_button,
            self.fetch_metadata_button,
            self.config_metadata_button,
            self.button_box,
        )
        for first, second in pairwise(fields):
            QWidget.setTabOrder(first, second)

    def _connect_formats_summary(self):
        # Deferred: rowsInserted fires from inside Format.__init__, before the
        # row's Python item exists, so reading it then gets a bare
        # QListWidgetItem with no ext or size.
        model = self.formats_manager.formats.model()
        for signal in (model.rowsInserted, model.rowsRemoved, model.modelReset, model.dataChanged):
            signal.connect(self.schedule_formats_summary)

    def schedule_formats_summary(self, *args):
        QTimer.singleShot(0, self.refresh_formats_summary)

    def refresh_formats_summary(self, *args):
        formats = self.formats_manager.formats
        parts = []
        for row in range(formats.count()):
            item = formats.item(row)
            if getattr(item, 'ext', None) is not None:
                parts.append(f'{item.ext.upper()} · {item.size:.1f} MB')
        self.zen_formats_label.setText(', '.join(parts) if parts else _('No book files'))

    def set_sorts_open(self, open_):
        self.zen_sorts_body.setVisible(open_)
        self.zen_sorts_toggle.setArrowType(Qt.ArrowType.DownArrow if open_ else Qt.ArrowType.RightArrow)

    def save_widget_settings(self):
        gprefs['zen_edit_metadata_sorts_open'] = self.zen_sorts_toggle.isChecked()

    def restore_widget_settings(self):
        self.zen_sorts_toggle.setChecked(bool(gprefs.get('zen_edit_metadata_sorts_open', False)))
        self.set_sorts_open(self.zen_sorts_toggle.isChecked())
        self.zen_tabs.setCurrentIndex(self.DETAILS)

    def __call__(self, id_):
        super().__call__(id_)
        self.refresh_formats_summary()

    def do_one(self, delta=0, apply_changes=True):
        super().do_one(delta=delta, apply_changes=apply_changes)
        count = len(self.id_list)
        self.zen_position.setText(_('{0} of {1}').format(self.current_row + 1, count))
        for widget in (self.zen_position, self.prev_button, self.next_button):
            widget.setVisible(count > 1)

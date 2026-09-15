#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
What the filter panel shows, one screenful at a time.

A *level* is one screen of rows: the root list of categories, the values inside
one of them, or a short list of choices lifted out of a real `QMenu`. Every
level answers the same two questions -- which rows are on it, and what happens
when one is activated -- so the panel, the list model and the delegate never
need to know which kind they are looking at.

Rows address the tag browser's model by **named path**
(`TagsModel.named_path_for_index`), never by `QModelIndex`. A recount throws
the entire node tree away and builds a new one, so an index the panel was
holding goes stale the moment a book is added, while the names stay good.
`TagsView.recount` remembers a named path across its own rebuild for exactly
that reason.

Nothing here reimplements what a row *does*. Marking a value calls
`TagsModel.toggle`, the sort and match rows call `QAction.trigger()` on the
very actions the Configure menu would have shown, and the search that results
is handed to calibre through `TagsView.tags_marked` -- the same signal the tree
emits. The one deliberate difference is that a click is never exclusive:
upstream clears every other mark unless Ctrl is held, which is right for a tree
you click through and wrong for a sheet whose whole shape says "tick what you
want". Reset, at the foot of the panel, is how you get back to nothing.

This module imports calibre, so it must not be imported before there is a
QApplication -- see `calibre_zen/filters/__init__.py`, which is why `install()`
does its importing rather than the package header.
"""

from dataclasses import dataclass, field

from qt.core import Qt

from calibre.gui2 import config, gprefs
from calibre.gui2.tag_browser.model import COUNT_ROLE, TAG_SEARCH_STATES, TagTreeItem

# Two of the five states mean "include" and two mean "exclude"; the doubled
# ones are the hierarchical 5-state variants, which say the same thing about
# the node's children as well. A mark has no more to say than that.
INCLUDED = (TAG_SEARCH_STATES['mark_plus'], TAG_SEARCH_STATES['mark_plusplus'])
EXCLUDED = (TAG_SEARCH_STATES['mark_minus'], TAG_SEARCH_STATES['mark_minusminus'])


@dataclass
class Entry:
    "One row. `kind` decides how the delegate paints it, nothing else does."

    kind: str = 'row'  # 'row' | 'header'
    label: str = ''
    value: str = ''  # the muted right-hand text
    chevron: bool = False  # there is a further level behind this row
    mark: str = ''  # '', 'check' or 'dash'
    strong: bool = False  # a category, rather than one value inside one
    path: tuple = ()  # named path of the model node, leaf first
    toggles: bool = False  # the row body marks the value instead of descending
    source: object = field(default=None, repr=False)  # the QMenu or QAction it stands for


# Sections {{{

# calibre has no notion of what a category is *about* -- the tag browser is one
# flat list in whatever order the user arranged in Preferences. The reference
# this panel is built from groups its filters by subject, and that grouping is
# most of what makes a long list scannable, so it is recovered here from the
# only signal the keys actually carry: '@' is a user category, '#' a custom
# column, 'search' the saved searches, and everything else is one of calibre's
# own fields.
#
# The user's configured order is kept *within* each section, so rearranging
# categories in Preferences still does what it says; only the grouping is ours.
# Changing that grouping is `sections()` and `section_for()`, and nothing else.

SECTION_AUTHOR = 'author'
SECTION_BOOK = 'book'
SECTION_COLUMNS = 'columns'
SECTION_YOURS = 'yours'

AUTHOR_KEYS = frozenset({'authors', 'author_sort'})


def sections() -> tuple:
    "Section id and caption, in the order they are shown."
    return (
        (SECTION_AUTHOR, _('Filter by — Author')),
        (SECTION_BOOK, _('Filter by — Book')),
        (SECTION_COLUMNS, _('Filter by — Your columns')),
        (SECTION_YOURS, _('Filter by — You')),
    )


def section_for(key: str) -> str:
    if key.startswith('@') or key == 'search':
        return SECTION_YOURS
    if key.startswith('#'):
        return SECTION_COLUMNS
    if key in AUTHOR_KEYS:
        return SECTION_AUTHOR
    return SECTION_BOOK


# }}}


# Reading the model {{{


def mark_for(state: int) -> str:
    if state in INCLUDED:
        return 'check'
    if state in EXCLUDED:
        return 'dash'
    return ''


def display_name(item) -> str:
    "What the tree would have painted for this node."
    name = item.data(Qt.ItemDataRole.DisplayRole)
    return '' if name is None else str(name)


def summarize(node) -> str:
    """
    The right-hand value on a category row: what this category is filtering by
    at the moment, in as few words as the answer allows.

    Only TAG descendants are counted. A first-letter group carries a state of
    its own, but "A-E" is a shape of the collapse setting rather than something
    the reader picked, and counting it would make this summary disagree with
    the marks actually visible one level down.
    """
    tag = node.tag
    if tag is not None:
        if tag.state in INCLUDED:
            return _('has any')
        if tag.state in EXCLUDED:
            return _('has none')

    included = excluded = 0
    first = None
    stack = list(node.children)
    while stack:
        item = stack.pop()
        stack.extend(item.children)
        child_tag = item.tag
        if item.type != TagTreeItem.TAG or child_tag is None:
            continue
        if child_tag.state in INCLUDED:
            included += 1
            if first is None:
                first = item
        elif child_tag.state in EXCLUDED:
            excluded += 1

    if not included and not excluded:
        return _('any')
    if included == 1 and not excluded:
        return display_name(first)
    if included and not excluded:
        return _('%d selected') % included
    if excluded and not included:
        return _('%d excluded') % excluded
    return _('%(in)d in, %(out)d out') % {'in': included, 'out': excluded}


def toggle(view, path: tuple) -> None:
    """
    Mark or unmark one node, and run the search that implies.

    The body of `TagsView._toggle` minus the exclusivity and the focus dance:
    the panel does not hold keyboard focus during a click, and exclusivity is
    the difference this module's docstring explains.
    """
    model = view._model
    index = model.index_for_named_path(list(path))
    if not index.isValid():
        return
    if model.toggle(index, False):
        view.tags_marked.emit(view.search_string)


# }}}


# Levels {{{


class Level:
    "One screenful. An empty `title` means the root, which shows no nav bar."

    title = ''

    def __init__(self, view):
        self.view = view

    @property
    def model(self):
        return self.view._model

    def entries(self) -> list:
        raise NotImplementedError

    def activate(self, entry: Entry, on_chevron: bool):
        "Do the row's work. Returns a Level to descend into, or None to stay."
        return


class RootLevel(Level):
    "Every category, grouped, and how each one is filtering right now."

    def entries(self) -> list:
        out = list(menu_rows(self.view))

        grouped = {}
        for node in self.model.root_item.children:
            grouped.setdefault(section_for(node.category_key), []).append(node)

        for section, caption in sections():
            nodes = grouped.get(section)
            if not nodes:
                continue
            out.append(Entry(kind='header', label=caption))
            for node in nodes:
                out.append(
                    Entry(
                        label=display_name(node),
                        value=summarize(node),
                        chevron=True,
                        strong=True,
                        path=(node.name_id,),
                    )
                )
        return out

    def activate(self, entry: Entry, on_chevron: bool):
        if entry.source is not None:
            return MenuLevel(self.view, entry.label, entry.source)
        return NodeLevel(self.view, entry.path, entry.label)


class NodeLevel(Level):
    """
    What is inside one category: its values, or the groups the collapse
    setting has arranged them into.

    A value with children of its own -- a hierarchical tag, a sub-category of a
    user category -- can be both marked and descended into, so its body toggles
    and its chevron descends. Two targets in one row is a real cost; the
    alternative is making a hierarchy's parent unmarkable, which upstream does
    not do and which would quietly drop searches people rely on.
    """

    def __init__(self, view, path: tuple, title: str):
        super().__init__(view)
        self.path = path
        self.title = title

    def entries(self) -> list:
        model = self.model
        parent = model.index_for_named_path(list(self.path))
        if not parent.isValid():
            return []
        node = model.get_node(parent)
        out = []

        # Clicking "Tags" in the tree searches for books that have any tag at
        # all. Here a click on that row descends instead, so that search gets a
        # row of its own rather than quietly disappearing.
        if node.type == TagTreeItem.CATEGORY and node.tag is not None and node.tag.is_searchable:
            out.append(
                Entry(
                    label=_('Has a value'),
                    mark=mark_for(node.tag.state),
                    toggles=True,
                    path=self.path,
                )
            )

        show_counts = bool(gprefs['tag_browser_show_counts'])
        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)
            item = model.get_node(index)
            tag = item.tag
            has_children = bool(item.children)
            count = index.data(COUNT_ROLE)
            out.append(
                Entry(
                    label=display_name(item),
                    value='' if not show_counts or count is None else str(count),
                    chevron=has_children,
                    mark='' if tag is None else mark_for(tag.state),
                    # A group heading -- a first letter, a sub-category -- is
                    # set in the same weight a category is, because that is
                    # what it is: a way in, not a value.
                    strong=item.type == TagTreeItem.CATEGORY,
                    path=(item.name_id, *self.path),
                    toggles=tag is not None and tag.is_searchable,
                )
            )
        return out

    def activate(self, entry: Entry, on_chevron: bool):
        if entry.chevron and (on_chevron or not entry.toggles):
            return NodeLevel(self.view, entry.path, entry.label)
        if entry.toggles:
            toggle(self.view, entry.path)
        return None


class MenuLevel(Level):
    """
    A level built out of a real `QMenu`'s actions -- the sort order and the
    multiple-selection match type, both of which already exist as exclusive
    `QActionGroup`s on the Configure menu.

    Nothing is named here: the rows are whatever `menu.actions()` holds, and a
    tap calls `trigger()` on the action itself, so calibre's own handler runs
    and the day upstream adds a fourth sort order this level shows it for free.
    """

    def __init__(self, view, title: str, menu):
        super().__init__(view)
        self.title = title
        self.menu = menu

    def entries(self) -> list:
        return [
            Entry(label=plain(action.text()), mark='check' if action.isChecked() else '', toggles=True, source=action)
            for action in self.menu.actions()
            if not action.isSeparator()
        ]

    def activate(self, entry: Entry, on_chevron: bool):
        action = entry.source
        if action is not None and not action.isChecked():
            action.trigger()
            # TagsView.match_changed() only records the preference; the search
            # whose meaning that preference changes has to be re-run by
            # whoever changed it. sort_changed() recounts on its own, and a
            # second emit of an unchanged search string is a no-op.
            view = self.view
            view.tags_marked.emit(view.search_string)


# }}}


# The two menu-backed rows at the top {{{


def plain(text: str) -> str:
    "A row has no keyboard mnemonic, so it has no business showing '&'."
    return text.replace('&', '')


def menu_rows(view) -> list:
    """
    "Sort by" and "Match", read off the Configure menu.

    They are here rather than left in the Configure button because they are the
    two settings that change what the list below them *means*, and the
    reference puts exactly that kind of control at the top of the sheet. The
    button keeps everything else it has.
    """
    alter_tb = getattr(view, 'alter_tb', None)
    if alter_tb is None:
        return []
    out = []
    menu = sort_menu(alter_tb)
    if menu is not None:
        out.append(Entry(label=_('Sort by'), value=checked_text(menu), chevron=True, strong=True, source=menu))
    menu = getattr(alter_tb, 'match_menu', None)
    if menu is not None:
        out.append(Entry(label=_('Match'), value=match_word(), chevron=True, strong=True, source=menu))
    return out


def checked_text(menu) -> str:
    checked = next((a for a in menu.actions() if a.isChecked()), None)
    return '' if checked is None else plain(checked.text())


def match_word() -> str:
    """
    One word for the match type.

    calibre's own wording for these two is a whole sentence -- "Match any of
    the items" -- which is right in a menu and four times too wide for the
    value column of a row already labelled "Match". The preference underneath
    is literally 'any' or 'all' (`db.MATCH_TYPE`), which is the word the row
    wants; the sentences stay on the level it opens. A third match type
    upstream has not thought of yet shows its raw key rather than nothing.
    """
    words = {'any': _('any'), 'all': _('all')}
    value = config['match_tags_type']
    return words.get(value, value)


def sort_menu(alter_tb):
    try:
        return alter_tb.m.named_action('sort_menu').menu()
    except KeyError, AttributeError:
        return None


# }}}

#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Tabler Icons (MIT) -- https://github.com/tabler/tabler-icons

A pack is a name, a directory of monochrome SVGs, and a map from the icon names
calibre asks for to the glyphs in that directory. Nothing else; adding a second
icon set means adding a sibling module, not touching any of this.

Only the mapped glyphs are vendored, under assets/tabler/. An unmapped name
falls through to calibre's own icon, so a partial map is a working map -- which
is what lets this be migrated a screen at a time. `icons/vendor.py` copies a
newly mapped glyph in from a downloaded Tabler release.

Roles are palette roles, not colours: an icon coloured `text` is legible in both
themes and follows a user's custom palette for free.
"""

from calibre_zen.icons.pack import Pack

# Carried here as well as in assets/tabler/LICENSE because a build copies the
# glyphs and the Python, not arbitrary files, and MIT asks for the notice to
# travel with them.
LICENSE = '''MIT License

Copyright (c) 2020-2026 Pawel Kuna

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.'''

# calibre icon name -> tabler glyph, or (glyph, role). Role defaults to 'text'.
MAP = {
    # Main toolbar, in the order the default macOS layout puts them {{{
    'add_book.png': 'library-plus',
    'edit_input.png': 'edit',
    'convert.png': 'transform',
    'view.png': 'book-2',
    'lt.png': 'books',
    # calibre's donate button is a red heart and has been for twenty years.
    # Monochrome everywhere else, but not here.
    'donate.png': ('heart', 'danger'),
    'news.png': 'news',
    'store.png': 'shopping-bag',
    'save.png': 'download',
    'connect_share.png': 'share',
    'remove_books.png': 'trash',
    'edit_book.png': 'file-pencil',
    # }}}
    # Tag browser categories {{{
    'user_profile.png': 'user',
    'series.png': 'list-numbers',
    'book.png': 'files',
    'publisher.png': 'building-store',
    'rating.png': 'star',
    'tags.png': 'tags',
    'column.png': 'columns',
    'tb_folder.png': 'folder',
    'identifiers.png': 'id',
    'catalog.png': 'list-search',
    'languages.png': 'language',
    # }}}
    # The chrome around the book list {{{
    'search.png': 'search',
    # The two glyphs inside the search field: full text search, and the
    # gear that opens the advanced search builder.
    'fts.png': 'file-search',
    'gear.png': 'adjustments',
    'highlight_only_on.png': 'highlight',
    'highlight_only_off.png': 'highlight-off',
    'vl.png': 'filter',
    'folder_saved_search.png': 'folder-search',
    'search_add_saved.png': 'bookmark-plus',
    'search_copy_saved.png': 'copy',
    'config.png': 'settings',
    'layout.png': 'layout-columns',
    'bookshelf.png': 'layout-board',
    'sort.png': 'arrows-sort',
    'jobs.png': 'progress',
    'exec.png': 'player-play',
    'dialog_error.png': ('alert-circle', 'danger'),
    'window-close.png': 'x',
    'arrow-down.png': 'chevron-down',
    'minus.png': 'minus',
    'notes.png': 'notes',
    'external-link.png': 'external-link',
    'highlight.png': 'highlight',
    # }}}
}

pack = Pack('tabler', 'Tabler Icons', MAP)

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
    # lt.png and library.png are the application's own icon (imgsrc/calibre.svg),
    # and on Windows the main window's title bar and taskbar entry: not mapped,
    # so they fall through to the fork's artwork rather than a generic glyph.
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
    # Dialogs, and the small change every menu is made of {{{
    'ok.png': 'check',
    'plus.png': 'plus',
    'list_remove.png': 'square-minus',
    'close.png': 'x',
    'clear_left.png': 'circle-x',
    'modified.png': 'pencil',
    'dictionary.png': 'vocabulary',
    'bullhorn.png': 'speakerphone',
    'subset-fonts.png': 'typography-off',
    # Status marks. `point` is vendored from Tabler's filled set rather than the
    # outline one: a hollow ring does not read as a status light at 16px. The
    # colour is the message, so these are the roles doing the work, not the
    # glyph -- both are the same dot.
    'dot_green.png': ('point', 'success'),
    'dot_red.png': ('point', 'danger'),
    # The subfolders are mostly brand marks and file-format badges, which stay
    # calibre's: a Kindle is not a line drawing of a Kindle and an EPUB badge is
    # not an icon. These are the ones that are neither -- generic things that
    # happen to live in those folders and turn up in ordinary menus.
    'devices/folder.png': 'folder',
    'devices/tablet.png': 'device-tablet',
    'mimetypes/dir.png': 'folder',
    'mimetypes/zip.png': 'file-zip',
    'mimetypes/unknown.png': 'file',
    'plugins/plugin_updater.png': 'puzzle',
    # The tag browser's four search states appear together in one list, so they
    # have to be four distinct glyphs rather than a plus and a bigger plus.
    'plusplus.png': 'circle-plus',
    'minusminus.png': 'circle-minus',
    'v-ellipsis.png': 'dots-vertical',
    'h-ellipsis.png': 'dots',
    'context_menu.png': 'menu-2',
    'help.png': 'help',
    'dialog_information.png': 'info-circle',
    'dialog_question.png': 'help-circle',
    'dialog_warning.png': ('alert-triangle', 'danger'),
    'ai.png': 'sparkles',
    'back.png': 'arrow-left',
    'forward.png': 'arrow-right',
    'next.png': 'chevron-right',
    'previous.png': 'chevron-left',
    'arrow-up.png': 'chevron-up',
    # }}}
    # The library and what you do to it {{{
    'generic-library.png': 'library',
    'books_in_series.png': 'books',
    'copy-to-library.png': 'copy',
    'merge_books.png': 'arrow-merge',
    'unpack-book.png': 'package',
    'marked.png': 'flag',
    'bookmarks.png': 'bookmarks',
    'filter.png': 'filter',
    'search_delete_saved.png': 'bookmark-minus',
    'trash.png': 'trash',
    'auto_author_sort.png': 'sort-a-z',
    'random.png': 'arrows-shuffle',
    'similar.png': 'affiliate',
    'metadata.png': 'file-description',
    'download-metadata.png': 'cloud-download',
    'swap.png': 'arrows-exchange',
    'diff.png': 'file-diff',
    'merge.png': 'git-merge',
    'split.png': 'arrows-split',
    # }}}
    # The editor: formatting, and the tools around it {{{
    'format-text-bold.png': 'bold',
    'format-text-italic.png': 'italic',
    'format-text-underline.png': 'underline',
    'format-text-strikethrough.png': 'strikethrough',
    'format-text-subscript.png': 'subscript',
    'format-text-superscript.png': 'superscript',
    'format-text-heading.png': 'heading',
    'format-text-color.png': 'text-color',
    'format-fill-color.png': 'highlight',
    'format-text-hr.png': 'separator-horizontal',
    'format-justify-left.png': 'align-left',
    'format-justify-center.png': 'align-center',
    'format-justify-right.png': 'align-right',
    'format-justify-fill.png': 'align-justified',
    'format-indent-less.png': 'indent-decrease',
    'format-indent-more.png': 'indent-increase',
    'format-list-ordered.png': 'list-numbers',
    'format-list-unordered.png': 'list',
    'insert-link.png': 'link',
    'edit-copy.png': 'copy',
    'edit-cut.png': 'cut',
    'edit-paste.png': 'clipboard',
    'edit-undo.png': 'arrow-back-up',
    'edit-redo.png': 'arrow-forward-up',
    'edit-clear.png': 'eraser',
    'edit-select-all.png': 'select-all',
    'spell-check.png': 'abc',
    'smarten-punctuation.png': 'quote',
    'font.png': 'typography',
    'font_size_larger.png': 'text-increase',
    'font_size_smaller.png': 'text-decrease',
    'character-set.png': 'letter-case',
    'code.png': 'code',
    'html-fix.png': 'html',
    'toc.png': 'list-tree',
    'chapters.png': 'list-details',
    'page.png': 'file',
    'reference.png': 'bookmark',
    'scene-divider.png': 'separator',
    'snippets.png': 'braces',
    'trim.png': 'crop',
    'resize.png': 'resize',
    'width.png': 'ruler',
    'compress-image.png': 'arrows-minimize',
    'view-image.png': 'photo',
    'embed-fonts.png': 'file-typography',
    'beautify.png': 'wand',
    'heuristics.png': 'bulb',
    'polish.png': 'stars',
    'document-new.png': 'file-plus',
    'document-import.png': 'file-import',
    'document-encrypt.png': 'lock-square',
    'document-split.png': 'scissors',
    'document_open.png': 'folder-open',
    'print.png': 'printer',
    'mail.png': 'mail',
    'send.png': 'send',
    # }}}
    # Devices, the content server, and the viewer {{{
    'eject.png': 'player-eject',
    'sync.png': 'refresh',
    'sync-right.png': 'device-mobile-share',
    'network-server.png': 'server',
    'reader.png': 'device-tablet',
    'viewer.png': 'eye',
    'sd.png': 'device-sd-card',
    'restart.png': 'rotate-clockwise',
    'view-refresh.png': 'refresh',
    'auto-reload.png': 'refresh-dot',
    'rotate-right.png': 'rotate',
    'scroll.png': 'mouse',
    'auto-scroll.png': 'chevrons-down',
    'cover_flow.png': 'carousel-horizontal',
    'grid.png': 'layout-grid',
    'connect_share_on.png': 'share',
    'drm-locked.png': 'lock',
    'drm-unlocked.png': 'lock-open',
    'debug.png': 'bug',
    # }}}
    # Preferences {{{
    'lookfeel.png': 'brush',
    'keyboard-prefs.png': 'keyboard',
    'template_funcs.png': 'template',
    'tweaks.png': 'adjustments-alt',
    'tweak.png': 'tool',
    'plugins.png': 'puzzle',
    'plugboard.png': 'plug',
    'reports.png': 'chart-bar',
    'scheduler.png': 'calendar-time',
    'quickview.png': 'layout-bottombar',
    'wizard.png': 'wand',
    'icon_choose.png': 'icons',
    # }}}
}

# Glyphs the overlay asks for by name, with no calibre icon name behind them:
# the Preferences menu's category submenus, which upstream draws as five copies
# of one gear, and the three states of the theme switcher. Listed here so they
# are vendored like everything else -- a glyph that is not on disk fails
# silently and leaves whatever calibre drew.
EXTRA = (
    'layout',
    'transform',
    'transfer',
    'share',
    'tool',
    'sun',
    'moon',
    'brightness-half',
    'device-desktop',
    'square',
    'square-check',
    # The status bar's readings. Most of these are already required by a
    # mapping above; naming them here is what makes `missing()` notice if the
    # mapping that happens to pull one in is ever changed.
    'books',
    'arrows-sort',
    'sort-ascending',
    'sort-descending',
    'server',
    'progress',
    # The centre strip's preview toggle (centre/layout.py): open while the
    # preview is up, struck through while it is not.
    'eye',
    'eye-off',
)

pack = Pack('tabler', 'Tabler Icons', MAP, EXTRA)

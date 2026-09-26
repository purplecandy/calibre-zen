#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The settings folder: what in it is Look & feel, and the few things done to it.

calibre keeps its settings as a folder of files, and two parts of the overlay
act on that folder as a whole: the welcome wizard's import
(onboarding/importer.py) and the Look & feel page's reset (lookfeel.py). What
they share is here, so preferences code never imports the wizard's:

* **What is Look & feel** (`look_and_feel`, `look_and_feel_file`). Everything
  calibre's Look & feel preference pages store -- fonts, icon sizes, the
  palette, the cover grid's sizes, the Edit metadata layout, the tag browser's
  display -- plus calibre's colour palettes and a user icon theme. The rules
  are key names and key prefixes per file. `test_onboarding` reads the
  preference pages' own source, so a setting upstream adds there fails the
  test until it is sorted. The language is not Look & feel here: it is a
  person's, not a look's.
* **`backup`**: a copy of the folder beside it, before anything replaces it.
* **`refresh_loaded`**: every settings object this process has loaded,
  re-read. Needed after any write underneath them, because each writes its
  whole dict back on its next change.
* **`reset_look_and_feel`**: the Look & feel settings taken out of the stored
  files, so the defaults -- this app's -- apply again.
"""

import os
import re

# Never copied: regenerated caches, and locks that belong to a running calibre.
SKIP_DIRS = frozenset({'caches'})
SKIP_SUFFIXES = ('.lock',)

# Look & feel, by file. A key is left behind when it is named, or when it
# starts with one of the prefixes -- calibre groups each preference page's
# settings under one, so a new setting on a page is caught by its prefix.
LOOK_AND_FEEL_PREFIXES = {
    'gui.json': (
        'bd_',
        'book_details_',
        'bookshelf_',
        'cb_',
        'cover_browser_',
        'cover_grid_',
        'edit_metadata_',
        'emblem_',
        'qv_',
        'show_sb_',
        'tag_browser_',
        'tags_browser_',
    ),
}
LOOK_AND_FEEL_KEYS = {
    'gui.json': frozenset({
        # Main interface
        'book_list_extra_row_spacing',
        'book_list_tooltips',
        'booklist_grid',
        'books_autoscroll_time',
        'color_palette',
        'cover_corner_radius',
        'cover_corner_radius_unit',
        'dark_palette_name',
        'dark_palettes',
        'default_author_link',
        'dnd_merge',
        'font',
        'font_stretch',
        'gui_layout',
        'id_link_rules',
        'last_used_language',
        'light_palette_name',
        'light_palettes',
        'row_numbers_in_book_list',
        'show_layout_buttons',
        'show_splash_screen',
        'toolbar_icon_size',
        'toolbar_text',
        'ui_style',
        'wrap_toolbar_text',
        # Tag browser
        'categories_using_hierarchy',
        'icons_on_right_in_tag_browser',
        'show_links_in_tag_browser',
        'show_notes_in_tag_browser',
        'tb_search_order',
    }),
    'gui.py.json': frozenset({
        'cover_flow_queue_length',
        'disable_animations',
        'disable_tray_notification',
        'separate_cover_flow',
        'show_avg_rating',
        'systray_icon',
        'use_roman_numerals_for_series_number',
    }),
}
# A user icon theme is compiled into the config directory as icons-<which>.rcc,
# and single icons can be overridden under resources/images/.
LOOK_AND_FEEL_FILES = ('resources/images/',)
LOOK_AND_FEEL_FILE_PATTERN = r'^icons(-[a-z]+)?\.rcc$'


def look_and_feel(rel: str, key: str) -> bool:
    "Whether `key` in the settings file `rel` is look & feel, and so stays behind."
    prefixes = LOOK_AND_FEEL_PREFIXES.get(rel, ())
    return key in LOOK_AND_FEEL_KEYS.get(rel, ()) or bool(prefixes and key.startswith(prefixes))


def look_and_feel_file(rel: str) -> bool:
    rel = rel.replace(os.sep, '/')
    return rel.startswith(LOOK_AND_FEEL_FILES) or bool(re.match(LOOK_AND_FEEL_FILE_PATTERN, rel))


def refresh_loaded(config_dir: str) -> int:
    """
    Re-read every settings object in this process that reads from `config_dir`.

    They are found rather than listed: calibre makes them at import time all
    over the tree, and the one that was missed would be the one that writes
    its stale dict back over the import the next time it is changed.
    """
    import gc

    from calibre.utils.config import DynamicConfig, XMLConfig
    from calibre.utils.config_base import ConfigProxy

    def ours(path) -> bool:
        return isinstance(path, str) and os.path.abspath(path).startswith(os.path.abspath(config_dir) + os.sep)

    count = 0
    for obj in gc.get_objects():
        try:
            if isinstance(obj, (XMLConfig, DynamicConfig)):
                if ours(getattr(obj, 'file_path', None)):
                    obj.refresh()
                    count += 1
            elif isinstance(obj, ConfigProxy):
                obj.refresh()
                count += 1
        except Exception:
            import traceback

            traceback.print_exc()

    from calibre.utils import config_base

    config_base.tweaks.clear()
    config_base.tweaks.update(config_base.read_tweaks())
    return count


def backup(config_dir: str | None = None) -> str:
    """
    Copy the current settings to a folder beside them, and return its path.

    `<config>-backup-<date>-<time>`, caches and locks left out. Restoring is
    putting its contents back, by hand, with the app closed.
    """
    import shutil
    import time

    from calibre.constants import config_dir as current

    config_dir = config_dir or current
    stamp = time.strftime('%Y-%m-%d-%H%M%S')
    target = f'{config_dir.rstrip(os.sep)}-backup-{stamp}'
    n = 1
    while os.path.exists(target):
        n += 1
        target = f'{config_dir.rstrip(os.sep)}-backup-{stamp}-{n}'

    def ignore(folder, names):
        top = os.path.abspath(folder) == os.path.abspath(config_dir)
        return [n for n in names if (top and n in SKIP_DIRS) or n.endswith(SKIP_SUFFIXES)]

    shutil.copytree(config_dir, target, ignore=ignore, symlinks=True)
    return target


def _commit_json(path: str, data: dict) -> None:
    import json

    from calibre.utils.config_base import commit_data

    commit_data(path, json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8'))


def reset_look_and_feel(config_dir: str | None = None) -> list:
    """
    Take every Look & feel setting out of the settings folder. Returns what was
    removed, as `file: key` for settings and the path for files.

    Only the stored values go. A key that is not stored is already on its
    default, and every other setting in the same file is left exactly as it
    was. Loaded settings are re-read afterwards, so nothing running writes the
    old values back. What is on screen keeps the old look until a restart.
    """
    import json
    import shutil

    from calibre.constants import config_dir as current

    config_dir = config_dir or current
    removed = []
    for rel in sorted(set(LOOK_AND_FEEL_KEYS) | set(LOOK_AND_FEEL_PREFIXES)):
        path = os.path.join(config_dir, rel)
        try:
            with open(path, 'rb') as f:
                data = json.loads(f.read())
        except OSError, ValueError:
            continue
        if not isinstance(data, dict):
            continue
        gone = [k for k in data if look_and_feel(rel, k)]
        if gone:
            for k in gone:
                del data[k]
            _commit_json(path, data)
            removed.extend(f'{rel}: {k}' for k in sorted(gone))
    try:
        names = os.listdir(config_dir)
    except OSError:
        names = []
    for name in sorted(names):
        if look_and_feel_file(name):
            os.remove(os.path.join(config_dir, name))
            removed.append(name)
    for rel in LOOK_AND_FEEL_FILES:
        path = os.path.join(config_dir, *rel.strip('/').split('/'))
        if os.path.isdir(path):
            shutil.rmtree(path)
            removed.append(rel)
    refresh_loaded(config_dir)
    return removed

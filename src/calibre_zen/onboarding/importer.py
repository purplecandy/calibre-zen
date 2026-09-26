#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Bring a calibre install's settings into calibre-zen.

calibre-zen keeps its own config directory (`__appname__` is the fork's), so a
person who has used calibre for years starts from defaults: no plugins, no
toolbar, no library. calibre's settings are a directory of files, and nearly
all of them mean the same thing here, so importing them is a copy with four
corrections:

* **JSON files that both sides have are merged**, calibre's keys over ours.
  By the time the wizard runs this process has already written a few keys of
  its own -- the wizard's language, the overlay's `zen_*` choices -- and a
  plain copy would drop them.
* **Paths into calibre's directory are pointed at ours.** calibre stores
  plugins by absolute path (`customize.py.json`), and a path left pointing at
  the other app's folder would share its files after all.
* **`installation_uuid` is left behind** (`DROP_KEYS`). It is what a paired
  device and the content server know an install by, and two apps answering
  to one id is a device that talks to whichever it reached first.
* **Look & feel is left behind** (`look_and_feel`). Everything calibre's Look
  & feel preference pages store -- fonts, icon sizes, the palette, the cover
  grid's sizes, the Edit metadata layout, the tag browser's display -- plus
  calibre's colour palettes and a user icon theme. Those are exactly what this
  app has its own answers for, and calibre's would sit on top of them: a
  toolbar at calibre's icon size, or calibre's Edit metadata layout hiding the
  compact editor. The one exception is the language, which is a person's, not
  a look's. `test_onboarding` checks the rules against the preference pages'
  own source, so a setting upstream adds there is not copied by accident.

**What comes over can be chosen** (`GROUPS`, `plugin_entries`). A full import
is every group and every plugin. The Advanced page picks: a group is a set
of files, plus for `gui.json` a set of keys; a plugin is an entry in the
`plugins/` folder, a zip or a folder or a settings file, taken as it is.
Look & feel is never a group, so no choice brings it.

After a copy, the overlay's own additions to calibre's defaults are merged
into what came across -- today the Preferences button on the toolbar
(`hooks.merge_toolbar_additions`). A person's arrangement stays as it was;
only what is missing is added.

`backup` copies the current settings aside before anything replaces them,
and `reset` puts them back to the app's defaults. Neither touches calibre's
folder: the source of an import is only ever read.

The files are written underneath settings objects this process has already
loaded, and those write their whole dict back on the next change. So every
loaded config object that reads from our directory is re-read afterwards
(`refresh_loaded`), and the plugins are initialised again, before anything
gets the chance to write a stale copy over the import.

`CALIBRE_ZEN_IMPORT_FROM=<dir>` imports from another directory, for tests and
for a calibre whose settings live somewhere unusual; `=0` hides the offer.
"""

import json
import os
from typing import NamedTuple

ENV_VAR = 'CALIBRE_ZEN_IMPORT_FROM'
OFF_VALUES = frozenset({'0', 'false', 'no', 'off'})

# Never copied: regenerated caches, and locks that belong to a running calibre.
SKIP_DIRS = frozenset({'caches'})
SKIP_SUFFIXES = ('.lock',)
# Keys left behind: `installation_uuid` names this install rather than
# describing a preference.
DROP_KEYS = {'global.py.json': frozenset({'installation_uuid'})}
# The files that say calibre has actually been used, rather than just started.
MARKERS = ('global.py.json', 'gui.json')

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


class Group(NamedTuple):
    key: str
    title: str  # untranslated; the page translates it
    note: str


# The settings groups the Advanced page offers, in its order. Everything that
# matches no group's files or keys is `general`.
GROUPS = (
    Group('general', 'General', 'Language, formats, adding books, saved searches and tweaks'),
    Group('toolbar', 'Toolbar and menus', 'Which buttons and menus you arranged, and where'),
    Group('shortcuts', 'Keyboard shortcuts', ''),
    Group('conversion', 'Conversion', 'Your settings for each format'),
    Group('devices', 'Devices and email', 'Readers, phones and the email you send books from'),
    Group('sharing', 'Sharing over the net', 'The content server and its users'),
    Group('metadata', 'Metadata download', 'Which sources to ask, and how'),
    Group('viewer', 'Viewer and book editor', ''),
    Group('windows', 'Window sizes and positions', ''),
)
GROUP_KEYS = tuple(g.key for g in GROUPS)
PLUGINS = 'plugins'

# Files, by the start of their path inside the settings folder.
GROUP_FILES = (
    ('shortcuts/', 'shortcuts'),
    ('conversion/', 'conversion'),
    ('device_drivers_', 'devices'),
    ('mtp_', 'devices'),
    ('smtp.', 'devices'),
    ('server-', 'sharing'),
    ('metadata_sources/', 'metadata'),
    ('metadata-sources', 'metadata'),
    ('viewer', 'viewer'),
    ('tweak_book', 'viewer'),
    ('toc-editor', 'viewer'),
    ('plugins/', PLUGINS),
)


def group_of_file(rel: str) -> str:
    rel = rel.replace(os.sep, '/')
    return next((group for start, group in GROUP_FILES if rel.startswith(start)), 'general')


def group_of_key(rel: str, key: str) -> str:
    """
    The group a key belongs to. Keys are sorted in two files: `gui.json`,
    where the toolbar and window sizes live among everything else, and
    `customize.py.json`, whose `plugins` map is the installed plugins.
    """
    if rel == 'customize.py.json':
        return PLUGINS if key == 'plugins' else 'general'
    if rel != 'gui.json':
        return group_of_file(rel)
    if key.startswith('action-layout-'):
        return 'toolbar'
    if 'geometry' in key or 'splitter' in key or key.endswith(('_state', ' state', 'column layout', 'column layout3')):
        return 'windows'
    return 'general'


def plugin_entries(src: str) -> list:
    "What is in the settings folder's `plugins/`, by name: zips, folders and settings files."
    try:
        return sorted(os.listdir(os.path.join(src, PLUGINS)), key=str.lower)
    except OSError:
        return []


def look_and_feel(rel: str, key: str) -> bool:
    "Whether `key` in the settings file `rel` is look & feel, and so stays behind."
    prefixes = LOOK_AND_FEEL_PREFIXES.get(rel, ())
    return key in LOOK_AND_FEEL_KEYS.get(rel, ()) or bool(prefixes and key.startswith(prefixes))


def look_and_feel_file(rel: str) -> bool:
    import re

    rel = rel.replace(os.sep, '/')
    return rel.startswith(LOOK_AND_FEEL_FILES) or bool(re.match(LOOK_AND_FEEL_FILE_PATTERN, rel))


class Found(NamedTuple):
    path: str  # the settings folder: calibre's config directory
    library: str  # its current library, or ''
    plugins: tuple  # names of the plugins it has installed


def candidates() -> list:
    "Where calibre keeps its settings on this platform, most likely first."
    from calibre.constants import islinux, ismacos, iswindows

    home = os.path.expanduser('~')
    if ismacos:
        return [os.path.join(home, 'Library', 'Preferences', 'calibre')]
    if iswindows:
        try:
            from calibre_extensions import winutil

            base = winutil.special_folder_path(winutil.CSIDL_APPDATA)
        except Exception:
            base = os.environ.get('APPDATA', '')
        return [os.path.join(base, 'calibre')] if base else []
    ans = []
    xdg = os.environ.get('XDG_CONFIG_HOME') or os.path.join(home, '.config')
    ans.append(os.path.join(xdg, 'calibre'))
    if islinux:
        # calibre's own Flatpak keeps its settings inside its sandbox.
        ans.append(os.path.join(home, '.var', 'app', 'com.calibre_ebook.calibre', 'config', 'calibre'))
    return ans


def _same(a: str, b: str) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.realpath(a) == os.path.realpath(b)


def settings_folder(path: str) -> str:
    """
    The calibre settings folder at `path`, or '' when there is none.

    Either `path` itself, or a `config` folder inside it: a folder that holds
    a calibre install's data, like this repo's own `.calibre-zen/`, keeps its
    settings one level down, and that is the folder a person points at. Never
    this process's own settings.
    """
    from calibre.constants import config_dir

    if not path:
        return ''
    for folder in (path, os.path.join(path, 'config')):
        if not os.path.isdir(folder) or _same(folder, config_dir):
            continue
        if any(os.path.isfile(os.path.join(folder, m)) for m in MARKERS):
            return folder
    return ''


def own_settings(path: str) -> bool:
    """
    Whether `path` is, or holds as `config`, the settings this process runs
    on. Never a source -- a copy onto itself -- but worth telling apart from
    a folder with no settings at all, because under the dev launcher it is
    exactly the folder a person reaches for.
    """
    from calibre.constants import config_dir

    return bool(path) and any(os.path.isdir(f) and _same(f, config_dir) for f in (path, os.path.join(path, 'config')))


def source() -> str:
    "calibre's config directory, or '' when there is nothing to import."
    from calibre.constants import isportable

    override = os.environ.get(ENV_VAR, '')
    if override.lower() in OFF_VALUES:
        return ''
    if override:
        paths = [override]
    elif isportable:
        # A portable install is its own island; its neighbour's settings are
        # not the reader's.
        return ''
    else:
        paths = candidates()
    for path in paths:
        if folder := settings_folder(path):
            return folder
    return ''


def offered() -> bool:
    "Whether the wizard should offer an import at all. CALIBRE_ZEN_IMPORT_FROM=0 says no."
    return os.environ.get(ENV_VAR, '').lower() not in OFF_VALUES


def _read_json(path: str):
    try:
        with open(path, 'rb') as f:
            return json.loads(f.read())
    except Exception:
        return None


def find(path: str | None = None) -> Found | None:
    """
    What an import from `path` would bring -- calibre's own settings when no
    path is given -- or None when there is nothing to import there.
    """
    path = source() if path is None else settings_folder(path)
    if not path:
        return None
    prefs = _read_json(os.path.join(path, 'global.py.json')) or {}
    customize = _read_json(os.path.join(path, 'customize.py.json')) or {}
    library = prefs.get('library_path') if isinstance(prefs, dict) else ''
    plugins = customize.get('plugins') if isinstance(customize, dict) else {}
    return Found(path, library if isinstance(library, str) else '', tuple(sorted(plugins)) if isinstance(plugins, dict) else ())


def _repath(value, src: str, dst: str):
    "Every string under `value` that points into `src`, pointed into `dst`."
    if isinstance(value, str):
        if value == src or value.startswith(src + os.sep):
            return dst + value[len(src) :]
        return value
    if isinstance(value, list):
        return [_repath(v, src, dst) for v in value]
    if isinstance(value, dict):
        return {k: _repath(v, src, dst) for k, v in value.items()}
    return value


def _merged(src_file: str, dst_file: str, rel: str, src: str, dst: str, groups=None, plugins=None) -> bytes | None:
    """
    The JSON to write at `dst_file`, or None to copy the file as it is.

    Only a top-level object is merged; anything else is calibre's file whole.
    `groups` and `plugins`, when given, are what to keep (see `copy`).
    """
    theirs = _read_json(src_file)
    if not isinstance(theirs, dict):
        return None
    for key in DROP_KEYS.get(rel, ()):
        theirs.pop(key, None)
    for key in list(theirs):
        group = group_of_key(rel, key)
        # PLUGINS keys are filtered by plugin, below, not dropped by group.
        if look_and_feel(rel, key) or (groups is not None and group != PLUGINS and group not in groups):
            del theirs[key]
    theirs = _repath(theirs, src, dst)
    if rel == 'customize.py.json' and isinstance(theirs.get('plugins'), dict):
        # The installed plugins, by path. Only the ones whose files came too.
        chosen = plugin_entries(src) if plugins is None else plugins
        theirs['plugins'] = {name: path for name, path in theirs['plugins'].items() if isinstance(path, str) and os.path.basename(path) in chosen}
    ours = _read_json(dst_file) if os.path.exists(dst_file) else None
    merged = {**ours, **theirs} if isinstance(ours, dict) else theirs
    return json.dumps(merged, indent=2, ensure_ascii=False).encode('utf-8')


def wanted(rel: str, groups=None, plugins=None) -> bool:
    "Whether a file at `rel` is part of the selection; None is everything."
    group = group_of_file(rel)
    if group == PLUGINS:
        entry = rel.replace(os.sep, '/').split('/')[1] if '/' in rel.replace(os.sep, '/') else ''
        return plugins is None or entry in plugins
    if rel.replace(os.sep, '/') in ('gui.json', 'customize.py.json'):
        return True  # sorted key by key in _merged
    return groups is None or group in groups


def plan(src: str, groups=None, plugins=None) -> list:
    "[(relative path, source file)] for everything an import copies."
    ans = []
    for dirpath, dirnames, filenames in os.walk(src):
        rel_dir = os.path.relpath(dirpath, src)
        if rel_dir == '.':
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            rel_dir = ''
        for name in filenames:
            rel = os.path.join(rel_dir, name)
            if name.endswith(SKIP_SUFFIXES) or look_and_feel_file(rel) or not wanted(rel, groups, plugins):
                continue
            path = os.path.join(dirpath, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            ans.append((rel, path))
    ans.sort()
    return ans


def copy(src: str, dst: str, groups=None, plugins=None) -> int:
    """
    Copy calibre's settings from `src` into `dst`. Returns the files written.

    `groups` is the set of GROUP_KEYS to bring and `plugins` the set of
    `plugin_entries` to bring; None for either is all of them.

    Files only; the live objects are `refresh_loaded`'s job. Every file is
    written atomically, so a failure part way leaves each file whole -- either
    calibre's, or what was here before.
    """
    from calibre.utils.config_base import commit_data

    count = 0
    for rel, path in plan(src, groups, plugins):
        target = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        data = _merged(path, target, rel, src, dst, groups, plugins) if rel.endswith('.json') else None
        if data is None:
            with open(path, 'rb') as f:
                data = f.read()
        commit_data(target, data)
        count += 1
    return count


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


def reload_plugins() -> None:
    "Load the plugins that came across, as installing one at runtime does."
    from calibre.customize import ui

    ui.initialize_plugins()


def is_library(path: str) -> bool:
    return bool(path) and os.path.isfile(os.path.join(path, 'metadata.db'))


def _settle(config_dir: str) -> None:
    "Everything loaded re-read, and the plugins loaded again."
    refresh_loaded(config_dir)
    try:
        reload_plugins()
    except Exception:
        # A plugin that will not load now will say so again at the next start,
        # in calibre's own words. The settings are in place either way.
        import traceback

        traceback.print_exc()


def run(src: str | None = None, library: str = '', groups=None, plugins=None) -> int:
    """
    The whole import: copy, re-read what is loaded, merge the overlay's
    additions, reload the plugins. `library`, when given, is used instead of
    the one the settings name; `groups` and `plugins` are as for `copy`.
    Returns the number of files written. Raises if the copy fails.
    """
    from calibre.constants import config_dir

    src = src or source()
    if not src:
        return 0
    count = copy(src, config_dir, groups, plugins)
    refresh_loaded(config_dir)
    if groups is None or 'toolbar' in groups:
        from calibre_zen import hooks

        hooks.merge_toolbar_additions()
    if library:
        use_library(library)
    _settle(config_dir)
    return count


def use_library(path: str) -> None:
    "Record `path` as the library, making the folder if it is not there yet."
    from calibre.utils.config import prefs

    os.makedirs(path, exist_ok=True)
    prefs.set('library_path', path)


def has_settings() -> bool:
    "Whether this app already has settings someone made: the wizard has run before."
    from calibre.utils.config import dynamic

    return bool(dynamic.get('welcome_wizard_was_run', False))


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


def reset(config_dir: str | None = None) -> int:
    """
    Put this app's settings back to its defaults. Returns the entries removed.

    Everything in the settings folder goes but the caches, which are
    rebuilt, not chosen. The language is kept -- it was just picked on the
    page doing this -- and so is the note that the welcome wizard has run,
    or the next start would open it again.
    """
    import shutil

    from calibre.constants import config_dir as current
    from calibre.utils.config import dynamic, prefs

    config_dir = config_dir or current
    language = prefs['language']
    removed = 0
    for name in os.listdir(config_dir):
        if name in SKIP_DIRS:
            continue
        path = os.path.join(config_dir, name)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        removed += 1
    _settle(config_dir)
    if language:
        prefs.set('language', language)
    dynamic.set('welcome_wizard_was_run', True)
    return removed

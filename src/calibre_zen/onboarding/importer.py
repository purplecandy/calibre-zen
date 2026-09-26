#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Bring a calibre install's settings into calibre-zen.

calibre-zen keeps its own config directory (`__appname__` is the fork's), so a
person who has used calibre for years starts from defaults: no plugins, no
toolbar, no library. calibre's settings are a directory of files, and nearly
all of them mean the same thing here, so importing them is a copy with three
corrections:

* **JSON files that both sides have are merged**, calibre's keys over ours.
  By the time the wizard runs this process has already written a few keys of
  its own -- the wizard's language, the overlay's `zen_*` choices -- and a
  plain copy would drop them.
* **Paths into calibre's directory are pointed at ours.** calibre stores
  plugins by absolute path (`customize.py.json`), and a path left pointing at
  the other app's folder would share its files after all.
* **Two keys are left behind** (`DROP_KEYS`). `installation_uuid` is what a
  paired device and the content server know an install by, and two apps
  answering to one id is a device that talks to whichever it reached first.
  `edit_metadata_single_layout` picked between calibre's layouts; imported,
  it would hide the compact editor this app opens by default.

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
# Keys left behind. `installation_uuid` names this install rather than
# describing a preference. `edit_metadata_single_layout` was a choice between
# calibre's own layouts, and carried over it would hide the compact editor
# that is this app's default (editor/); the Edit metadata preferences and the
# features menu still switch it.
DROP_KEYS = {
    'global.py.json': frozenset({'installation_uuid'}),
    'gui.json': frozenset({'edit_metadata_single_layout'}),
}
# The files that say calibre has actually been used, rather than just started.
MARKERS = ('global.py.json', 'gui.json')


class Found(NamedTuple):
    path: str  # calibre's config directory
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


def source() -> str:
    "calibre's config directory, or '' when there is nothing to import."
    from calibre.constants import config_dir, isportable

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
        if not os.path.isdir(path) or _same(path, config_dir):
            continue
        if any(os.path.isfile(os.path.join(path, m)) for m in MARKERS):
            return path
    return ''


def _read_json(path: str):
    try:
        with open(path, 'rb') as f:
            return json.loads(f.read())
    except Exception:
        return None


def find() -> Found | None:
    "What an import would bring, or None when there is nothing to import."
    path = source()
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


def _merged(src_file: str, dst_file: str, rel: str, src: str, dst: str) -> bytes | None:
    """
    The JSON to write at `dst_file`, or None to copy the file as it is.

    Only a top-level object is merged; anything else is calibre's file whole.
    """
    theirs = _read_json(src_file)
    if not isinstance(theirs, dict):
        return None
    for key in DROP_KEYS.get(rel, ()):
        theirs.pop(key, None)
    theirs = _repath(theirs, src, dst)
    ours = _read_json(dst_file) if os.path.exists(dst_file) else None
    merged = {**ours, **theirs} if isinstance(ours, dict) else theirs
    return json.dumps(merged, indent=2, ensure_ascii=False).encode('utf-8')


def plan(src: str) -> list:
    "[(relative path, source file)] for everything an import copies."
    ans = []
    for dirpath, dirnames, filenames in os.walk(src):
        rel_dir = os.path.relpath(dirpath, src)
        if rel_dir == '.':
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            rel_dir = ''
        for name in filenames:
            if name.endswith(SKIP_SUFFIXES):
                continue
            path = os.path.join(dirpath, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            ans.append((os.path.join(rel_dir, name), path))
    ans.sort()
    return ans


def copy(src: str, dst: str) -> int:
    """
    Copy calibre's settings from `src` into `dst`. Returns the files written.

    Files only; the live objects are `refresh_loaded`'s job. Every file is
    written atomically, so a failure part way leaves each file whole -- either
    calibre's, or what was here before.
    """
    from calibre.utils.config_base import commit_data

    count = 0
    for rel, path in plan(src):
        target = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        data = _merged(path, target, rel, src, dst) if rel.endswith('.json') else None
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


def run(src: str | None = None) -> int:
    """
    The whole import: copy, re-read what is loaded, reload the plugins.
    Returns the number of files written. Raises if the copy fails.
    """
    from calibre.constants import config_dir

    src = src or source()
    if not src:
        return 0
    count = copy(src, config_dir)
    refresh_loaded(config_dir)
    try:
        reload_plugins()
    except Exception:
        # A plugin that will not load now will say so again at the next start,
        # in calibre's own words. The settings are across either way.
        import traceback

        traceback.print_exc()
    return count

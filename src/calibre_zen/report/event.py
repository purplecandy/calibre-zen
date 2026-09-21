#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
An exception as a Sentry event.

This is the whole of what leaves the machine, so it is written out here rather
than left to an SDK's defaults. What goes: the exception's type and message,
its frames as file, function and line with a few lines of source around ours,
which Zen and which calibre this is, the operating system and Qt, and the
overlay's own state -- scheme, dark mode, icon pack, font, and which modules
installed. What does not: local variables (in this application those are book
titles and library paths), the user's name, the executable path, the library
location, or the names of installed plugins.

Paths are normalised before they go, so `.../site-packages/calibre_zen/centre/
table.py` and `/opt/zen/src/calibre_zen/centre/table.py` are the same frame to
Sentry and group together. Anything under the home directory is written `~`.
"""

import linecache
import os
import platform
import uuid
from collections import deque
from datetime import UTC, datetime

from calibre_zen.report import classify

CONTEXT_LINES = 3
# What the status bar's bug report can quote: (timestamp, summary, our frame).
RECENT: deque = deque(maxlen=8)


def release() -> str:
    "`zen@0.1.0+calibre9.14.0`: semver, so Sentry sorts it, with the upstream as build metadata."
    from calibre.constants import __version__, zen_version

    return f'zen@{zen_version}+calibre{__version__}'


def environment() -> str:
    return 'production' if os.environ.get('CALIBRE_ZEN_PACKAGED') else 'development'


def scrub(text: str) -> str:
    "Strip the one piece of identity a message or path reliably carries."
    home = os.path.expanduser('~')
    if home and home != '~' and home in text:
        text = text.replace(home, '~')
    return text


def normalise_path(filename: str) -> str:
    """
    A path a person can read and Sentry can group on.

    `calibre_zen/...` and `calibre/...` for the two trees that matter; the
    stdlib relative to its `lib/python3.x/`; a plugin's zip by basename only,
    since the directory it sits in is the user's config directory.
    """
    f = filename.replace(os.sep, '/')
    for mark in ('/calibre_zen/', '/calibre/', '/polyglot/', '/qt/'):
        i = f.rfind(mark)
        if i >= 0:
            return f[i + 1 :]
    if f.endswith('.zip'):
        return 'calibre_plugins/' + os.path.basename(f)
    i = f.find('/lib/python')
    if i >= 0:
        j = f.find('/', i + len('/lib/python'))
        if j >= 0:
            return f[j + 1 :]
    return scrub(f)


def _frame(frame, lineno: int, module: str) -> dict:
    filename = frame.f_code.co_filename
    o = classify.frame_origin(filename, module)
    ans = {
        'filename': normalise_path(filename),
        'function': frame.f_code.co_name,
        'module': module,
        'lineno': lineno,
        'in_app': o == classify.ZEN,
    }
    if o != classify.PLUGIN:
        # Source is on disk for our tree and calibre's; a plugin's lives in a
        # zip and would need the loader. A few lines either side is what makes
        # a report readable without opening the file.
        lines = linecache.getlines(filename, frame.f_globals)
        if lines and 0 < lineno <= len(lines):
            lo, hi = max(0, lineno - 1 - CONTEXT_LINES), min(len(lines), lineno + CONTEXT_LINES)
            ans['pre_context'] = [ln.rstrip('\n') for ln in lines[lo : lineno - 1]]
            ans['context_line'] = lines[lineno - 1].rstrip('\n')
            ans['post_context'] = [ln.rstrip('\n') for ln in lines[lineno:hi]]
    return ans


def _exception_values(exc: BaseException, tb, mechanism: dict) -> list[dict]:
    "The exception and its chain, oldest first, each with its own frames."
    chain = []
    seen = set()
    e = exc
    while e is not None and id(e) not in seen:
        seen.add(id(e))
        chain.append(e)
        e = e.__cause__ or (None if e.__suppress_context__ else e.__context__)
    chain.reverse()
    values = []
    for i, e in enumerate(chain):
        t = tb if (e is exc and tb is not None) else e.__traceback__
        frames = []
        while t is not None:
            f = t.tb_frame
            frames.append(_frame(f, t.tb_lineno, f.f_globals.get('__name__', '')))
            t = t.tb_next
        v = {
            'type': type(e).__name__,
            'value': scrub(str(e))[:2000],
            'module': type(e).__module__,
            'stacktrace': {'frames': frames},
        }
        if i == len(chain) - 1:
            v['mechanism'] = mechanism
        values.append(v)
    return values


def _os_context() -> dict:
    from calibre.constants import islinux, ismacos, iswindows

    if iswindows:
        rel = platform.win32_ver()
        return {'name': 'Windows', 'version': rel[0], 'build': rel[1]}
    if ismacos:
        return {'name': 'macOS', 'version': platform.mac_ver()[0]}
    ans = {'name': 'Linux', 'kernel_version': platform.release()}
    if islinux:
        try:
            r = platform.freedesktop_os_release()
            ans['version'] = r.get('PRETTY_NAME', r.get('ID', ''))
        except Exception:
            pass
    return ans


def _qt_version() -> str:
    try:
        from qt.core import qVersion

        return qVersion()
    except Exception:
        return ''


def zen_context() -> dict:
    "The overlay's own state, read defensively: a report must build even when the thing that broke is one of these."
    ans = {}

    def put(key, fn):
        try:
            ans[key] = fn()
        except Exception:
            ans[key] = '?'

    def scheme():
        from calibre_zen.theme.tokens import schemes

        return _name(schemes.active())

    def appearance():
        from calibre_zen.theme import appearance

        return appearance.current()

    def icons():
        from calibre_zen.icons import registry

        return _name(registry.active())

    def modules():
        from calibre_zen.report import guard

        return dict(guard.states())

    put('scheme', scheme)
    put('appearance', appearance)
    put('icons', icons)
    put('font', lambda: os.environ.get('CALIBRE_ZEN_FONT', 'inter'))
    put('modules', modules)
    put('overrides', lambda: sorted(k for k in os.environ if k.startswith('CALIBRE_ZEN_') and k != 'CALIBRE_ZEN_PACKAGED'))
    return ans


def _name(obj) -> str:
    if obj is None:
        return 'none'
    return str(getattr(obj, 'name', obj))


def build(exc: BaseException, tb=None, *, mechanism_type: str = 'excepthook', handled: bool = False, tags: dict | None = None) -> dict:
    """
    The event, as Sentry's event payload. Pure: nothing here talks to the
    network or the UI, so it can be built on any thread and inspected in a test.
    """
    from calibre.constants import __appname__, __version__, zen_display_name, zen_version

    mechanism = {'type': mechanism_type, 'handled': handled}
    zen = zen_context()
    modules = zen.get('modules') or {}
    degraded = any(v == 'failed' for v in modules.values()) if isinstance(modules, dict) else False
    all_tags = {
        'origin': classify.origin(exc, tb),
        'calibre.version': __version__,
        'zen.version': zen_version,
        'zen.scheme': str(zen.get('scheme', '?')),
        'zen.appearance': str(zen.get('appearance', '?')),
        'zen.icons': str(zen.get('icons', '?')),
        'zen.degraded': 'yes' if degraded else 'no',
        'qt.version': _qt_version(),
        'plugins.on_stack': 'yes' if classify.has_plugin_frames(exc, tb) else 'no',
    }
    if tags:
        all_tags.update(tags)
    ans = {
        'event_id': uuid.uuid4().hex,
        'timestamp': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'platform': 'python',
        'level': 'error',
        'logger': 'calibre_zen',
        'release': release(),
        'environment': environment(),
        'sdk': {'name': 'calibre-zen.report', 'version': zen_version},
        'contexts': {
            'os': _os_context(),
            'runtime': {'name': platform.python_implementation(), 'version': platform.python_version()},
            'app': {'app_name': zen_display_name, 'app_identifier': __appname__, 'app_version': zen_version},
            'zen': zen,
        },
        'tags': {k: v for k, v in all_tags.items() if v},
        'exception': {'values': _exception_values(exc, tb, mechanism)},
    }
    from calibre_zen.report import consent

    uid = consent.install_id(create=False)
    if uid:
        ans['user'] = {'id': uid}
    _remember(ans)
    return ans


def _remember(ev: dict) -> None:
    where = ''
    for v in ev['exception']['values']:
        for f in v['stacktrace']['frames']:
            if f.get('in_app'):
                where = f'{f["filename"]}:{f["lineno"]} in {f["function"]}'
    RECENT.append((ev['timestamp'], summary(ev), where))


def recent() -> list[tuple[str, str, str]]:
    return list(RECENT)


def summary(event: dict) -> str:
    "One line for a dialog or the log: the innermost exception."
    values = event.get('exception', {}).get('values') or []
    if not values:
        return event.get('message', '')
    v = values[-1]
    return f'{v.get("type", "")}: {v.get("value", "")}'

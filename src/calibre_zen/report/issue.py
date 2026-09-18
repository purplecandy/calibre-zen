#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
A bug report the person writes, with the boring half already filled in.

The crash reporter (`event.py`) is for the moment something breaks. This is
for everything else: it looks wrong, it is slow, it did the wrong thing. The
status bar's Report a bug menu opens GitHub's issue form with two of its
fields prefilled -- the environment (which Zen, which calibre, which OS and
Qt, which scheme and icon pack, which modules installed, which plugins) and
the Zen errors seen this session -- so the reporter types only what they saw.
Both fields are on screen and editable before anything is submitted; this
never posts.

GitHub prefills an issue form from the URL's query string, one parameter per
field id. The ids here must match `.github/ISSUE_TEMPLATE/01-bug.yml`. URLs
have a length ceiling of roughly 8 KB, so the logs are trimmed to fit.

The Reddit entry is a link and nothing more; Reddit has no prefill. Copy
diagnostics puts the same two blocks on the clipboard for pasting there.
"""

import platform
from urllib.parse import urlencode

GITHUB_REPO = 'purplecandy/calibre-zen'
GITHUB_ISSUES = f'https://github.com/{GITHUB_REPO}/issues'
TEMPLATE = '01-bug.yml'
# The menu hides the entry while this is empty.
REDDIT_URL = 'https://www.reddit.com/r/CalibreZen/'
# Where calibre's own bugs go. Kovid takes reports on the forum and Launchpad,
# not GitHub, and a bug that reproduces without Zen is his, not ours.
CALIBRE_BUGS_URL = 'https://calibre-ebook.com/bugs'

URL_BUDGET = 7000
LOGS_MIN = 800


def environment_block() -> str:
    from calibre.constants import __version__, zen_version
    from calibre_zen.report import event

    zen = event.zen_context()
    modules = zen.get('modules') or {}
    lines = [
        f'Calibre Zen {zen_version} on calibre {__version__} ({event.environment()})',
        _os_line(),
        f'Qt {event._qt_version()}, Python {platform.python_version()}',
        f'Scheme {zen.get("scheme")}, appearance {zen.get("appearance")}, icons {zen.get("icons")}, font {zen.get("font")}',
    ]
    if isinstance(modules, dict) and modules:
        lines.append('Modules: ' + ', '.join(f'{k}={v}' for k, v in modules.items()))
    overrides = zen.get('overrides') or []
    if overrides:
        lines.append('Environment overrides: ' + ', '.join(overrides))
    plugins = _plugins()
    lines.append('Third-party plugins: ' + (', '.join(plugins) if plugins else 'none'))
    return '\n'.join(lines)


def _os_line() -> str:
    from calibre_zen.report import event

    os_ = event._os_context()
    parts = [os_.get('name', ''), os_.get('version', '')]
    if os_.get('build'):
        parts.append(f'build {os_["build"]}')
    if os_.get('kernel_version'):
        parts.append(f'kernel {os_["kernel_version"]}')
    return ' '.join(p for p in parts if p) + f', {platform.machine()}'


def _plugins() -> list[str]:
    try:
        from calibre.customize import PluginInstallationType
        from calibre.customize.ui import initialized_plugins

        return sorted(
            f'{p.name} {p.version_string()}' if hasattr(p, 'version_string') else p.name
            for p in initialized_plugins()
            if getattr(p, 'installation_type', None) is not PluginInstallationType.BUILTIN
        )
    except Exception:
        return []


def logs_block(limit: int | None = None) -> str:
    "The Zen errors seen this session, newest last, trimmed from the top to fit `limit`."
    from calibre_zen.report import event, guard

    lines = []
    failed = guard.failed()
    if failed:
        lines.append('Modules that failed to install: ' + ', '.join(failed))
    recent = event.recent()
    if not recent:
        lines.append('No errors in Calibre Zen code this session.')
    for stamp, summary, where in recent:
        lines.append(f'{stamp}  {summary}' + (f'  @ {where}' if where else ''))
    text = '\n'.join(lines)
    if limit is not None and len(text) > limit:
        text = '…' + text[-(limit - 1) :]
    return text


def github_url(title: str = '') -> str:
    "The new-issue URL, environment and logs prefilled, trimmed to the budget."
    env = environment_block()
    fixed = urlencode({'template': TEMPLATE, 'title': title, 'environment': env})
    room = URL_BUDGET - len(GITHUB_ISSUES) - len('/new?') - len(fixed) - len('&logs=')
    logs = logs_block(limit=max(LOGS_MIN, room // 3))  # percent-encoding roughly triples
    return f'{GITHUB_ISSUES}/new?' + fixed + '&' + urlencode({'logs': logs})


def diagnostics_text() -> str:
    "Both blocks, for the clipboard."
    return '## Environment\n' + environment_block() + '\n\n## Zen errors this session\n' + logs_block()

#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Check for new releases of calibre-zen, not of calibre.

calibre checks its own server once a day and, finding a newer calibre, shows
"Update available: 9.15.0" in the status bar and a dialog whose Get update
button opens calibre's download page. A packaged calibre-zen ran that check
unchanged, and so offered its users a release they cannot install over it.

Three things are wrapped, all in `calibre.gui2.update`, and the machinery
around them -- the daily thread, the status-bar label, the "notify me" and
"already told you" bookkeeping, the plugin-update count that rides along --
stays calibre's:

    CheckForUpdates.run
        The thread body. Ours fetches the release feed and compares its
        zen_version with this build's, then runs calibre's own plugin-update
        check exactly as before and emits the same signal. calibre's compared
        against calibre's numeric_version, which a zen version never exceeds.

    Main.update_found
        What the signal reaches. calibre's treats a version whose first
        number is 0 as "no update", which every 0.x release of this fork is,
        and words the label for calibre. Ours is the same dozen lines with the
        fork's name in them and no such rule.

    get_download_url
        Where Get update goes: the release's page rather than calibre's
        download page. Rebound in its module, where the dialog looks it up.

The feed is `latest.json`, an asset the release workflow writes beside the
packages, at the address GitHub keeps pointing at the newest published
release. A draft is not "latest" until it is published, and the
`upstream-<version>` mirror entries are pre-releases, so neither can announce
itself. The fetch is one verified HTTPS GET over the same connection the
crash reporter uses, redirects followed by hand because GitHub answers that
address with one.

    CALIBRE_ZEN_UPDATE=0            calibre's own check back
    CALIBRE_ZEN_UPDATE_URL=<url>    another feed; file:///... reads a local file,
                                    which is how the headless test drives it
"""

import json
import os
import re
from urllib.parse import urlsplit

FEED_URL = 'https://github.com/purplecandy/calibre-zen/releases/latest/download/latest.json'
RELEASES_URL = 'https://github.com/purplecandy/calibre-zen/releases'
TIMEOUT = 15
MAX_REDIRECTS = 5
NOTIFIED_KEY = 'zen-notified-version-updates'

_installed = False
_latest: dict = {}  # the last feed read, for the dialog and the download URL


def enabled() -> bool:
    return os.environ.get('CALIBRE_ZEN_UPDATE', '1') not in ('0', 'false', 'no', 'off')


def feed_url() -> str:
    return os.environ.get('CALIBRE_ZEN_UPDATE_URL') or FEED_URL


# --------------------------------------------------------------- the feed


def parse_version(v) -> tuple[int, int, int]:
    "The first three integers in a version string, zero-padded: '0.2' -> (0, 2, 0)."
    nums = [int(x) for x in re.findall(r'\d+', str(v))[:3]]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


def fetch(url: str | None = None) -> dict:
    """
    Read the feed. Raises on anything short of a well-formed one, which the
    thread prints and swallows exactly as calibre does its own failures.
    """
    url = url or feed_url()
    if url.startswith('file:'):
        path = url[len('file:') :].lstrip('/')  # file:///tmp/x -> tmp/x; file:///C:/x -> C:/x
        if os.name != 'nt':
            path = '/' + path
        with open(path, 'rb') as f:
            raw = f.read()
    else:
        raw = _get(url)
    feed = json.loads(raw.decode('utf-8'))
    if not isinstance(feed, dict) or 'zen_version' not in feed:
        raise ValueError('the release feed has no zen_version')
    return feed


def _get(url: str, redirects: int = MAX_REDIRECTS) -> bytes:
    from calibre.constants import zen_version
    from calibre_zen.report.transport import connection

    p = urlsplit(url)
    if p.scheme != 'https':
        raise ValueError(f'the release feed must be https, not {p.scheme!r}: {url}')
    conn = connection(p.hostname, p.port or 443, timeout=TIMEOUT)
    try:
        path = p.path or '/'
        if p.query:
            path += '?' + p.query
        conn.request('GET', path, headers={'User-Agent': f'calibre-zen/{zen_version}', 'Accept': 'application/json'})
        resp = conn.getresponse()
        if resp.status in (301, 302, 303, 307, 308):
            if redirects <= 0:
                raise ValueError('too many redirects fetching the release feed')
            location = resp.getheader('Location')
            if not location:
                raise ValueError(f'{url} redirected nowhere')
            resp.read()
            return _get(location, redirects - 1)
        if resp.status != 200:
            raise ValueError(f'{url} answered HTTP {resp.status}')
        return resp.read()
    finally:
        conn.close()


def check_once() -> tuple[tuple[int, int, int], dict]:
    """
    One check, synchronously: the newest version as a tuple and the feed it
    came from. (0, 0, 0) when this build is current. The thread body calls
    this; so does the headless test.
    """
    global _latest
    from calibre.constants import zen_version

    feed = fetch()
    _latest = feed
    newest = parse_version(feed['zen_version'])
    if newest > parse_version(zen_version):
        return newest, feed
    return (0, 0, 0), feed


def release_url() -> str:
    "The page Get update opens: the release's own when the feed named it."
    return _latest.get('url') or RELEASES_URL


# --------------------------------------------------------------- the wraps


def install() -> bool:
    global _installed
    if _installed:
        return True
    if not enabled():
        return False
    from calibre.gui2 import update as up
    from calibre.gui2.ui import Main

    up.CheckForUpdates.run = _run
    up.get_download_url = release_url
    Main.update_found = _update_found
    _installed = True
    return True


def _run(self):
    "CheckForUpdates.run, against our feed. The plugin half is calibre's own."
    from calibre import as_unicode, prints
    from calibre.gui2.dialogs.plugin_updater import get_plugin_updates_available
    from calibre.gui2.update import NO_CALIBRE_UPDATE

    while not self.shutdown_event.is_set():
        version = NO_CALIBRE_UPDATE
        plugins = 0
        try:
            version, _feed = check_once()
        except Exception as e:
            prints('Failed to check for calibre-zen update:', as_unicode(e))
        try:
            update_plugins = get_plugin_updates_available(raise_error=True)
            if update_plugins is not None:
                plugins = len(update_plugins)
        except Exception as e:
            prints('Failed to check for plugin update:', as_unicode(e))
        if version != NO_CALIBRE_UPDATE or plugins > 0:
            self.signal.update_found.emit(version, plugins)
        self.shutdown_event.wait(self.INTERVAL)


def _update_found(self, version, number_of_plugin_updates, force=False, no_show_popup=False):
    """
    Main.update_found. The same shape as calibre's -- recalc_update_label and
    update_link_clicked call it with the same arguments -- minus the rule that
    a leading 0 means nothing to report.
    """
    from calibre.constants import zen_display_name
    from calibre.gui2 import config, qapplication_or_fail
    from calibre.gui2.update import NO_CALIBRE_UPDATE
    from calibre.utils.localization import _, ngettext
    from calibre.utils.serialize import msgpack_dumps
    from polyglot.binary import as_hex_unicode

    self.last_newest_calibre_version = version
    has_update = version != NO_CALIBRE_UPDATE
    has_plugin_updates = number_of_plugin_updates > 0
    self.plugin_update_found(number_of_plugin_updates)
    if not has_update and not has_plugin_updates:
        self.status_bar.update_label.setVisible(False)
        return
    link = as_hex_unicode(msgpack_dumps((tuple(version), number_of_plugin_updates)))
    version_str = '.'.join(map(str, version))
    if has_update:
        plt = ''
        if has_plugin_updates:
            plt = ngettext(' and one plugin update', ' and {} plugin updates', number_of_plugin_updates).format(number_of_plugin_updates)
        green = 'darkgreen' if qapplication_or_fail().is_dark_theme else 'green'
        msg = '<span style="color:{}; font-weight: bold">{}: <a href="update:{}">{} {}{}</a></span>'.format(
            green, _('Update available'), link, zen_display_name, version_str, plt
        )
    else:
        plt = ngettext('plugin update available', 'plugin updates available', number_of_plugin_updates)
        msg = f'<a href="update:{link}">{number_of_plugin_updates} {plt}</a>'
    self.status_bar.update_label.setText(msg)
    self.status_bar.update_label.setVisible(True)

    if has_update:
        if force or (config.get('new_version_notification') and not _notified(version_str)):
            if not no_show_popup:
                self._update_notification__ = Notification(version_str, number_of_plugin_updates, parent=self)
                self._update_notification__.show()
    elif has_plugin_updates:
        if force:
            self.show_plugin_update_dialog()


# calibre remembers which versions it has already shown the dialog for by
# major.minor, so 9.14.1 after 9.14.0 is not news. For this fork a third
# number is a release like any other, so the whole string is the key.
def _notified(version_str: str) -> bool:
    from calibre.gui2 import dynamic

    return version_str in (dynamic.get(NOTIFIED_KEY) or set())


def _save_notified(version_str: str) -> None:
    from calibre.gui2 import dynamic

    done = dynamic.get(NOTIFIED_KEY) or set()
    done.add(version_str)
    dynamic.set(NOTIFIED_KEY, done)


_notification_class = None


def Notification(version_str, plugin_updates, parent=None):
    "The dialog. Its class is built on first use so this module imports no Qt widgets."
    global _notification_class
    if _notification_class is None:
        _notification_class = _make_notification_class()
    return _notification_class(version_str, plugin_updates, parent=parent)


def _make_notification_class():
    from calibre.gui2.update import UpdateNotification
    from calibre.utils.localization import _

    class ZenUpdateNotification(UpdateNotification):
        """
        calibre's dialog -- logo, checkbox, Get update, Cancel, plugin button
        when there are plugin updates -- with the fork's words on it. accept()
        opens get_download_url(), which install() rebound to the release page.
        """

        def __init__(self, version_str, plugin_updates, parent=None):
            from calibre.constants import zen_display_name

            UpdateNotification.__init__(self, version_str, plugin_updates, parent=parent)
            on = _latest.get('calibre_version')
            on = _(' (on calibre {})').format(on) if on else ''
            self.label.setText(
                '<p>'
                + _('<b>{app} {ver}</b> is available{on}. See <a href="{url}">what changed</a>, or get it from the releases page.').format(
                    app=zen_display_name, ver=version_str, on=on, url=release_url()
                )
            )
            self.setWindowTitle(_('{app} update available').format(app=zen_display_name))
            _save_notified(version_str)

    return ZenUpdateNotification

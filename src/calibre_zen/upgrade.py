#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Download a release and install it over this one, from inside the app.

update.py finds a newer release. This module gets it onto the machine, so
nobody has to visit the releases page, find the right file and run it by
hand. The update dialog's Download button saves the package for this install
to ~/Downloads/calibre-zen-updates/ and checks it against the sha256 and size
the feed lists. Install and restart quits calibre through its own quit, and a
small helper that outlives it puts the new version in place and opens it:

    macOS     Before quitting, mount the .dmg, check that the new app is
              signed by the same team as this one (when this one is signed
              at all), and copy it beside this bundle. After quitting, the
              helper swaps the two with a pair of renames and opens the new
              one, so the app is gone for a second, not a minute. A folder
              we cannot write to opens the .dmg instead.
    .msi      msiexec /passive, which upgrades an older .msi in place and
              shows only its progress bar, then reopen.
    portable  The portable installer, given this Calibre Zen Portable folder,
              which upgrades it without asking and keeps its library and
              settings, then reopen.

Whatever installed this copy and keeps it updated -- Homebrew, Flatpak, the
Microsoft Store -- stays in charge. The dialog says how to update there and
downloads nothing. So does a copy run from source, and the Linux .txz.

The hook into quitting is calibre's own restart. Main.quit(restart=True)
closes the library, stops the workers and leaves the event loop, and
calibre.gui2.main.main() calls restart_after_quit() once the single-instance
lock is released. For the one quit that installs, that module-level name is
rebound to start the helper instead. If the helper cannot start, calibre's
restart runs as it would have, so the worst case is the old version back.

The helper writes one line to last-install.txt in the download folder, and
the next start reads it: a status-bar message for a finished update, a
warning with the reason for one that did not.

    CALIBRE_ZEN_UPDATE_DIR=<dir>    download here instead of Downloads
"""

import hashlib
import os
import re
import subprocess
import sys
import threading
import traceback
from dataclasses import dataclass
from urllib.parse import quote

from calibre_zen import update

CHUNK = 256 * 1024
DOWNLOAD_TIMEOUT = 60
RESULT_FILE = 'last-install.txt'


# --------------------------------------------------------------- where this copy came from


@dataclass(frozen=True)
class Channel:
    """
    How this copy was installed, and so how it updates. `pattern` matches the
    release asset to download; a channel without one is updated elsewhere,
    and `how` is the sentence that says where.
    """

    kind: str
    pattern: str = ''
    target: str = ''  # the .app bundle, or the portable folder
    relaunch: str = ''  # what to open once the new version is in place
    how: str = ''

    @property
    def installable(self) -> bool:
        return bool(self.pattern)


_channel: Channel | None = None  # detected once; a test sets it directly


def channel() -> Channel:
    global _channel
    if _channel is None:
        _channel = detect()
    return _channel


def detect() -> Channel:
    from calibre.constants import __appname__, ismacos, iswindows
    from calibre.utils.localization import _

    if os.environ.get('CALIBRE_ZEN_PACKAGED') != '1':
        return Channel('source', how=_('This copy runs from source. Pull the latest code to update it.'))
    manual = _('Download it from the releases page and install it the same way as before.')
    if ismacos:
        for prefix in ('/opt/homebrew', '/usr/local'):
            if os.path.isdir(os.path.join(prefix, 'Caskroom', __appname__)):
                return Channel('homebrew', how=_('Homebrew keeps it up to date. Run brew upgrade {} to update now.').format(__appname__))
        fw = getattr(sys, 'frameworks_dir', None)
        if not fw:
            return Channel('manual', how=manual)
        app = os.path.dirname(os.path.dirname(os.path.realpath(fw)))
        return Channel('macos', r'-macos\.dmg$', target=app, relaunch=app)
    if iswindows:
        here = os.path.dirname(os.path.abspath(sys.executable))
        if '\\windowsapps\\' in here.lower() + '\\':
            return Channel('store', how=_('The Microsoft Store updates it for you.'))
        portable = os.environ.get('CALIBRE_PORTABLE_BUILD')
        if portable:
            folder = os.path.dirname(os.path.dirname(os.path.abspath(portable)))
            return Channel('portable', r'-portable-installer-[\d.]+\.exe$', target=folder, relaunch=os.path.join(folder, f'{__appname__}-portable.exe'))
        return Channel('msi', r'-windows-x64\.msi$', target=here, relaunch=os.path.join(here, f'{__appname__}.exe'))
    flatpak = os.environ.get('FLATPAK_ID')
    if flatpak or os.path.exists('/.flatpak-info'):
        return Channel('flatpak', how=_('Your software center updates it, or run flatpak update.'))
    return Channel('manual', how=manual)


# --------------------------------------------------------------- the download


def asset_for(feed: dict, ch: Channel) -> tuple[str, str, dict] | None:
    "The (name, url, info) of the release file for this channel, or None."
    if not ch.installable:
        return None
    for name, info in sorted((feed.get('assets') or {}).items()):
        if re.search(ch.pattern, name) and isinstance(info, dict) and info.get('sha256'):
            return name, asset_url(feed, name, info), info
    return None


def asset_url(feed: dict, name: str, info: dict) -> str:
    """
    Where a release file is. Feeds since this module name it; an older feed
    only named the release page, and GitHub keeps a release's files one path
    segment over from it.
    """
    if info.get('url'):
        return info['url']
    page = feed.get('url') or ''
    if '/releases/tag/' not in page:
        raise ValueError('the release feed does not say where its files are')
    return page.replace('/releases/tag/', '/releases/download/', 1) + '/' + quote(name)


def download_dir(create: bool = True) -> str:
    from calibre.constants import __appname__

    d = os.environ.get('CALIBRE_ZEN_UPDATE_DIR')
    if not d:
        base = ''
        try:
            from qt.core import QStandardPaths

            base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        except Exception:
            pass
        d = os.path.join(base or os.path.expanduser('~/Downloads'), f'{__appname__}-updates')
    if create:
        os.makedirs(d, exist_ok=True)
    return d


class Cancelled(Exception):
    pass


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def downloaded(name: str, info: dict) -> str:
    "The path of a finished download of this file, or ''. Only a verified file ever gets its final name."
    path = os.path.join(download_dir(create=False), name)
    size = info.get('size')
    if os.path.isfile(path) and (not size or os.path.getsize(path) == size):
        return path
    return ''


def download(url: str, dest: str, sha256: str, size: int | None = None, progress=None, cancelled=None) -> str:
    """
    Fetch `url` to `dest` and check it. The bytes go to dest.part and are
    renamed only once the size and digest match, so a file under the final
    name is always a whole, verified package. progress(done, total) is called
    as it goes; cancelled() returning true stops it.
    """
    if os.path.isfile(dest) and sha256_of(dest) == sha256:
        return dest
    part = dest + '.part'
    h = hashlib.sha256()
    done = 0
    try:
        with open(part, 'wb') as out:
            for chunk in _stream(url):
                if cancelled is not None and cancelled():
                    raise Cancelled()
                out.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress is not None:
                    progress(done, size or 0)
        if size and done != size:
            raise ValueError(f'got {done} bytes of {url}, the release lists {size}')
        if h.hexdigest() != sha256.lower():
            raise ValueError(f'{os.path.basename(dest)} does not match the sha256 the release lists')
        os.replace(part, dest)
    except BaseException:
        try:
            os.remove(part)
        except OSError:
            pass
        raise
    _tidy(os.path.dirname(dest), keep=os.path.basename(dest))
    return dest


def _stream(url: str):
    if url.startswith('file:'):
        with open(update.file_path(url), 'rb') as f:
            while chunk := f.read(CHUNK):
                yield chunk
        return
    conn, resp = update.open_url(url, accept='application/octet-stream', timeout=DOWNLOAD_TIMEOUT)
    try:
        while chunk := resp.read(CHUNK):
            yield chunk
    finally:
        conn.close()


def _tidy(folder: str, keep: str) -> None:
    "Older packages in the download folder, which the new one replaces."
    for name in os.listdir(folder):
        if name != keep and not name.startswith('.') and name.endswith(('.dmg', '.msi', '.exe', '.part')):
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass


# --------------------------------------------------------------- getting ready to install


class NotWritable(Exception):
    "The folder the app is in cannot be changed by this user."


@dataclass
class Plan:
    "Everything the helper needs, decided while the app is still running."

    channel: Channel
    installer: str
    version: str
    staged: str = ''  # macOS: the new bundle, copied beside the old one


def prepare(ch: Channel, installer: str, sha256: str, version: str) -> Plan:
    """
    The slow part of installing, done before quitting: check the package
    again, and on macOS copy the new app into place beside the old one.
    Raises NotWritable when the app's folder cannot be changed.
    """
    if sha256_of(installer) != sha256.lower():
        raise ValueError(f'{os.path.basename(installer)} changed since it was downloaded')
    plan = Plan(ch, installer, version)
    if ch.kind == 'macos':
        plan.staged = stage_macos(installer, ch.target)
    return plan


def staged_path(app: str) -> str:
    "Hidden, and not ending in .app, so Finder and Launch Services leave it alone."
    return os.path.join(os.path.dirname(app), f'.{os.path.basename(app)}.update')


def stage_macos(dmg: str, app: str) -> str:
    import shutil
    import tempfile

    parent = os.path.dirname(app)
    if not os.access(parent, os.W_OK) or not os.access(app, os.W_OK):
        raise NotWritable(parent)
    staged = staged_path(app)
    shutil.rmtree(staged, ignore_errors=True)
    mnt = tempfile.mkdtemp(prefix='zen-update-')
    _run(['hdiutil', 'attach', '-nobrowse', '-readonly', '-noautoopen', '-quiet', '-mountpoint', mnt, dmg])
    try:
        apps = sorted(n for n in os.listdir(mnt) if n.endswith('.app') and os.path.isdir(os.path.join(mnt, n)))
        if not apps:
            raise ValueError('the disk image has no app in it')
        new = os.path.join(mnt, apps[0])
        team = signing_team(app)
        if team:
            _run(['codesign', '--verify', '--deep', '--strict', new])
            if signing_team(new) != team:
                raise ValueError('the new version is not signed by the same developer as this one')
        _run(['ditto', new, staged])
    except BaseException:
        shutil.rmtree(staged, ignore_errors=True)
        raise
    finally:
        subprocess.run(['hdiutil', 'detach', '-quiet', mnt], capture_output=True)
        try:
            os.rmdir(mnt)
        except OSError:
            pass
    return staged


def signing_team(app: str) -> str:
    "The Developer ID team an app is signed by; '' for ad-hoc or unsigned."
    r = subprocess.run(['codesign', '-dv', app], capture_output=True, text=True)
    m = re.search(r'^TeamIdentifier=(.+)$', r.stderr or '', re.M)
    team = m.group(1).strip() if m else ''
    return '' if team == 'not set' else team


def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise ValueError(f'{cmd[0]} failed: {(r.stderr or r.stdout).strip()}')


def discard(plan: Plan | None) -> None:
    "Undo prepare() when the install does not go ahead."
    if plan is not None and plan.staged:
        import shutil

        shutil.rmtree(plan.staged, ignore_errors=True)


# --------------------------------------------------------------- the helper


# Waits for the app to quit, swaps the prepared bundle in, opens it. Two
# renames in one folder: the old app is never half replaced.
MACOS_HELPER = r'''#!/bin/sh
# Written and started by calibre_zen/upgrade.py. It swaps a prepared update
# into place once the app has quit, then opens it.
pid=$1 app=$2 staged=$3 installer=$4 result=$5 version=$6 opener=${7:-open}
trap 'rm -f "$0"' EXIT
waited=0
while kill -0 "$pid" 2>/dev/null; do
    sleep 0.2
    waited=$((waited + 1))
    if [ "$waited" -gt 3000 ]; then
        printf 'failed %s %s\n' "$version" 'the app took too long to quit' > "$result"
        rm -rf "$staged"
        exit 1
    fi
done
old="$staged.old"
rm -rf "$old"
if mv "$app" "$old"; then
    if mv "$staged" "$app"; then
        printf 'ok %s\n' "$version" > "$result"
        rm -f "$installer"
        $opener "$app"
        rm -rf "$old"
        exit 0
    fi
    mv "$old" "$app"
fi
printf 'failed %s %s\n' "$version" 'the new version could not be moved into place' > "$result"
rm -rf "$staged"
$opener "$app"
exit 1
'''

# Waits for the app and its launcher to quit, runs the installer, reopens.
WINDOWS_HELPER = r'''# Written and started by calibre_zen/upgrade.py. It runs a downloaded
# installer once the app has quit, then opens the app again.
param([int]$ZenPid, [int]$LauncherPid, [string]$Kind, [string]$Installer,
      [string]$Target, [string]$Relaunch, [string]$Result, [string]$Version, [string]$Log)
$launcher = $null
if ($LauncherPid -gt 0) {
    $launcher = Get-Process -Id $LauncherPid -ErrorAction SilentlyContinue
    if ($launcher -and $launcher.Path -ne $Relaunch) { $launcher = $null }
}
Wait-Process -Id $ZenPid -Timeout 600 -ErrorAction SilentlyContinue
if ($launcher) { Wait-Process -Id $LauncherPid -Timeout 60 -ErrorAction SilentlyContinue }
try {
    if ($Kind -eq 'msi') {
        $p = Start-Process -FilePath 'msiexec.exe' -Wait -PassThru -ArgumentList @(
            '/i', "`"$Installer`"", '/passive', '/norestart', '/l*', "`"$Log`"")
    } else {
        $p = Start-Process -FilePath $Installer -Wait -PassThru -ArgumentList @("`"$Target`"")
    }
    $code = $p.ExitCode
} catch {
    $code = -1
}
if ($code -eq 0 -or $code -eq 3010) {
    Set-Content -LiteralPath $Result -Value "ok $Version"
    Remove-Item -LiteralPath $Installer -ErrorAction SilentlyContinue
} elseif ($code -eq 1602) {
    Set-Content -LiteralPath $Result -Value "failed $Version the installer was cancelled"
} else {
    Set-Content -LiteralPath $Result -Value "failed $Version the installer stopped with code $code"
}
if (Test-Path -LiteralPath $Relaunch) { Start-Process -FilePath $Relaunch }
Remove-Item -LiteralPath $PSCommandPath -ErrorAction SilentlyContinue
'''


def helper_command(plan: Plan, folder: str) -> list[str]:
    "Write the helper script to `folder` and return the command that runs it."
    result = os.path.join(folder, RESULT_FILE)
    ch = plan.channel
    if ch.kind == 'macos':
        script = os.path.join(folder, 'install.sh')
        with open(script, 'w', encoding='utf-8', newline='\n') as f:
            f.write(MACOS_HELPER)
        return ['/bin/sh', script, str(os.getpid()), ch.target, plan.staged, plan.installer, result, plan.version]
    if ch.kind in ('msi', 'portable'):
        script = os.path.join(folder, 'install.ps1')
        with open(script, 'w', encoding='utf-8', newline='\r\n') as f:
            f.write(WINDOWS_HELPER)
        ps = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
        return [
            ps, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', script,
            '-ZenPid', str(os.getpid()), '-LauncherPid', str(os.getppid()), '-Kind', ch.kind, '-Installer', plan.installer,
            '-Target', ch.target, '-Relaunch', ch.relaunch, '-Result', result, '-Version', plan.version,
            '-Log', os.path.join(folder, 'install.log'),
        ]  # fmt: skip
    raise ValueError(f'nothing installs a {ch.kind} copy from inside the app')


def start_helper(plan: Plan) -> None:
    "Start the helper, detached, to wait for this process to exit."
    folder = download_dir()
    try:
        os.remove(os.path.join(folder, RESULT_FILE))
    except OSError:
        pass
    cmd = helper_command(plan, folder)
    kw = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL, 'close_fds': True}
    if os.name == 'nt':
        kw['creationflags'] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kw['start_new_session'] = True
    subprocess.Popen(cmd, **kw)


def arm(plan: Plan, module=None):
    """
    Make the next restart_after_quit() start the helper instead of calibre
    again. Returns a function that undoes it, for a quit that did not happen.
    """
    gm = module or sys.modules.get('calibre.gui2.main')
    if gm is None or not callable(getattr(gm, 'restart_after_quit', None)):
        raise RuntimeError('calibre was not started through calibre.gui2.main')
    orig = gm.restart_after_quit

    def restart_after_quit():
        gm.restart_after_quit = orig
        try:
            start_helper(plan)
        except Exception:
            traceback.print_exc()
            discard(plan)
            orig()

    gm.restart_after_quit = restart_after_quit
    return lambda: setattr(gm, 'restart_after_quit', orig)


def install_and_restart(gui, plan: Plan, module=None) -> bool:
    """
    Quit through calibre's own quit, with the helper armed. False when the
    quit did not happen -- the user kept calibre open over running jobs.
    """
    disarm = arm(plan, module)
    gui.quit(restart=True)
    if getattr(gui, 'shutting_down', False):
        return True
    disarm()
    discard(plan)
    return False


# --------------------------------------------------------------- after the restart


def take_result() -> tuple[str, str, str] | None:
    "The helper's last line, as (status, version, reason), read once."
    path = os.path.join(download_dir(create=False), RESULT_FILE)
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            line = f.read().strip()
        os.remove(path)
    except OSError:
        return None
    status, _, rest = line.partition(' ')
    version, _, reason = rest.partition(' ')
    return status, version, reason


def report_result(gui) -> None:
    "Say how the last install went, on the first start after it."
    from calibre.constants import zen_display_name, zen_version
    from calibre.utils.localization import _

    res = take_result()
    if res is None:
        return
    status, version, reason = res
    if status == 'ok':
        try:
            gui.status_bar.show_message(_('Updated to {app} {ver}').format(app=zen_display_name, ver=zen_version), 10000)
        except Exception:
            traceback.print_exc()
        return
    from calibre.gui2 import warning_dialog

    warning_dialog(
        gui,
        _('The update did not install'),
        _('{app} is still on {cur}. The {ver} installer is in {folder}, so you can run it yourself.').format(
            app=zen_display_name, cur=zen_version, ver=version or _('new'), folder=download_dir(create=False)
        ),
        det_msg=reason,
        show=True,
    )


# --------------------------------------------------------------- the dialog


_dialog_class = None


def notification(version_str, plugin_updates, parent=None):
    "The update dialog. Its class is built on first use so this module imports no Qt widgets."
    global _dialog_class
    if _dialog_class is None:
        _dialog_class = _make_dialog_class()
    return _dialog_class(version_str, plugin_updates, parent=parent)


def _make_dialog_class():
    from urllib.parse import urlsplit

    from qt.core import (
        QApplication,
        QCheckBox,
        QDialog,
        QHBoxLayout,
        QIcon,
        QLabel,
        QObject,
        QProgressBar,
        QPushButton,
        Qt,
        QTimer,
        QUrl,
        QVBoxLayout,
        QWidget,
        pyqtSignal,
    )

    from calibre import as_unicode
    from calibre.constants import ismacos, zen_display_name, zen_version
    from calibre.gui2 import config, open_local_file, open_url
    from calibre.utils.localization import _
    from calibre_zen.theme import surfaces
    from calibre_zen.theme.tokens import components as c

    class Signals(QObject):
        progress = pyqtSignal(object, object)
        downloaded = pyqtSignal(object)
        prepared = pyqtSignal(object)
        failed = pyqtSignal(str)
        not_writable = pyqtSignal()

    def named(widget, name):
        widget.setObjectName(name)
        return widget

    def mb(n) -> str:
        return f'{n / 1e6:.0f} MB'

    class ZenUpdateDialog(QDialog):
        """
        One page and the lifted footer, as in the design guide's dialogs. The
        app's icon beside a title, the versions under it, and a status line
        that moves through the steps. The primary button is the one filled
        button and the last on the right: Download, then Install and restart.
        A copy that updates elsewhere is told where, and gets a button to
        the release page instead.
        """

        def __init__(self, version_str, plugin_updates, parent=None):
            QDialog.__init__(self, parent)
            self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
            self.setObjectName('zenUpdate')
            self.setWindowTitle(_('Software update'))
            self.version_str = version_str
            self.feed = dict(update.latest())
            self.channel = channel()
            try:
                self.asset = asset_for(self.feed, self.channel)
            except Exception:
                traceback.print_exc()
                self.asset = None
            self.path = ''
            self.cancel_event = threading.Event()
            self.signals = s = Signals(self)
            q = Qt.ConnectionType.QueuedConnection
            s.progress.connect(self.on_progress, type=q)
            s.downloaded.connect(self.on_downloaded, type=q)
            s.prepared.connect(self.on_prepared, type=q)
            s.failed.connect(self.on_failed, type=q)
            s.not_writable.connect(self.on_not_writable, type=q)
            self.build(plugin_updates)
            update._save_notified(version_str)

            if self.asset is None:
                self.state = 'elsewhere'
                self.show_status(self.channel.how or _('Download it from the releases page and install it the same way as before.'))
                if self.channel.kind in ('homebrew', 'flatpak', 'store'):
                    self.primary.setText(_('OK'))
                    self.cancel.setVisible(False)
                else:
                    self.primary.setText(_('Open releases page'))
                return
            self.path = downloaded(self.asset[0], self.asset[2])
            if self.path:
                self.set_ready()
            else:
                self.state = 'offer'
                self.primary.setText(_('Download'))
                self.show_status(self.where())

        # ---- the layout

        def build(self, plugin_updates):
            outer = QVBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(0)

            page = named(QWidget(self), 'zenUpdatePage')
            row = QHBoxLayout(page)
            row.setContentsMargins(c.UPDATE_PAD, c.UPDATE_PAD, c.UPDATE_PAD, c.UPDATE_PAD)
            row.setSpacing(c.UPDATE_GAP)
            icon = QApplication.windowIcon()
            if icon.isNull():
                icon = QIcon.ic('lt.png')
            logo = named(QLabel(page), 'zenUpdateIcon')
            logo.setPixmap(icon.pixmap(c.UPDATE_ICON, c.UPDATE_ICON))
            logo.setAlignment(Qt.AlignmentFlag.AlignTop)
            row.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)

            col = QVBoxLayout()
            col.setSpacing(c.UPDATE_LINE_GAP)
            row.addLayout(col, 1)
            self.title = named(QLabel(_('{app} {ver} is available').format(app=zen_display_name, ver=self.version_str), page), 'zenUpdateTitle')
            col.addWidget(self.title)
            on = self.feed.get('calibre_version')
            sub = _('You have {cur}.').format(cur=zen_version)
            if on:
                sub += ' ' + _('The new version is built on calibre {}.').format(on)
            self.subtitle = named(QLabel(sub, page), 'zenUpdateSubtitle')
            self.subtitle.setWordWrap(True)
            col.addWidget(self.subtitle)
            col.addSpacing(c.UPDATE_GAP)
            self.status = named(QLabel(page), 'zenUpdateStatus')
            self.status.setWordWrap(True)
            self.status.linkActivated.connect(self.link)
            self.status.setVisible(False)
            col.addWidget(self.status)
            self.bar = named(QProgressBar(page), 'zenUpdateProgress')
            self.bar.setTextVisible(False)
            self.bar.setVisible(False)
            col.addWidget(self.bar)
            col.addSpacing(c.UPDATE_GAP)
            self.cb = named(QCheckBox(_('Tell me when a new version is out'), page), 'zenUpdateNotify')
            self.cb.setChecked(bool(config.get('new_version_notification')))
            self.cb.toggled.connect(lambda on: config.set('new_version_notification', bool(on)))
            col.addWidget(self.cb)
            col.addStretch(1)
            outer.addWidget(page, 1)

            footer = named(QWidget(self), 'zenUpdateFooter')
            bar = QHBoxLayout(footer)
            bar.setContentsMargins(c.UPDATE_PAD, c.UPDATE_FOOTER_PAD_Y, c.UPDATE_PAD, c.UPDATE_FOOTER_PAD_Y)
            bar.setSpacing(c.UPDATE_BUTTON_GAP)
            self.notes = named(QPushButton(_("What's new"), footer), 'zenUpdateNotes')
            self.notes.clicked.connect(lambda: open_url(QUrl(update.release_url())))
            bar.addWidget(self.notes)
            self.plugins = named(QPushButton(_('Update plugins'), footer), 'zenUpdatePlugins')
            self.plugins.clicked.connect(self.get_plugins, type=Qt.ConnectionType.QueuedConnection)
            self.plugins.setVisible(plugin_updates > 0)
            bar.addWidget(self.plugins)
            bar.addStretch(1)
            self.cancel = QPushButton(_('Not now'), footer)
            self.cancel.setAutoDefault(False)
            self.cancel.clicked.connect(self.reject)
            bar.addWidget(self.cancel)
            self.primary = QPushButton(footer)
            self.primary.setDefault(True)
            self.primary.clicked.connect(self.accept)
            bar.addWidget(self.primary)
            for b in (self.notes, self.plugins):
                b.setAutoDefault(False)
            outer.addWidget(footer)
            surfaces.lift(footer)
            # The floor goes on the page, not the dialog: a minimum set on the
            # dialog would override its layout's, and a footer whose buttons
            # outgrow it would squeeze them instead of widening the dialog.
            page.setMinimumWidth(c.UPDATE_WIDTH)

        def show_status(self, text):
            self.status.setText(text)
            self.status.setVisible(bool(text))
            # A turn later, once the new words and button texts have told the
            # layout their sizes; at once, it would fit the old ones and cut
            # the new status short.
            QTimer.singleShot(0, self.adjustSize)

        def link(self, href):
            if href == 'reveal:':
                open_local_file(os.path.dirname(self.path))
            else:
                open_url(QUrl(href))

        def reveal_link(self) -> str:
            return '<a href="reveal:">{}</a>'.format(_('Show in Finder') if ismacos else _('Show the file'))

        def where(self) -> str:
            name, url, info = self.asset
            host = urlsplit(url).hostname or _('this computer')
            size = info.get('size')
            got = _('{size} from {host}.').format(size=mb(size), host=host) if size else _('From {host}.').format(host=host)
            return got + ' ' + _('It goes to your Downloads folder.')

        def working(self, busy: bool):
            self.primary.setEnabled(not busy)
            self.bar.setVisible(busy)

        def get_plugins(self):
            from calibre.gui2.dialogs.plugin_updater import FILTER_UPDATE_AVAILABLE, PluginUpdaterDialog

            d = PluginUpdaterDialog(self.parent(), initial_filter=FILTER_UPDATE_AVAILABLE)
            d.exec()
            if d.do_restart:
                QDialog.accept(self)
                from calibre.gui2.ui import get_gui

                gui = get_gui()
                if gui is not None:
                    gui.quit(restart=True)

        # ---- the steps

        def accept(self):
            if self.state in ('offer', 'failed'):
                self.start_download()
            elif self.state == 'ready':
                self.start_install()
            elif self.state == 'not-writable':
                self.open_installer()
            elif self.state == 'elsewhere':
                if self.channel.kind not in ('homebrew', 'flatpak', 'store'):
                    open_url(QUrl(update.release_url()))
                QDialog.accept(self)

        def reject(self):
            if self.state == 'preparing':
                return  # copying the new app; it finishes in a moment
            self.cancel_event.set()
            QDialog.reject(self)

        def start_download(self):
            name, url, info = self.asset
            self.state = 'downloading'
            self.cancel_event.clear()
            self.primary.setText(_('Downloading'))
            self.cancel.setText(_('Cancel'))
            self.bar.setRange(0, 1000)
            self.bar.setValue(0)
            self.working(True)
            self.show_status(_('Starting the download.'))
            dest = os.path.join(download_dir(), name)
            s, ev = self.signals, self.cancel_event
            last = [-1]

            def progress(done, total):
                step = int(done * 1000 / total) if total else 0
                if step != last[0]:
                    last[0] = step
                    s.progress.emit(done, total)

            def work():
                try:
                    path = download(url, dest, info['sha256'], info.get('size'), progress, ev.is_set)
                except Cancelled:
                    return
                except Exception as e:
                    traceback.print_exc()
                    _emit(s.failed, as_unicode(e))
                else:
                    _emit(s.downloaded, path)

            threading.Thread(target=work, name='ZenUpdateDownload', daemon=True).start()

        def on_progress(self, done, total):
            if total:
                self.bar.setValue(int(done * 1000 / total))
                self.show_status(_('Downloading. {done} of {total}.').format(done=mb(done), total=mb(total)))

        def on_downloaded(self, path):
            self.path = path
            self.set_ready()

        def set_ready(self):
            self.state = 'ready'
            self.working(False)
            self.cancel.setText(_('Later'))
            self.cancel.setEnabled(True)
            self.primary.setText(_('Install and restart'))
            self.show_status(_('The update is downloaded. {app} will close, update and open again.').format(app=zen_display_name) + ' ' + self.reveal_link())

        def on_failed(self, msg):
            self.state = 'failed'
            self.working(False)
            self.cancel.setText(_('Not now'))
            self.cancel.setEnabled(True)
            self.primary.setText(_('Try again'))
            self.show_status(
                _('The update did not come through. You can try again, or get it from the <a href="{url}">releases page</a>.').format(url=update.release_url())
            )
            self.status.setToolTip(msg)

        def start_install(self):
            self.state = 'preparing'
            self.cancel.setEnabled(False)
            self.bar.setRange(0, 0)
            self.working(True)
            self.primary.setText(_('Installing'))
            self.show_status(_('Getting the update ready. This takes a minute.'))
            s, ch, path, sha, ver = self.signals, self.channel, self.path, self.asset[2]['sha256'], self.version_str

            def work():
                try:
                    plan = prepare(ch, path, sha, ver)
                except NotWritable:
                    _emit(s.not_writable)
                except Exception as e:
                    traceback.print_exc()
                    _emit(s.failed, as_unicode(e))
                else:
                    _emit(s.prepared, plan)

            threading.Thread(target=work, name='ZenUpdatePrepare', daemon=True).start()

        def on_prepared(self, plan):
            from calibre.gui2.ui import get_gui

            self.state = 'done'
            gui = get_gui()
            QDialog.accept(self)
            try:
                if gui is None or not install_and_restart(gui, plan):
                    discard(plan)
            except Exception:
                traceback.print_exc()
                discard(plan)
                open_local_file(self.path)

        def on_not_writable(self):
            self.state = 'not-writable'
            self.working(False)
            self.cancel.setText(_('Later'))
            self.cancel.setEnabled(True)
            self.primary.setText(_('Open installer'))
            self.show_status(
                _('{app} cannot replace itself in {folder}. The installer will open, so you can drag the new version over the old one.').format(
                    app=zen_display_name, folder=os.path.dirname(self.channel.target)
                )
            )

        def open_installer(self):
            from calibre.gui2.ui import get_gui

            QDialog.accept(self)
            open_local_file(self.path)
            gui = get_gui()
            if gui is not None:
                gui.quit()

    return ZenUpdateDialog


def _emit(signal, *args) -> None:
    "From a worker thread: the dialog may be gone by the time it finishes."
    try:
        signal.emit(*args)
    except RuntimeError:
        pass

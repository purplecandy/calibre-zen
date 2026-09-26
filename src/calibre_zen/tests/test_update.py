#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The update check's feed, and the in-app download and install behind its
dialog.

Nothing here touches the network or quits the process: feeds and packages
are file:// URLs to files made here, the quit is a stand-in object, and the
macOS swap runs its real script against a throwaway bundle.
"""

import hashlib
import json
import os
import subprocess
import sys
import types
from unittest import mock, skipUnless

from qt.core import QWidget

from calibre_zen import update, upgrade
from calibre_zen.tests.base import ZenTestCase, process_events, wait_until


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_url(path: str) -> str:
    return 'file://' + ('/' if os.name == 'nt' else '') + path.replace(os.sep, '/')


PACKAGE = b'a release package' * 1000
MSI = upgrade.Channel('msi', r'-windows-x64\.msi$', target='C:\\zen', relaunch='C:\\zen\\calibre-zen.exe')


class Fixtures:
    def make_feed(self, folder: str, data: bytes = PACKAGE, **info) -> dict:
        "A feed naming one .msi in `folder`, the way the release workflow writes one."
        pkg = os.path.join(folder, 'calibre-zen-9.9.9-windows-x64.msi')
        with open(pkg, 'wb') as f:
            f.write(data)
        entry = {'sha256': sha(data), 'size': len(data), 'url': file_url(pkg)}
        entry.update(info)
        return {
            'zen_version': '9.9.9',
            'calibre_version': '9.15.0',
            'url': 'https://github.com/purplecandy/calibre-zen/releases/tag/v9.9.9',
            'assets': {'calibre-zen-9.9.9-windows-x64.msi': entry, 'calibre-zen-9.9.9-macos.dmg': {'sha256': 'ab', 'size': 1}},
        }


class TestFeed(ZenTestCase, Fixtures):
    def test_a_newer_release_is_found(self):
        d = self.mkdtemp()
        path = os.path.join(d, 'latest.json')
        with open(path, 'w') as f:
            json.dump(self.make_feed(d), f)
        with mock.patch.dict(os.environ, {'CALIBRE_ZEN_UPDATE_URL': file_url(path)}):
            newest, feed = update.check_once()
        self.assertEqual(newest, (9, 9, 9))
        self.assertEqual(update.latest()['calibre_version'], '9.15.0')

    def test_a_feed_without_a_version_is_refused(self):
        d = self.mkdtemp()
        path = os.path.join(d, 'latest.json')
        with open(path, 'w') as f:
            json.dump({'assets': {}}, f)
        with self.assertRaises(ValueError):
            update.fetch(file_url(path))

    def test_files_come_over_https_only(self):
        with self.assertRaises(ValueError):
            update.open_url('http://example.com/x.msi')


class TestDownload(ZenTestCase, Fixtures):
    def setUp(self):
        self.dir = self.mkdtemp()
        p = mock.patch.dict(os.environ, {'CALIBRE_ZEN_UPDATE_DIR': self.dir})
        p.start()
        self.addCleanup(p.stop)

    def test_each_install_gets_its_own_package(self):
        feed = self.make_feed(self.mkdtemp())
        name, _url, _info = upgrade.asset_for(feed, MSI)
        self.assertEqual(name, 'calibre-zen-9.9.9-windows-x64.msi')
        mac = upgrade.Channel('macos', r'-macos\.dmg$')
        self.assertEqual(upgrade.asset_for(feed, mac)[0], 'calibre-zen-9.9.9-macos.dmg')
        portable = upgrade.Channel('portable', r'-portable-installer-[\d.]+\.exe$')
        self.assertIsNone(upgrade.asset_for(feed, portable), 'this feed has no portable installer')
        self.assertIsNone(upgrade.asset_for(feed, upgrade.Channel('flatpak', how='x')))

    def test_an_older_feed_still_says_where_its_files_are(self):
        feed = {'url': 'https://github.com/o/r/releases/tag/v1.2.3'}
        self.assertEqual(
            upgrade.asset_url(feed, 'calibre-zen 1.2.3.dmg', {'sha256': 'x'}),
            'https://github.com/o/r/releases/download/v1.2.3/calibre-zen%201.2.3.dmg',
        )

    def test_a_verified_package_gets_its_name(self):
        name, url, info = upgrade.asset_for(self.make_feed(self.mkdtemp()), MSI)
        seen = []
        path = upgrade.download(url, os.path.join(self.dir, name), info['sha256'], info['size'], lambda d, t: seen.append((d, t)))
        with open(path, 'rb') as f:
            self.assertEqual(f.read(), PACKAGE)
        self.assertEqual(seen[-1], (len(PACKAGE), len(PACKAGE)))
        self.assertEqual(upgrade.downloaded(name, info), path)

    def test_a_package_that_does_not_match_is_thrown_away(self):
        name, url, info = upgrade.asset_for(self.make_feed(self.mkdtemp(), sha256='0' * 64), MSI)
        with self.assertRaises(ValueError):
            upgrade.download(url, os.path.join(self.dir, name), info['sha256'], info['size'])
        self.assertEqual(os.listdir(self.dir), [], 'neither the file nor its .part stays behind')
        self.assertEqual(upgrade.downloaded(name, info), '')

    def test_a_short_package_is_thrown_away(self):
        name, url, info = upgrade.asset_for(self.make_feed(self.mkdtemp(), size=len(PACKAGE) + 1), MSI)
        with self.assertRaises(ValueError):
            upgrade.download(url, os.path.join(self.dir, name), info['sha256'], info['size'])
        self.assertEqual(os.listdir(self.dir), [])

    def test_a_cancelled_download_leaves_nothing(self):
        name, url, info = upgrade.asset_for(self.make_feed(self.mkdtemp()), MSI)
        with self.assertRaises(upgrade.Cancelled):
            upgrade.download(url, os.path.join(self.dir, name), info['sha256'], info['size'], cancelled=lambda: True)
        self.assertEqual(os.listdir(self.dir), [])

    def test_an_older_package_is_replaced(self):
        old = os.path.join(self.dir, 'calibre-zen-9.9.8-windows-x64.msi')
        with open(old, 'wb') as f:
            f.write(b'old')
        name, url, info = upgrade.asset_for(self.make_feed(self.mkdtemp()), MSI)
        upgrade.download(url, os.path.join(self.dir, name), info['sha256'])
        self.assertEqual(os.listdir(self.dir), [name])

    def test_a_package_changed_after_download_is_not_installed(self):
        name, url, info = upgrade.asset_for(self.make_feed(self.mkdtemp()), MSI)
        path = upgrade.download(url, os.path.join(self.dir, name), info['sha256'])
        with open(path, 'ab') as f:
            f.write(b'tampered')
        with self.assertRaises(ValueError):
            upgrade.prepare(MSI, path, info['sha256'], '9.9.9')


class TestInstall(ZenTestCase):
    def setUp(self):
        self.dir = self.mkdtemp()
        p = mock.patch.dict(os.environ, {'CALIBRE_ZEN_UPDATE_DIR': self.dir})
        p.start()
        self.addCleanup(p.stop)

    def test_a_copy_run_from_source_updates_elsewhere(self):
        with mock.patch.dict(os.environ, {'CALIBRE_ZEN_PACKAGED': ''}):
            ch = upgrade.detect()
        self.assertEqual(ch.kind, 'source')
        self.assertFalse(ch.installable)
        self.assertTrue(ch.how)

    def test_the_helper_is_handed_everything_it_needs(self):
        plan = upgrade.Plan(MSI, os.path.join(self.dir, 'x.msi'), '9.9.9')
        cmd = upgrade.helper_command(plan, self.dir)
        self.assertEqual(cmd[cmd.index('-Kind') + 1], 'msi')
        self.assertEqual(cmd[cmd.index('-Relaunch') + 1], MSI.relaunch)
        self.assertEqual(cmd[cmd.index('-ZenPid') + 1], str(os.getpid()))
        self.assertTrue(os.path.isfile(os.path.join(self.dir, 'install.ps1')))
        mac = upgrade.Channel('macos', 'x', target='/Applications/Calibre Zen.app')
        cmd = upgrade.helper_command(upgrade.Plan(mac, '/d/x.dmg', '9.9.9', staged='/Applications/.Calibre Zen.app.update'), self.dir)
        self.assertEqual(cmd[:3], ['/bin/sh', os.path.join(self.dir, 'install.sh'), str(os.getpid())])
        with self.assertRaises(ValueError):
            upgrade.helper_command(upgrade.Plan(upgrade.Channel('flatpak'), '', '9.9.9'), self.dir)

    def test_calibre_still_restarts_through_the_name_we_rebind(self):
        # arm() rebinds calibre.gui2.main.restart_after_quit, which main()
        # looks up as a global after the single-instance lock is released.
        # If upstream renames it or calls it some other way, installing would
        # quietly become a plain restart.
        import inspect

        import calibre.gui2.main as gm

        self.assertTrue(callable(getattr(gm, 'restart_after_quit', None)))
        src = inspect.getsource(gm.main)
        self.assertIn("if after_quit_actions['restart_after_quit']:\n        restart_after_quit()", src)
        self.assertGreater(src.index('restart_after_quit()'), src.index('with SingleInstance('))

    def fake_main(self):
        calls = []
        return types.SimpleNamespace(restart_after_quit=lambda: calls.append('calibre restart')), calls

    def test_quitting_starts_the_helper_instead_of_calibre(self):
        gm, calls = self.fake_main()
        orig = gm.restart_after_quit

        class Gui:
            shutting_down = False

            def quit(self, restart=False):
                calls.append(('quit', restart))
                self.shutting_down = True

        plan = upgrade.Plan(MSI, 'x.msi', '9.9.9')
        with mock.patch.object(upgrade, 'start_helper', lambda p: calls.append(('helper', p))):
            self.assertTrue(upgrade.install_and_restart(Gui(), plan, module=gm))
            gm.restart_after_quit()  # what calibre.gui2.main.main() does next
        self.assertEqual(calls, [('quit', True), ('helper', plan)])
        self.assertIs(gm.restart_after_quit, orig, 'armed for one quit only')

    def test_a_helper_that_cannot_start_restarts_the_old_version(self):
        gm, calls = self.fake_main()

        def broken(plan):
            raise OSError('no powershell')

        upgrade.arm(upgrade.Plan(MSI, 'x.msi', '9.9.9'), module=gm)
        with mock.patch.object(upgrade, 'start_helper', broken), mock.patch('traceback.print_exc'):
            gm.restart_after_quit()
        self.assertEqual(calls, ['calibre restart'])

    def test_a_quit_the_user_declines_installs_nothing(self):
        gm, calls = self.fake_main()
        orig = gm.restart_after_quit

        class Gui:
            shutting_down = False

            def quit(self, restart=False):
                pass  # jobs are running and the user kept calibre open

        self.assertFalse(upgrade.install_and_restart(Gui(), upgrade.Plan(MSI, 'x.msi', '9.9.9'), module=gm))
        self.assertIs(gm.restart_after_quit, orig)

    def test_the_next_start_hears_how_it_went(self):
        with open(os.path.join(self.dir, upgrade.RESULT_FILE), 'w') as f:
            f.write('failed 9.9.9 the installer stopped with code 1603\n')
        self.assertEqual(upgrade.take_result(), ('failed', '9.9.9', 'the installer stopped with code 1603'))
        self.assertIsNone(upgrade.take_result(), 'said once')


@skipUnless(sys.platform == 'darwin', 'hdiutil and codesign are macOS tools')
class TestMacSwap(ZenTestCase):
    def make_app(self, parent: str, marker: str) -> str:
        app = os.path.join(parent, 'Calibre Zen.app')
        os.makedirs(os.path.join(app, 'Contents', 'MacOS'))
        with open(os.path.join(app, 'Contents', 'MacOS', 'marker'), 'w') as f:
            f.write(marker)
        return app

    def marker(self, app: str) -> str:
        with open(os.path.join(app, 'Contents', 'MacOS', 'marker')) as f:
            return f.read()

    def test_the_new_app_replaces_the_old_one(self):
        apps = self.mkdtemp()
        old = self.make_app(apps, 'old')
        src = self.mkdtemp()
        self.make_app(src, 'new')
        dmg = os.path.join(self.mkdtemp(), 'calibre-zen-9.9.9-macos.dmg')
        subprocess.run(['hdiutil', 'create', '-quiet', '-fs', 'HFS+', '-format', 'UDZO', '-srcfolder', src, dmg], check=True)

        staged = upgrade.stage_macos(dmg, old)
        self.assertEqual(self.marker(staged), 'new')
        self.assertEqual(self.marker(old), 'old', 'nothing changes while the app runs')

        done = subprocess.Popen(['true'])
        done.wait()
        folder = self.mkdtemp()
        result = os.path.join(folder, upgrade.RESULT_FILE)
        script = os.path.join(folder, 'install.sh')
        with open(script, 'w') as f:
            f.write(upgrade.MACOS_HELPER)
        subprocess.run(['/bin/sh', script, str(done.pid), old, staged, dmg, result, '9.9.9', 'true'], check=True, timeout=30)

        self.assertEqual(self.marker(old), 'new')
        self.assertEqual(sorted(os.listdir(apps)), ['Calibre Zen.app'], 'no staged or old copy is left')
        self.assertFalse(os.path.exists(dmg), 'the installer goes once it is used')
        with open(result) as f:
            self.assertEqual(f.read().strip(), 'ok 9.9.9')

    def test_a_folder_that_cannot_be_changed_opens_the_installer_instead(self):
        apps = self.mkdtemp()
        old = self.make_app(apps, 'old')
        os.chmod(apps, 0o555)
        self.addCleanup(os.chmod, apps, 0o755)
        with self.assertRaises(upgrade.NotWritable):
            upgrade.stage_macos('/nowhere.dmg', old)


class TestDialog(ZenTestCase, Fixtures):
    def setUp(self):
        self.dir = self.mkdtemp()
        p = mock.patch.dict(os.environ, {'CALIBRE_ZEN_UPDATE_DIR': self.dir})
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(setattr, upgrade, '_channel', upgrade._channel)
        self.addCleanup(setattr, update, '_latest', update._latest)

    def dialog(self, ch, feed):
        upgrade._channel = ch
        update._latest = feed
        d = upgrade.notification('9.9.9', 0)
        self.addCleanup(d.deleteLater)
        return d

    def test_download_then_install(self):
        d = self.dialog(MSI, self.make_feed(self.mkdtemp()))
        self.assertIn('Download', d.primary.text())
        d.primary.click()
        self.assertTrue(wait_until(lambda: d.state == 'ready'), d.state)
        self.assertIn('Install and restart', d.primary.text())
        self.assertTrue(os.path.isfile(os.path.join(self.dir, 'calibre-zen-9.9.9-windows-x64.msi')))

    def test_a_finished_download_is_not_fetched_again(self):
        feed = self.make_feed(self.mkdtemp())
        name, url, info = upgrade.asset_for(feed, MSI)
        upgrade.download(url, os.path.join(self.dir, name), info['sha256'])
        d = self.dialog(MSI, feed)
        self.assertEqual(d.state, 'ready')

    def test_a_failed_download_can_be_tried_again(self):
        d = self.dialog(MSI, self.make_feed(self.mkdtemp(), sha256='0' * 64))
        with mock.patch('traceback.print_exc'):
            d.primary.click()
            self.assertTrue(wait_until(lambda: d.state == 'failed'), d.state)
        self.assertIn('Try again', d.primary.text())
        self.assertTrue(d.primary.isEnabled())

    def test_a_copy_that_updates_elsewhere_says_where(self):
        ch = upgrade.Channel('flatpak', how='Your software center updates it.')
        d = self.dialog(ch, self.make_feed(self.mkdtemp()))
        process_events()
        self.assertEqual(d.state, 'elsewhere')
        self.assertEqual(d.status.text(), ch.how)
        self.assertEqual(d.primary.text(), 'OK')
        self.assertFalse(d.cancel.isVisible(), 'nothing to put off')

    def test_the_dialog_follows_the_design_guide(self):
        from qt.core import QPushButton

        d = self.dialog(MSI, self.make_feed(self.mkdtemp()))
        d.show()
        process_events()
        footer = d.findChild(QWidget, 'zenUpdateFooter')
        self.assertIsNotNone(footer.graphicsEffect(), 'the footer is lifted')
        buttons = [b for b in footer.findChildren(QPushButton) if b.isVisible()]
        self.assertIs(buttons[-1], d.primary, 'the primary button is last')
        self.assertEqual([b for b in buttons if b.isDefault()], [d.primary], 'and the only filled one')
        self.assertEqual(d.layout().contentsMargins().left(), 0, 'the footer spans the width')

    def test_a_longer_button_widens_the_dialog_instead_of_clipping(self):
        from qt.core import QPushButton

        d = self.dialog(MSI, self.make_feed(self.mkdtemp()))
        d.plugins.setVisible(True)
        d.show()
        d.path = 'x'
        d.set_ready()
        process_events(50)
        for b in d.findChild(QWidget, 'zenUpdateFooter').findChildren(QPushButton):
            if b.isVisible():
                self.assertGreaterEqual(b.width(), b.sizeHint().width(), b.text())

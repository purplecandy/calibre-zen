#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>
#
# calibre-zen: this file signs the fork, so it no longer delegates to
# bypy.macos_sign. That module hardcodes `codesign -s 'Kovid Goyal'`, a .p12 at
# ~/code-signing/maccert.p12 and an apple-id credentials file -- one developer's
# build VM, written down. Everything that identifies the signer is read from the
# environment here instead, and nothing is imported from bypy, so the same code
# can be run by hand against a bundle or a disk image:
#
#     python3 packaging/macos/sign.py build/macos/calibre-zen.app --notarize
#     python3 packaging/macos/sign.py dist/calibre-zen-9.14.0.dmg --notarize
#
# packaging/macos/package.sh runs both when CALIBRE_ZEN_SIGN_IDENTITY is set.
#
# The inside-out walk below is upstream's and is the part worth keeping: nested
# code is signed before the bundle that contains it, because the outer seal
# covers the inner signatures. `codesign --deep` is not a substitute -- Apple
# documents it as a repair tool, not a way to sign for distribution.
#
# Environment:
#   CALIBRE_ZEN_SIGN_IDENTITY   required to sign. The certificate's common name,
#                               e.g. "Developer ID Application: Jane Doe (AB12CD34EF)".
#                               `security find-identity -v -p codesigning` lists them.
#   CALIBRE_ZEN_SIGN_P12        optional. A Developer ID .p12 to import into a
#   CALIBRE_ZEN_SIGN_P12_PASSWORD   throwaway keychain for the duration of the
#                               signing, for a CI runner with no login keychain.
#                               Omitted, the identity must already be in an
#                               unlocked keychain.
#   CALIBRE_ZEN_NOTARY_KEY      App Store Connect API key: the .p8 file, its key
#   CALIBRE_ZEN_NOTARY_KEY_ID   id and the issuer uuid. Preferred over an Apple
#   CALIBRE_ZEN_NOTARY_ISSUER   ID because it carries no second factor.
#   CALIBRE_ZEN_NOTARY_APPLE_ID the fallback: an Apple ID, its team and an
#   CALIBRE_ZEN_NOTARY_TEAM_ID  app-specific password from appleid.apple.com.
#   CALIBRE_ZEN_NOTARY_PASSWORD

import os
import plistlib
import re
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from glob import glob
from uuid import uuid4

entitlements = {
    # MAP_JIT is used by libpcre which is bundled with Qt
    'com.apple.security.cs.allow-jit': True,
    # v8 and therefore WebEngine need this as they don't use MAP_JIT
    'com.apple.security.cs.allow-unsigned-executable-memory': True,
    # calibre itself does not use DYLD env vars, but don't know about its
    # dependencies.
    'com.apple.security.cs.allow-dyld-environment-variables': True,
    # Allow loading of unsigned plugins or frameworks
    # 'com.apple.security.cs.disable-library-validation': True,
}

# Set up by sign_app()/sign_dmg() before anything calls codesign().
state = {'identity': None, 'entitlements': None}


def run(*args):
    if subprocess.call(list(args)) != 0:
        raise SystemExit('Failed: {}'.format(' '.join(args)))


@contextmanager
def current_dir(path):
    cwd = os.getcwd()
    os.chdir(path)
    try:
        yield path
    finally:
        os.chdir(cwd)


@contextmanager
def timeit():
    times = [0, 0]
    st = time.monotonic()
    yield times
    dt = time.monotonic() - st
    times[0] = int(dt) // 60
    times[1] = int(dt) % 60


def files_in(folder):
    for record in os.walk(folder):
        for f in record[-1]:
            yield os.path.join(record[0], f)


def expand_dirs(items, exclude=lambda x: x.endswith('.so')):
    items = set(items)
    dirs = {x for x in items if os.path.isdir(x)}
    items.difference_update(dirs)
    for x in dirs:
        items.update({y for y in files_in(x) if not exclude(y)})
    return items


def get_executable(info_path):
    with open(info_path, 'rb') as f:
        return plistlib.load(f)['CFBundleExecutable']


def find_sub_apps(contents_dir='.'):
    for app in glob(os.path.join(contents_dir, '*.app')):
        cdir = os.path.join(app, 'Contents')
        yield from find_sub_apps(cdir)
        yield app


def signing_identity():
    ans = os.environ.get('CALIBRE_ZEN_SIGN_IDENTITY', '').strip()
    if not ans:
        raise SystemExit(
            'Set CALIBRE_ZEN_SIGN_IDENTITY to the name of a Developer ID Application certificate.\n'
            'Run `security find-identity -v -p codesigning` to see what this machine has.'
        )
    return ans


@contextmanager
def make_certificate_useable():
    # A runner has no login keychain, so the certificate arrives as a .p12 and
    # lives in a keychain that exists only for this build. On a developer's own
    # Mac neither variable is set and the identity is simply already there.
    p12 = os.environ.get('CALIBRE_ZEN_SIGN_P12')
    if not p12:
        yield
        return
    password = os.environ.get('CALIBRE_ZEN_SIGN_P12_PASSWORD', '')
    keychain = tempfile.NamedTemporaryFile(suffix='.keychain', dir=os.path.expanduser('~'), delete=False).name
    os.remove(keychain)
    keychain_password = str(uuid4())
    run('security', 'create-keychain', '-p', keychain_password, keychain)
    raw = subprocess.check_output('security list-keychains -d user'.split()).decode('utf-8')
    existing = [x for x in raw.replace('"', '').split() if x]
    run('security', 'list-keychains', '-d', 'user', '-s', keychain, *existing)
    try:
        # No relock timeout, or a long signing run finds the keychain closed
        run('security', 'set-keychain-settings', keychain)
        run('security', 'unlock-keychain', '-p', keychain_password, keychain)
        run('security', 'import', p12, '-k', keychain, '-P', password, '-T', '/usr/bin/codesign')
        raw = subprocess.check_output(['security', 'find-identity', '-v', '-p', 'codesigning', keychain]).decode('utf-8')
        m = re.search(r'"([^"]+)"', raw)
        if m is None:
            raise SystemExit('No codesigning identity was found in ' + p12)
        cert_id = m.group(1)
        # Without this codesign stops to ask for the key, from a shell that
        # cannot answer
        run('security', 'set-key-partition-list', '-S', 'apple-tool:,apple:', '-s', '-k', keychain_password, '-D', cert_id, '-t', 'private', keychain)
        yield
    finally:
        run('security', 'delete-keychain', keychain)


@contextmanager
def entitlements_file(ent=None):
    fd, path = tempfile.mkstemp(suffix='.plist', prefix='calibre-zen-entitlements-')
    with os.fdopen(fd, 'wb') as f:
        f.write(plistlib.dumps(ent if ent is not None else entitlements))
    try:
        yield path
    finally:
        os.remove(path)


def codesign(items):
    if isinstance(items, str):
        items = [items]
    items = list(items)
    if not items:
        return
    # If you get errors while codesigning that look like "A timestamp was
    # expected but not found" it means that codesign failed to contact Apple's
    # time servers, probably due to network congestion.
    #
    # --options=runtime enables the Hardened Runtime, which notarization
    # requires. --force because parts of a built bundle arrive already signed
    # (Qt signs some of its own, and a preview build is a copy of a signed
    # calibre) and codesign refuses to replace a signature without it.
    cmd = ['codesign', '--force', '--options=runtime', '--timestamp']
    if state['entitlements']:
        cmd.append('--entitlements=' + state['entitlements'])
    cmd += ['-s', state['identity']]
    subprocess.check_call(cmd + items)


def sign_MacOS(contents_dir='.'):
    # Sign everything in MacOS except the main executable
    # which will be signed automatically by codesign when
    # signing the app bundles
    with current_dir(os.path.join(contents_dir, 'MacOS')):
        exe = get_executable('../Info.plist')
        items = {x for x in os.listdir('.') if x != exe and not os.path.islink(x)}
        if items:
            codesign(items)


def do_sign_app(appdir):
    appdir = os.path.abspath(appdir)
    # Extended attributes -- a quarantine flag, a Finder comment, anything ditto
    # carried over -- make codesign fail with "resource fork, Finder
    # information, or similar detritus not allowed".
    run('xattr', '-cr', appdir)
    with current_dir(os.path.join(appdir, 'Contents')):
        sign_MacOS()
        # Sign the sub application bundles
        sub_apps = list(find_sub_apps())
        helper = 'Frameworks/QtWebEngineCore.framework/Versions/Current/Helpers/QtWebEngineProcess.app'
        if os.path.exists(helper):
            sub_apps.append(helper)
        for sa in sub_apps:
            sign_MacOS(os.path.join(sa, 'Contents'))
        codesign(sub_apps)

        # Sign all .so files
        so_files = {x for x in files_in('.') if x.endswith('.so')}
        codesign(so_files)

        # Sign everything in PlugIns
        if os.path.isdir('PlugIns'):
            with current_dir('PlugIns'):
                items = set(os.listdir('.'))
                codesign(expand_dirs(items))

        # Sign everything else in Frameworks
        if os.path.isdir('Frameworks'):
            with current_dir('Frameworks'):
                fw = set(glob('*.framework'))
                codesign(fw)
                items = set(os.listdir('.')) - fw
                codesign(expand_dirs(items))

    # Now sign the main app
    codesign(appdir)
    verify_signature(appdir)
    return 0


def verify_signature(path):
    run('codesign', '-vvv', '--deep', '--strict', path)
    kind = 'open' if path.endswith('.dmg') else 'execute'
    args = ['spctl', '--verbose=4', '--assess', '--type', kind]
    if kind == 'open':
        args += ['--context', 'context:primary-signature']
    try:
        run(*(args + [path]))
    except SystemExit:
        # An assessment before notarization fails by design; say so rather than
        # failing the build, and let notarize_path() be the real check.
        print('spctl rejects', path, '-- expected until it has been notarized', file=sys.stderr)


def notarytool():
    for cmd in (['xcrun', 'notarytool'], ['/usr/bin/notarytool']):
        try:
            subprocess.check_output(cmd + ['--version'], stderr=subprocess.STDOUT)
            return cmd
        except Exception:
            continue
    raise SystemExit('notarytool not found. Install the Xcode command line tools: xcode-select --install')


def notary_credentials():
    key = os.environ.get('CALIBRE_ZEN_NOTARY_KEY')
    if key:
        key_id = os.environ.get('CALIBRE_ZEN_NOTARY_KEY_ID')
        issuer = os.environ.get('CALIBRE_ZEN_NOTARY_ISSUER')
        if not key_id or not issuer:
            raise SystemExit('CALIBRE_ZEN_NOTARY_KEY needs CALIBRE_ZEN_NOTARY_KEY_ID and CALIBRE_ZEN_NOTARY_ISSUER alongside it')
        return ['--key', key, '--key-id', key_id, '--issuer', issuer]
    apple_id = os.environ.get('CALIBRE_ZEN_NOTARY_APPLE_ID')
    if apple_id:
        team = os.environ.get('CALIBRE_ZEN_NOTARY_TEAM_ID')
        password = os.environ.get('CALIBRE_ZEN_NOTARY_PASSWORD')
        if not team or not password:
            raise SystemExit('CALIBRE_ZEN_NOTARY_APPLE_ID needs CALIBRE_ZEN_NOTARY_TEAM_ID and CALIBRE_ZEN_NOTARY_PASSWORD alongside it')
        return ['--apple-id', apple_id, '--team-id', team, '--password', password]
    raise SystemExit(
        'No notarization credentials. Set CALIBRE_ZEN_NOTARY_KEY, _KEY_ID and _ISSUER (an App Store\n'
        'Connect API key), or CALIBRE_ZEN_NOTARY_APPLE_ID, _TEAM_ID and _PASSWORD.'
    )


def notarize_path(path, name='program'):
    # See https://developer.apple.com/documentation/security/customizing-the-notarization-workflow
    creds = notary_credentials()
    submission = path
    tmp_zip = None
    if os.path.isdir(path):
        # A bundle is a directory; notarytool takes an archive of one.
        tmp_zip = os.path.join(os.path.dirname(os.path.abspath(path)), name + '.zip')
        print('Creating zip file for notarization')
        with timeit() as times:
            run('ditto', '-c', '-k', '--zlibCompressionLevel', '9', '--keepParent', path, tmp_zip)
        print('ZIP file of {} MB created in {} minutes and {} seconds'.format(os.path.getsize(tmp_zip) // 1024**2, *times))
        submission = tmp_zip
    try:
        print('Submitting for notarization')
        timeout = 60 * 60
        cmd = notarytool() + ['submit', '--wait'] + creds + [submission]
        with timeit() as times:
            try:
                cp = subprocess.run(cmd, timeout=timeout)
            except subprocess.TimeoutExpired as e:
                raise SystemExit(f'Notarization did not complete in {timeout} seconds. Check pending submissions with `notarytool history`.') from e
        print('Notarization done in {} minutes and {} seconds'.format(*times))
        if cp.returncode != 0:
            raise SystemExit('Notarization failed for ' + submission + '. Run `notarytool log <id>` for the reason.')
    finally:
        if tmp_zip:
            os.remove(tmp_zip)

    # The ticket is stapled to the thing itself, not to the zip that carried it,
    # so that it is present on a machine that is offline when the app first runs.
    with timeit() as times:
        print('Stapling notarization ticket')
        run('xcrun', 'stapler', 'staple', '-v', path)
        run('xcrun', 'stapler', 'validate', '-v', path)
        verify_signature(path)
    print('Stapling took {} minutes and {} seconds'.format(*times))


def sign_app(appdir, notarize):
    with make_certificate_useable(), entitlements_file() as ent:
        state['identity'], state['entitlements'] = signing_identity(), ent
        do_sign_app(appdir)
        if notarize:
            notarize_path(appdir, os.path.basename(appdir).rsplit('.', 1)[0])


def sign_dmg(dmg, notarize):
    # A disk image carries no entitlements and needs no hardened runtime; it is
    # signed so that the download itself is identified, and notarized so that
    # the first double-click is not refused.
    with make_certificate_useable():
        state['identity'], state['entitlements'] = signing_identity(), None
        run('codesign', '--force', '--timestamp', '-s', state['identity'], dmg)
        if notarize:
            notarize_path(dmg, os.path.basename(dmg).rsplit('.', 1)[0])
        else:
            verify_signature(dmg)


def main(argv):
    import argparse

    p = argparse.ArgumentParser(description='Sign a calibre-zen bundle or disk image with a Developer ID certificate')
    p.add_argument('path', help='the .app bundle or .dmg to sign')
    p.add_argument('--notarize', action='store_true', help='submit to Apple, wait for the ticket, and staple it')
    args = p.parse_args(argv[1:])
    path = os.path.abspath(args.path)
    if not os.path.exists(path):
        raise SystemExit('No such path: ' + path)
    if path.endswith('.dmg'):
        sign_dmg(path, args.notarize)
    elif path.endswith('.app'):
        sign_app(path, args.notarize)
    else:
        raise SystemExit('Expected a .app or a .dmg, got ' + path)
    print()
    print(path, 'is signed by', signing_identity())
    if not args.notarize:
        print('It is not notarized. Gatekeeper still refuses a download until it is.')


if __name__ == '__main__':
    main(sys.argv)

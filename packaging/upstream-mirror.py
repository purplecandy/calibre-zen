#!/usr/bin/env python3
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Mirror one calibre release's installers into this repository's own releases.

calibre-zen ships upstream's binaries with this fork's Python laid over them
(BUILDING.md), so every package build starts by downloading an installer that
Kovid Goyal published. Two things can take those away: GitHub, because
upstream deletes a release's assets the day the next release ships (9.14.0's
vanished when 9.15.0 came out), and his archive, download.calibre-ebook.com,
if it is ever down, rate-limited or gone. This script copies a release's
installers into a release of our own, tagged `upstream-<version>` and marked
pre-release so it never shows as this project's "latest", and the package
scripts try that copy first.

Nothing is modified. Every file is checked against a sha256 upstream
published -- the GitHub release's own digests while it still has assets,
otherwise the digests pinned in packaging/upstream.json -- and the release
body records, per file, its size, its digest, where the digest came from and
where the bytes came from. That body is the log.

    packaging/upstream-mirror.py                # upstream's latest release
    packaging/upstream-mirror.py --version 9.14.0
    packaging/upstream-mirror.py --dry-run      # resolve and verify, publish nothing

Needs `gh` logged in (or GH_TOKEN) with write access to the mirror repo named
in packaging/upstream.json. Downloads are kept in .calibre-zen/upstream/, the
same cache the package scripts use, so a local run leaves them ready.
Idempotent: a release that already has every file is left alone, one missing
some gets only those uploaded. Run daily by .github/workflows/zen-upstream-mirror.yml.
"""

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIN = os.path.join(REPO, 'packaging', 'upstream.json')

# What an upstream release ships, for a version whose GitHub assets are gone
# and the API can no longer tell us. The source tarball is included: the
# binaries are GPL, and keeping the matching source beside them is the polite
# form of redistribution.
KNOWN_ASSETS = (
    'calibre-{v}-x86_64.txz',
    'calibre-{v}-arm64.txz',
    'calibre-{v}.dmg',
    'calibre-64bit-{v}.msi',
    'calibre-portable-installer-{v}.exe',
    'calibre-{v}.tar.xz',
)

USER_AGENT = 'calibre-zen-upstream-mirror (+https://github.com/purplecandy/calibre-zen)'


def say(msg):
    print(f'==> {msg}', flush=True)


def die(msg):
    print(f'upstream-mirror: {msg}', file=sys.stderr, flush=True)
    sys.exit(1)


def gh(*args, check=True, input=None):
    """Run gh, return stdout. With check=False, return None on failure."""
    try:
        p = subprocess.run(['gh', *args], capture_output=True, text=True, input=input)
    except FileNotFoundError:
        die('gh is not installed; it does the GitHub API calls and the uploads')
    if p.returncode != 0:
        if not check:
            return None
        die(f'gh {" ".join(args[:3])} failed:\n{p.stderr.strip()}')
    return p.stdout


def human(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def download(url, dest, retries=3):
    """Fetch url to dest. False if it is not there -- including the archive's
    habit of answering a missing path with its HTML index and a 200."""
    for attempt in range(1, retries + 1):
        part = dest + '.part'
        try:
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as r, open(part, 'wb') as out:
                head = r.read(512)
                if b'<!DOCTYPE' in head[:64] or b'<html' in head[:64].lower():
                    return False
                out.write(head)
                shutil.copyfileobj(r, out, 1 << 20)
            os.replace(part, dest)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            say(f'    attempt {attempt}: HTTP {e.code}')
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            say(f'    attempt {attempt}: {e}')
        finally:
            if os.path.exists(part):
                os.unlink(part)
        time.sleep(5 * attempt)
    return False


def upstream_release(repo, version):
    """The upstream release as the API sees it, or None if there is no such tag."""
    out = gh('api', f'repos/{repo}/releases/tags/v{version}', check=False)
    return json.loads(out) if out else None


def latest_version(repo):
    out = gh('api', f'repos/{repo}/releases/latest', '--jq', '.tag_name')
    tag = out.strip()
    if not tag.startswith('v'):
        die(f'unexpected upstream tag {tag!r}')
    return tag[1:]


def our_release(mirror, tag):
    """Our mirror release, or None."""
    out = gh('release', 'view', tag, '-R', mirror, '--json', 'assets,url,isPrerelease', check=False)
    return json.loads(out) if out else None


def plan(pin, version, rel):
    """Decide what to fetch and how each file is checked.

    Returns [(name, size_or_None, sha256_or_None, digest_source, [urls])].
    """
    archive = pin['archive'].rstrip('/')
    items = []
    if rel and rel.get('assets'):
        for a in rel['assets']:
            digest = a.get('digest') or ''
            sha = digest.split(':', 1)[1] if digest.startswith('sha256:') else None
            items.append((a['name'], a['size'], sha, 'GitHub release digest' if sha else None, [a['browser_download_url'], f'{archive}/{version}/{a["name"]}']))
        return items
    # Assets gone from GitHub: the names are known, the digests only if this
    # is the version the fork pins.
    pinned = {a['name']: a['sha256'] for a in pin['assets'].values()} if pin['version'] == version else {}
    for pattern in KNOWN_ASSETS:
        name = pattern.format(v=version)
        sha = pinned.get(name)
        items.append((
            name,
            None,
            sha,
            'packaging/upstream.json' if sha else None,
            [f'{archive}/{version}/{name}', f'https://github.com/{pin["repo"]}/releases/download/v{version}/{name}'],
        ))
    return items


def notes(pin, version, rel, rows, when):
    upstream_url = (rel or {}).get('html_url') or f'https://github.com/{pin["repo"]}/releases/tag/v{version}'
    published = ((rel or {}).get('published_at') or '')[:10]
    on = f' on {published}' if published else ''
    intro = (
        f'A copy of the installers Kovid Goyal published for calibre {version}{on}, kept here so '
        "calibre-zen can be rebuilt after upstream removes them: GitHub loses a release's assets when "
        'the next release ships, and the archive is one server. Nothing is modified. This is not a '
        'calibre-zen release; those are tagged `v<version>`.'
    )
    pinned = f"calibre-zen's packaging currently pins calibre **{pin['version']}** (`packaging/upstream.json`)."
    if pin['version'] != version:
        pinned += f' Taking {version} is a deliberate step: BUILDING.md, "Taking an upstream release".'
    lines = [
        f'calibre {version}, mirrored from upstream on {when}.',
        '',
        intro,
        '',
        f'Upstream: {upstream_url} and {pin["archive"].rstrip("/")}/{version}/',
        '',
        pinned,
        '',
        '| file | size | sha256 | digest from | fetched from |',
        '| --- | --- | --- | --- | --- |',
    ]
    for name, size, sha, source, fetched in rows:
        lines.append(f'| `{name}` | {human(size)} | `{sha}` | {source} | {fetched} |')
    footer = (
        'A digest "from" a published source was compared before upload; "computed here" means upstream '
        'no longer publishes one for that file and the value is what arrived, recorded for the future. '
        'The package scripts check every installer against `packaging/upstream.json` regardless of '
        'where it was fetched from.'
    )
    lines += ['', footer]
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--version', help="calibre version, e.g. 9.14.0 (default: upstream's latest release)")
    ap.add_argument('--cache', default=os.environ.get('CALIBRE_ZEN_UPSTREAM_CACHE') or os.path.join(REPO, '.calibre-zen', 'upstream'))
    ap.add_argument('--dry-run', action='store_true', help='download and verify, but publish nothing')
    args = ap.parse_args()

    with open(PIN) as f:
        pin = json.load(f)
    mirror = pin.get('mirror')
    if not mirror:
        die('packaging/upstream.json has no "mirror" (owner/repo to publish into)')
    repo = pin['repo']

    version = args.version or latest_version(repo)
    tag = f'upstream-{version}'
    say(f'calibre {version} from {repo}, into {mirror} as {tag}')

    rel = upstream_release(repo, version)
    if rel is None:
        die(f'{repo} has no release tagged v{version}')
    items = plan(pin, version, rel)
    if rel.get('assets'):
        say(f'{len(items)} assets on the upstream release, with digests')
    else:
        say(f'upstream release has no assets any more; using the known names, digests from the pin for {pin["version"]}')

    ours = our_release(mirror, tag)
    have = {a['name'] for a in (ours or {}).get('assets', [])}
    missing = [it for it in items if it[0] not in have]
    if ours and not missing:
        say(f'already mirrored, every file present: {ours["url"]}')
        emit(version, False, ours['url'])
        return
    if ours:
        say(f'release exists with {len(have)} of {len(items)} files; fetching the rest')

    os.makedirs(args.cache, exist_ok=True)
    rows = []
    for name, size, sha, source, urls in missing:
        dest = os.path.join(args.cache, name)
        fetched = 'cache'
        if os.path.exists(dest) and (sha is None or sha256_of(dest) == sha):
            say(f'{name}: cached')
        else:
            if os.path.exists(dest):
                say(f'{name}: cached copy does not match its digest, refetching')
                os.unlink(dest)
            for url in urls:
                say(f'{name}: downloading {url}')
                if download(url, dest):
                    fetched = 'GitHub' if 'github.com' in url else 'archive'
                    break
            else:
                die(f'{name}: could not be downloaded from any source')
        got = sha256_of(dest)
        if sha is not None and got != sha:
            os.unlink(dest)
            die(f'{name}: sha256 {got} does not match the {source} digest {sha}; not mirroring it')
        if sha is None:
            source = 'computed here'
        actual = os.path.getsize(dest)
        if size is not None and actual != size:
            die(f'{name}: {actual} bytes, upstream says {size}')
        say(f'{name}: {human(actual)}, sha256 {got[:16]}... ok ({source})')
        rows.append((name, actual, got, source, fetched))

    # Rows for files already there, so the body stays complete.
    for a in (ours or {}).get('assets', []):
        if a['name'] not in {r[0] for r in rows} and a['name'] != 'SHA256SUMS':
            digest = a.get('digest') or ''
            rows.append((a['name'], a['size'], digest.split(':', 1)[-1] or '?', 'this release, earlier run', 'mirror'))
    rows.sort()

    when = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d')
    body = notes(pin, version, rel, rows, when)
    sums = ''.join(f'{sha}  {name}\n' for name, _, sha, _, _ in rows)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(f'## {tag}\n\n{body}')
    if args.dry_run:
        say('dry run; the release body would be:')
        print(body)
        return

    with tempfile.TemporaryDirectory() as tmp:
        notes_path = os.path.join(tmp, 'notes.md')
        sums_path = os.path.join(tmp, 'SHA256SUMS')
        with open(notes_path, 'w') as f:
            f.write(body)
        with open(sums_path, 'w') as f:
            f.write(sums)
        if ours is None:
            say(f'creating {tag}')
            create = ['release', 'create', tag, '-R', mirror, '--prerelease', '--title', f'calibre {version} installers', '--notes-file', notes_path]
            if os.environ.get('GITHUB_SHA'):
                create += ['--target', os.environ['GITHUB_SHA']]
            gh(*create)
        files = [os.path.join(args.cache, name) for name, *_ in missing] + [sums_path]
        say(f'uploading {len(files)} files')
        gh('release', 'upload', tag, *files, '-R', mirror, '--clobber')
        gh('release', 'edit', tag, '-R', mirror, '--notes-file', notes_path)
    ours = our_release(mirror, tag)
    say(f'done: {ours["url"]}')
    emit(version, True, ours['url'])


def emit(version, mirrored, url):
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f'version={version}\nmirrored={"true" if mirrored else "false"}\nurl={url}\n')


if __name__ == '__main__':
    main()

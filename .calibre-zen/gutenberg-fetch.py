#!/usr/bin/env python3
# gutenberg-fetch.py -- download real public-domain EPUBs for a second dev library.
#
# Project Gutenberg allows automated downloads only through its robot harvest
# endpoint, with a pause between requests:
# https://www.gutenberg.org/policy/robot_access.html
# This follows that endpoint page by page, waits between every request, and
# stops once the budget is reached. It can be stopped and rerun: files already
# on disk are skipped and the next harvest page is remembered.
#
#   python3 .calibre-zen/gutenberg-fetch.py                 # 1 GB of epub.images
#   python3 .calibre-zen/gutenberg-fetch.py --budget-mb 300 --langs en fr de
#   python3 .calibre-zen/gutenberg-fetch.py --top 100       # the 100 most downloaded
#
# --top ranks books by the download counts in the offline RDF catalog (about
# 130 MB, fetched once), which the policy allows, instead of reading the
# website's top-100 page, which it does not. It then asks the mirror for each
# book directly.
#
# Then build the library from what was downloaded:
#
#   ./calibre-zen --tool calibre-debug -e .calibre-zen/gutenberg-library.py

import argparse
import csv
import html
import os
import re
import sys
import tarfile
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DEST = os.path.join(HERE, 'gutenberg-sources')
HARVEST = 'https://www.gutenberg.org/robot/harvest'
CATALOG = 'https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv'
RDF_CATALOG = 'https://www.gutenberg.org/cache/epub/feeds/rdf-files.tar.bz2'
MIRROR = 'https://aleph.pglaf.org/cache/epub/{id}/pg{id}-{kind}.epub'
RDF_NAME = re.compile(r'(\d+)/pg\1\.rdf$')
DOWNLOADS = re.compile(rb'<pgterms:downloads[^>]*>(\d+)</pgterms:downloads>')
UA = 'calibre-zen-dev-harvest/1.0 (+https://github.com/purplecandy/calibre-zen)'
LINK = re.compile(r'<a href="([^"]+)">')
# The harvest links name aleph.gutenberg.org, an alias whose certificate is
# issued only for the mirror's own name. Ask for that name rather than turning
# certificate checks off.
MIRROR_ALIASES = {'https://aleph.gutenberg.org/': 'https://aleph.pglaf.org/'}


class TooBig(Exception):
    pass


class Fetcher:
    def __init__(self, delay):
        self.delay = delay
        self.last = 0.0

    def get(self, url, dest=None, max_bytes=None):
        wait = self.last + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                if dest is None:
                    return resp.read().decode('utf-8', 'replace')
                size = int(resp.headers.get('Content-Length') or 0)
                if max_bytes and size > max_bytes:
                    raise TooBig(f'{size / 1e6:.1f} MB')
                part = dest + '.part'
                with open(part, 'wb') as f:
                    while chunk := resp.read(1 << 16):
                        f.write(chunk)
                os.replace(part, dest)
                return os.path.getsize(dest)
        finally:
            self.last = time.monotonic()


def used_bytes(epubs):
    return sum(os.path.getsize(os.path.join(epubs, n)) for n in os.listdir(epubs) if n.endswith('.epub'))


def ranking(dest, fetch):
    """(downloads, id) for every text in the catalog, most downloaded first; cached as top.csv."""
    cached = os.path.join(dest, 'top.csv')
    if not os.path.exists(cached):
        rdf = os.path.join(dest, 'rdf-files.tar.bz2')
        if not os.path.exists(rdf):
            print('rdf catalog:', fetch.get(RDF_CATALOG, rdf), 'bytes', flush=True)
        with open(os.path.join(dest, 'pg_catalog.csv'), encoding='utf-8') as f:
            texts = {row['Text#'] for row in csv.DictReader(f) if row['Type'] == 'Text'}
        rows = []
        with tarfile.open(rdf, 'r:bz2') as tar:
            for member in tar:
                m = RDF_NAME.search(member.name)
                if m and m.group(1) in texts:
                    d = DOWNLOADS.search(tar.extractfile(member).read())
                    rows.append((int(d.group(1)) if d else 0, m.group(1)))
        rows.sort(key=lambda x: (-x[0], int(x[1])))
        with open(cached + '.part', 'w', newline='') as f:
            csv.writer(f).writerows(rows)
        os.replace(cached + '.part', cached)
    with open(cached, newline='') as f:
        return [(int(n), i) for n, i in csv.reader(f)]


def top(args, fetch, epubs):
    """The args.top most downloaded books, walking further down the list past any that fail or are too big."""
    got = total = 0
    kind = args.filetype.split('.', 1)[1]  # epub.images -> images
    for downloads, pg_id in ranking(args.dest, fetch):
        if got >= args.top:
            break
        name = f'pg{pg_id}-{kind}.epub'
        dest = os.path.join(epubs, name)
        if not os.path.exists(dest):
            try:
                total += fetch.get(MIRROR.format(id=pg_id, kind=kind), dest, int(args.max_file_mb * 1_000_000))
            except TooBig as e:
                print(f'skip {name}: too big, {e}', flush=True)
                continue
            except Exception as e:
                print(f'skip {name}: {e}', file=sys.stderr, flush=True)
                continue
        got += 1
        print(f'{got:5d}/{args.top} {downloads:7d} downloads  {name}', flush=True)
    print(f'done: {got} books, {total / 1e6:.1f} MB new in {epubs}', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dest', default=DEFAULT_DEST)
    ap.add_argument('--budget-mb', type=int, default=1000)
    ap.add_argument('--filetype', default='epub.images')
    ap.add_argument('--langs', nargs='*', default=[], help='ISO codes, e.g. en fr de; default all')
    ap.add_argument('--max-file-mb', type=float, default=100, help='skip books bigger than this; 0 for no limit')
    ap.add_argument('--top', type=int, default=0, help='download the N most downloaded books instead of harvesting')
    ap.add_argument('--delay', type=float, default=2.0, help='seconds between requests; keep >= 2')
    args = ap.parse_args()

    epubs = os.path.join(args.dest, 'epub')
    os.makedirs(epubs, exist_ok=True)
    state = os.path.join(args.dest, 'next-page.txt')
    fetch = Fetcher(max(args.delay, 2.0))
    budget = args.budget_mb * 1_000_000

    catalog = os.path.join(args.dest, 'pg_catalog.csv')
    if not os.path.exists(catalog):
        print('catalog:', fetch.get(CATALOG, catalog), 'bytes', flush=True)
    if args.top:
        return top(args, fetch, epubs)

    if os.path.exists(state):
        with open(state) as f:
            page = f.read().strip()
    else:
        q = [('filetypes[]', args.filetype)] + [('langs[]', lang) for lang in args.langs]
        page = f'{HARVEST}?{urllib.parse.urlencode(q)}'

    total = used_bytes(epubs)
    while page and total < budget:
        body = fetch.get(page)
        links = [html.unescape(u) for u in LINK.findall(body)]
        files = [u for u in links if u.endswith('.epub')]
        nxt = next((u for u in links if u.startswith('harvest?')), None)
        for url in files:
            if total >= budget:
                break
            name = url.rsplit('/', 1)[1]
            for alias, real in MIRROR_ALIASES.items():
                if url.startswith(alias):
                    url = real + url[len(alias) :]
            dest = os.path.join(epubs, name)
            if os.path.exists(dest):
                continue
            try:
                total += fetch.get(url, dest, int(args.max_file_mb * 1_000_000))
            except TooBig as e:
                print(f'skip {name}: too big, {e}', flush=True)
                continue
            except Exception as e:
                print(f'skip {name}: {e}', file=sys.stderr, flush=True)
                continue
            n = sum(1 for x in os.listdir(epubs) if x.endswith('.epub'))
            print(f'{n:5d} files {total / 1e6:7.1f} MB  {name}', flush=True)
        if total >= budget:
            break  # keep this page, so a bigger budget later picks up its remaining files
        page = urllib.parse.urljoin(HARVEST, nxt) if nxt else ''
        with open(state, 'w') as f:
            f.write(page)
    print(f'done: {total / 1e6:.1f} MB in {epubs}', flush=True)


if __name__ == '__main__':
    main()

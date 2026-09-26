#!/usr/bin/env python
# gutenberg-library.py -- build a second dev library from real Project Gutenberg books.
#
# The seed library has the right shape but generated text. This one has real
# books: real covers, real tables of contents, real subjects, long and short
# texts, and a dozen languages. It gets the same custom columns and reading
# history as the seed library, so both exercise the same features.
#
# Download the books first (see gutenberg-fetch.py), then:
#
#   ./calibre-zen --tool calibre-debug -e .calibre-zen/gutenberg-library.py
#   ./calibre-zen --tool calibre-debug -e .calibre-zen/gutenberg-library.py -- --limit 50 --force
#
# and open it:
#
#   CALIBRE_ZEN_LIBRARY=.calibre-zen/gutenberg-library ./calibre-zen

import argparse
import csv
import html
import importlib.util
import os
import posixpath
import random
import re
import shutil
import sys
import time
import zipfile
from datetime import UTC, datetime
from xml.etree import ElementTree as ET

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SOURCES = os.path.join(HERE, 'gutenberg-sources')
DEFAULT_OUT = os.path.join(HERE, 'gutenberg-library')
NAME = re.compile(r'pg(\d+)(?:-images)?\.epub$')
TAG = re.compile(r'<[^>]+>')
SENTENCE_END = re.compile(r'(?<=[.!?])\s+')


def load_seed():
    spec = importlib.util.spec_from_file_location('seed_library', os.path.join(HERE, 'seed-library.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_catalog(path):
    with open(path, encoding='utf-8') as f:
        return {row['Text#']: row for row in csv.DictReader(f)}


def split(value):
    return [x.strip() for x in (value or '').split(';') if x.strip()]


def shelf_tags(row):
    """Gutenberg's bookshelves as a hierarchy: 'Category: Adventure' -> 'Genre.Adventure'."""
    out = []
    for shelf in split(row.get('Bookshelves')):
        shelf = shelf.replace('.', '')
        if shelf.startswith('Category: '):
            out.append('Genre.' + shelf[len('Category: ') :])
        else:
            out.append('Bookshelf.' + shelf)
    return out


def read_text(path, r):
    """Word count, and real sentences to highlight as (spine_index, spine_name, text)."""
    ns = {'c': 'urn:oasis:names:tc:opendocument:xmlns:container', 'o': 'http://www.idpf.org/2007/opf'}
    words, passages = 0, []
    with zipfile.ZipFile(path) as z:
        opf_path = ET.fromstring(z.read('META-INF/container.xml')).find('.//c:rootfile', ns).get('full-path')
        opf = ET.fromstring(z.read(opf_path))
        base = posixpath.dirname(opf_path)
        hrefs = {i.get('id'): i.get('href') for i in opf.iterfind('.//o:manifest/o:item', ns)}
        spine = [posixpath.join(base, hrefs[i.get('idref')]) for i in opf.iterfind('.//o:spine/o:itemref', ns) if i.get('idref') in hrefs]
        for idx, name in enumerate(spine):
            try:
                text = html.unescape(TAG.sub(' ', z.read(name).decode('utf-8', 'replace')))
            except KeyError:
                continue
            words += len(text.split())
            found = [s for s in (' '.join(x.split()) for x in SENTENCE_END.split(text)) if 40 <= len(s) <= 280]
            passages.extend((idx, name, s) for s in r.sample(found, min(len(found), 4)))
    return words, r.sample(passages, min(len(passages), 80))


def build(sources, out, limit, seed):
    from calibre.ebooks.metadata.meta import get_metadata
    from calibre.utils.date import parse_only_date

    zen = load_seed()
    r = random.Random(seed)
    g = zen.Gen(r)
    t0 = time.monotonic()

    def log(msg):
        print(f'[{time.monotonic() - t0:6.1f}s] {msg}', flush=True)

    catalog = read_catalog(os.path.join(sources, 'pg_catalog.csv'))
    epub_dir = os.path.join(sources, 'epub')
    files = sorted((n for n in os.listdir(epub_dir) if NAME.search(n)), key=lambda n: int(NAME.search(n).group(1)))
    if limit:
        files = files[:limit]
    log(f'{len(files)} EPUBs, catalog of {len(catalog)} entries')

    ldb = zen.create_columns(out)
    cache = ldb.new_api
    log(f'created {len(zen.COLUMNS)} custom columns')

    people = sorted({a for n in files for a in split(catalog.get(NAME.search(n).group(1), {}).get('Authors'))}) or ['Anonymous']
    extra, passages, batch, added, failed = {}, {}, [], [], 0
    for i, name in enumerate(files):
        path = os.path.join(epub_dir, name)
        pg_id = NAME.search(name).group(1)
        row = catalog.get(pg_id, {})
        try:
            with open(path, 'rb') as f:
                mi = get_metadata(f, 'epub')
            words, found = read_text(path, r)
        except Exception as e:
            print(f'skip {name}: {e}', file=sys.stderr, flush=True)
            failed += 1
            continue
        if row:
            # The catalog's subjects are whole; the EPUB's own are split at every comma.
            mi.tags = list(dict.fromkeys(split(row.get('Subjects')) + shelf_tags(row)))
        mi.set_identifier('gutenberg', pg_id)
        mi.publisher = 'Project Gutenberg'
        if row.get('Issued'):
            mi.pubdate = parse_only_date(row['Issued'], as_utc=True)
        mi.timestamp = zen.rand_date(r, datetime(2017, 1, 1, tzinfo=UTC), zen.NOW)
        mi.rating = r.choice((None, None, None, 6, 8, 8, 10))
        idx = len(extra)
        extra[idx] = zen.reading_values(r, g, mi.timestamp, words, people)
        passages[idx] = found
        batch.append((mi, {'EPUB': path}))
        if len(batch) == 50 or i == len(files) - 1:
            ids, _ = cache.add_books(batch, add_duplicates=True, apply_import_tags=False, run_hooks=False)
            added.extend(ids)
            batch = []
            log(f'added {len(added)}/{len(files)} books')
    idmap = dict(enumerate(added))

    log(f'set {zen.apply_values(cache, idmap, extra)} custom fields')
    log(f'added {zen.add_annotations(cache, r, g, idmap, extra, passages)} annotations')
    log(f'added {zen.add_notes_and_links(cache, r, g)} notes and author/publisher links')

    cache.set_pref(
        'saved_searches',
        {
            'Unread adventure': '#read_status:Unread and tags:"=.Genre.Adventure"',
            'Highly rated, not reread': '#my_rating:>=4 and #times_read:1',
            'Long books': '#words:>150000',
            'Short reads': '#words:<20000',
            'Loaned out': '#loaned_to:true',
            'Has a review': '#review:true',
            'Juvenile fiction': 'tags:"Juvenile fiction"',
        },
    )
    cache.set_pref(
        'virtual_libraries',
        {
            'Currently reading': '#read_status:"=Reading"',
            'To read': '#read_status:"=Want to read" or #read_status:Unread',
            'Read in 2025': '#date_read:2025',
            'Novels': 'tags:"=Genre.Novels"',
            'Poetry': 'tags:"=Genre.Poetry"',
            'Not English': 'not languages:eng',
        },
    )
    shelves = sorted(t for t in cache.all_field_names('tags') if t.startswith('Genre.'))
    top_authors = sorted(cache.all_field_names('authors'))[:9]
    cache.set_pref(
        'user_categories',
        {
            'Favourites': [[a, 'authors', 0] for a in top_authors[:6]] + [[t, 'tags', 0] for t in shelves[:4]],
            'Favourites.Poets': [[a, 'authors', 0] for a in top_authors[6:9]],
        },
    )
    cache.set_pref('grouped_search_terms', {'people': ['authors', '#narrators']})

    cache.dump_metadata()
    ldb.close()
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(out) for f in fs)
    log(f'done: {len(added)} books ({failed} skipped), {size / 1e6:.0f} MB in {out}')


def main():
    ap = argparse.ArgumentParser(description='Build a calibre library from downloaded Gutenberg EPUBs.')
    ap.add_argument('--sources', default=DEFAULT_SOURCES)
    ap.add_argument('--out', default=DEFAULT_OUT)
    ap.add_argument('--limit', type=int, default=0, help='import only the first N books')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--force', action='store_true', help='replace an existing library at --out')
    args = ap.parse_args(sys.argv[1:])
    out = os.path.abspath(args.out)
    if os.path.exists(out):
        if not args.force:
            raise SystemExit(f'{out} exists; pass --force to replace it')
        if not os.path.exists(os.path.join(out, 'metadata.db')) and os.listdir(out):
            raise SystemExit(f'{out} is not empty and has no metadata.db; refusing to delete it')
        shutil.rmtree(out)
    os.makedirs(out)
    build(os.path.abspath(args.sources), out, args.limit, args.seed)


if __name__ == '__main__':
    main()

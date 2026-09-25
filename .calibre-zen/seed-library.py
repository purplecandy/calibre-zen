#!/usr/bin/env python
# seed-library.py -- build a large, messy calibre library for performance work.
#
# Every book is generated, so the library is reproducible and has no copyright
# in it. What it has instead is the shape of a real reader's library: a long
# tail of authors, series with gaps and novellas, hierarchical tags, custom
# columns of every type, reading data, highlights, notes, saved searches and
# virtual libraries, covers of odd shapes, books with several formats and books
# with none.
#
# Run it with the bundle's interpreter, through the launcher:
#
#   ./calibre-zen --tool calibre-debug -e .calibre-zen/seed-library.py
#   ./calibre-zen --tool calibre-debug -e .calibre-zen/seed-library.py -- --count 5000 --force
#
# then open it:
#
#   CALIBRE_ZEN_LIBRARY=.calibre-zen/perf-library ./calibre-zen

import argparse
import io
import os
import random
import shutil
import sys
import time
import uuid
import zipfile
from datetime import UTC, datetime, timedelta

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, 'perf-library')
NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)

# {{{ vocabulary

FIRST = (
    'Ada Alan Amara Anika Arjun Beatrix Camille Cedric Chiara Dalia Darius Delphine Eamon Elif Elena Emeka Esme '
    'Farid Felix Freya Gideon Greta Hana Hugo Ingrid Isak Ivo Jasper Jun Kaito Kalinda Keziah Lars Leila Linnea '
    'Lorenzo Mael Magnus Maren Mateo Mei Mira Nadia Naveen Nell Niamh Odile Olu Oskar Pia Priya Quentin Rafael '
    'Rhea Rosalind Rowan Sabine Saoirse Selim Soren Tamsin Teodor Thea Tobias Una Valentina Vikram Wren Xavier '
    'Yara Yusuf Zadie Zora'
).split()
LAST = (
    'Abernathy Adeyemi Albrecht Almeida Ashworth Balogun Bellamy Blackwood Castellanos Chen Corrigan Dahl Delacroix '
    'Devereux Drummond Eriksen Fairweather Falk Fontaine Galloway Gupta Halloran Hartmann Holloway Ibarra Iwasaki '
    'Jovanovic Kaur Kessler Kowalczyk Lachance Lindqvist Lockwood Mbeki Mercer Moreau Nakamura Novak Okafor Oyelaran '
    'Pemberton Petrov Quintero Rahman Ravensworth Rossi Sandoval Sato Sinclair Sorensen Takahashi Thorne Underhill '
    'Valdez Vance Wainwright Whitlock Yilmaz Zeller'
).split()
# Names calibre has to sort, search and render outside Latin-1.
EXOTIC_AUTHORS = [
    'Søren Kjærgaard',
    'Zoë Brontë-Hale',
    'José Ñúñez',
    'Łukasz Wiśniewski',
    'Anaïs Lefèvre',
    'Ómar Þórsson',
    'Анна Петрова',
    'Дмитрий Соколов',
    '山田 花子',
    '佐藤 健',
    '李 小龙',
    '김 민준',
    'ليلى حسن',
    'יעל כהן',
    'Ελένη Παπαδοπούλου',
    'Nguyễn Thị Lan',
]
ADJ = (
    'Silent Hollow Crimson Last Broken Hidden Iron Burning Glass Winter Forgotten Distant Golden Drowned Quiet '
    'Wandering Shattered Endless Pale Wild Salt Hungry Paper Midnight Brass Sunken Ashen Velvet Northern Bitter'
).split()
NOUN = (
    'Garden River Crown Mirror Lantern Harbour Orchard Kingdom Signal Tide Archive Engine Chorus Lighthouse Atlas '
    'Compass Ember Library Meridian Cartographer Orchid Citadel Machine Weaver Tower Wolf Sparrow Archipelago '
    'Clockmaker Inheritance Ferryman Alchemist Hour Season Map Door Winter Song Stars'
).split()
TOPICS = (
    'Attention|Cities|Bread|Salt|Maps|Sleep|Memory|Rivers|Trust|Clocks|Money|Weather|Numbers|Language|Glass|'
    'Forests|Silk|Fire|Ships|Coffee|Paper|Bees|Stone|Light|Soil|Music|Habit|Networks|Iron|Gardens'
).split('|')
FIELDS_OF_STUDY = (
    'Design|Machine Learning|Typography|Distributed Systems|Cognitive Science|Urban Planning|Statistics|'
    'Linear Algebra|Compilers|Ecology|Game Theory|Epidemiology|Economics|Photography|Rust|Python|Philosophy'
).split('|')
WORDS = (
    'the a of and to in that it was he she they we for on with as at by from his her their this which but had not '
    'were said into over under before after while light river stone morning evening letter voice hand window door '
    'road city field sea ship house room fire garden winter summer north south quiet slowly again never always '
    'remembered carried opened waited watched listened turned walked found lost kept called answered whispered '
    'across beneath between beyond through against toward around small old new long dark bright cold warm heavy '
    'empty strange careful certain distant familiar ordinary patient sudden gentle bitter'
).split()

TAG_TREE = {
    'Fiction': {
        'Fantasy': ['Epic', 'Urban', 'Cozy', 'Grimdark', 'Fairy Tales'],
        'Science Fiction': ['Space Opera', 'Cyberpunk', 'Hard SF', 'Time Travel', 'First Contact'],
        'Mystery': ['Cozy', 'Police Procedural', 'Noir', 'Locked Room'],
        'Literary': ['Historical', 'Contemporary', 'Magical Realism'],
        'Horror': ['Gothic', 'Cosmic', 'Folk'],
        'Romance': ['Regency', 'Contemporary'],
        'Thriller': ['Espionage', 'Legal', 'Techno'],
    },
    'Nonfiction': {
        'History': ['Ancient', 'Medieval', 'Modern', 'Maritime'],
        'Science': ['Physics', 'Biology', 'Astronomy', 'Chemistry'],
        'Computing': ['Programming', 'Machine Learning', 'Systems', 'Security'],
        'Philosophy': ['Ethics', 'Stoicism'],
        'Biography': ['Memoir', 'Artists', 'Scientists'],
        'Cooking': ['Baking', 'Vegetarian'],
        'Travel': [],
        'Self-help': [],
    },
    'Poetry': {},
    'Comics': {'Manga': [], 'Graphic Novels': []},
    'Children': {'Picture Books': [], 'Middle Grade': []},
}
FLAT_TAGS = [
    'favourite',
    'to reread',
    'book club',
    'signed',
    'award winner',
    'Hugo',
    'Nebula',
    'Booker',
    'classic',
    'audiobook companion',
    'gift',
    'sample',
    'DRM-free',
    'needs better cover',
    'metadata checked',
    'series starter',
]
PUBLISHERS = [
    'Harbour & Finch',
    'Ninefold Press',
    'Lantern House',
    'Quill Street Books',
    'Blue Heron Editions',
    'Meridian Publishing',
    'Salt Road Press',
    'Copperplate',
    'North Tower Books',
    'Oakum & Rope',
    'Paperweight',
    'Tidewater',
    'Glasshouse',
    'Kestrel Books',
    'Small Hours Press',
    'Vellum & Vine',
    'Atlas Technical',
    'Open Circuit Media',
    'Éditions du Phare',
    'Verlag Nordlicht',
    'Ediciones Faro',
    'Kōyō Shobō',
    'Self-published',
    'Project Gutenberg',
]
LANGS = ['eng'] * 30 + ['fra', 'fra', 'deu', 'deu', 'spa', 'spa', 'ita', 'jpn', 'rus', 'por', 'nld', 'ara']

READ_STATUS = ['Unread', 'Want to read', 'Reading', 'Read', 'Abandoned']
SOURCES = ['Purchase', 'Gift', 'Library', 'Gutenberg', 'Bundle', 'Review copy']
SHELVES = ['Nightstand', 'Office', 'Living room', 'Kindle', 'Kobo', 'Storage box 1', 'Storage box 2', 'Loaned out']
MOODS = [
    'dark',
    'funny',
    'hopeful',
    'tense',
    'reflective',
    'adventurous',
    'emotional',
    'informative',
    'lighthearted',
    'mysterious',
    'slow-paced',
    'fast-paced',
    'challenging',
    'relaxing',
]
FRIENDS = ['Priya', 'Tom', 'Aunt Rosa', 'Book club', 'Jun', 'Mira', 'Office library']
READING_LISTS = ['2026 Challenge', 'Summer Reads', 'Classics Catch-up', 'Book Club', 'Work: Engineering', 'Comfort Rereads', 'Around the World']
HIGHLIGHT_STYLES = [{'kind': 'color', 'type': 'builtin', 'which': w} for w in ('yellow', 'green', 'blue', 'red', 'purple')] + [
    {'kind': 'decoration', 'type': 'builtin', 'which': w} for w in ('wavy', 'strikeout')
]

# }}}


def all_tags():
    out = []
    for top, mids in TAG_TREE.items():
        out.append(top)
        for mid, leaves in mids.items():
            out.append(f'{top}.{mid}')
            out.extend(f'{top}.{mid}.{leaf}' for leaf in leaves)
    return out


class Gen:
    def __init__(self, rng):
        self.r = rng
        self.paragraphs = [self.paragraph() for _ in range(400)]

    def sentence(self, lo=6, hi=22):
        w = self.r.choices(WORDS, k=self.r.randint(lo, hi))
        return ' '.join(w).capitalize() + self.r.choice('....!?;')[0]

    def paragraph(self, lo=3, hi=9):
        return ' '.join(self.sentence() for _ in range(self.r.randint(lo, hi)))

    def person(self):
        return f'{self.r.choice(FIRST)} {self.r.choice(LAST)}'

    def fiction_title(self):
        r = self.r
        return r.choice((
            lambda: f'The {r.choice(ADJ)} {r.choice(NOUN)}',
            lambda: f'{r.choice(NOUN)} of {r.choice(NOUN)}s',
            lambda: f'A Song for the {r.choice(ADJ)} {r.choice(NOUN)}',
            lambda: f"The {r.choice(NOUN)}'s {r.choice(NOUN)}",
            lambda: f'{r.choice(ADJ)} {r.choice(NOUN)}',
            lambda: f'When the {r.choice(NOUN)} {r.choice(("Fell", "Sang", "Burned", "Returned", "Slept"))}',
            lambda: r.choice(NOUN),
        ))()

    def nonfiction_title(self):
        r = self.r
        return r.choice((
            lambda: f'A Short History of {r.choice(TOPICS)}',
            lambda: f'{r.choice(TOPICS)}: How It Shaped the World',
            lambda: f'An Introduction to {r.choice(FIELDS_OF_STUDY)}',
            lambda: f'{r.choice(FIELDS_OF_STUDY)} in Practice',
            lambda: f'Thinking About {r.choice(TOPICS)}',
            lambda: f'The {r.choice(FIELDS_OF_STUDY)} Handbook, {r.randint(2, 7)}th Edition',
            lambda: f'On {r.choice(TOPICS)}',
        ))()

    def html_comments(self):
        n = self.r.choices((0, 1, 2, 3, 6, 12), weights=(8, 30, 30, 20, 10, 2))[0]
        if not n:
            return None
        paras = [f'<p>{self.r.choice(self.paragraphs)}</p>' for _ in range(n)]
        if self.r.random() < 0.2:
            paras.insert(1, f'<p><b>{self.sentence(3, 6)}</b> <i>{self.sentence(4, 9)}</i></p>')
        if self.r.random() < 0.1:
            paras.append('<ul>' + ''.join(f'<li>{self.sentence(3, 8)}</li>' for _ in range(4)) + '</ul>')
        return '\n'.join(paras)


def isbn13(r):
    digits = [9, 7, 8] + [r.randint(0, 9) for _ in range(9)]
    check = (10 - sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits)) % 10) % 10
    return ''.join(map(str, digits + [check]))


def make_epub(title, author, lang, chapters, book_uuid):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo('mimetype'), 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        z.writestr(
            'META-INF/container.xml',
            (
                '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                '</rootfiles></container>'
            ),
        )
        manifest, spine, nav = [], [], []
        for i, (heading, paras) in enumerate(chapters, 1):
            name = f'ch{i:03d}.xhtml'
            body = ''.join(f'<p>{p}</p>' for p in paras)
            z.writestr(
                'OEBPS/' + name,
                (
                    f'<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}">'
                    f'<head><title>{heading}</title></head><body><h2>{heading}</h2>{body}</body></html>'
                ),
            )
            manifest.append(f'<item id="c{i}" href="{name}" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="c{i}"/>')
            nav.append(f'<li><a href="{name}">{heading}</a></li>')
        z.writestr(
            'OEBPS/nav.xhtml',
            (
                '<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" '
                'xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Contents</title></head><body>'
                f'<nav epub:type="toc"><ol>{"".join(nav)}</ol></nav></body></html>'
            ),
        )
        esc = lambda s: s.replace('&', '&amp;').replace('<', '&lt;')  # noqa: E731
        z.writestr(
            'OEBPS/content.opf',
            (
                '<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
                'unique-identifier="uid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                f'<dc:identifier id="uid">urn:uuid:{book_uuid}</dc:identifier><dc:title>{esc(title)}</dc:title>'
                f'<dc:creator>{esc(author)}</dc:creator><dc:language>{lang}</dc:language>'
                f'<meta property="dcterms:modified">2026-01-01T00:00:00Z</meta></metadata>'
                f'<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
                f'{"".join(manifest)}</manifest><spine>{"".join(spine)}</spine></package>'
            ),
        )
    return buf.getvalue()


def rand_date(r, start, end):
    return start + timedelta(seconds=r.uniform(0, (end - start).total_seconds()))


def build(out, count, seed):
    from calibre.db.cache import Cache  # noqa: F401  (fail early if not run by calibre-debug)
    from calibre.ebooks.covers import cprefs, generate_cover, override_prefs
    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.library import db as open_db
    from calibre.utils.podofo import sample_pdf_data

    r = random.Random(seed)
    random.seed(seed)  # generate_cover draws its colours and styles from the global generator
    g = Gen(r)
    t0 = time.monotonic()

    def log(msg):
        print(f'[{time.monotonic() - t0:6.1f}s] {msg}', flush=True)

    # {{{ custom columns -- created first, then the library is reopened so they exist
    ldb = open_db(out)
    cols = [
        # label, name, datatype, is_multiple, display
        (
            'read_status',
            'Read status',
            'enumeration',
            False,
            {'enum_values': READ_STATUS, 'enum_colors': ['', '#4a90d9', '#e6a23c', '#67c23a', '#909399'], 'use_decorations': 0},
        ),
        ('date_started', 'Started', 'datetime', False, {'date_format': 'dd MMM yyyy'}),
        ('date_read', 'Date read', 'datetime', False, {'date_format': 'dd MMM yyyy'}),
        ('times_read', 'Times read', 'int', False, {'number_format': None}),
        ('progress', 'Progress', 'float', False, {'number_format': '{:.0f}%'}),
        ('reading_minutes', 'Minutes read', 'int', False, {'number_format': '{:,d}'}),
        ('words', 'Words', 'int', False, {'number_format': '{:,d}'}),
        ('my_rating', 'My rating', 'rating', False, {'allow_half_stars': True}),
        ('shelf', 'Shelf', 'text', False, {}),
        ('moods', 'Moods', 'text', True, {}),
        ('narrators', 'Narrators', 'text', True, {'is_names': True}),
        ('owned', 'Own paper copy', 'bool', False, {'bools_show_text': True, 'bools_show_icons': True}),
        ('loaned_to', 'Loaned to', 'text', False, {}),
        ('reading_list', 'Reading list', 'series', False, {}),
        ('review', 'My review', 'comments', False, {'interpret_as': 'html', 'heading_position': 'side'}),
        ('quote', 'Favourite quote', 'comments', False, {'interpret_as': 'long-text', 'heading_position': 'above'}),
        ('acquired', 'Acquired', 'datetime', False, {'date_format': 'MMM yyyy'}),
        ('price', 'Price', 'float', False, {'number_format': '{:.2f}'}),
        ('source', 'Source', 'enumeration', False, {'enum_values': SOURCES, 'enum_colors': []}),
        (
            'read_summary',
            'Reading',
            'composite',
            False,
            {'composite_template': '{#read_status}{#date_read:| on |}', 'composite_sort': 'text', 'make_category': False, 'contains_html': False},
        ),
        (
            'days_since_read',
            'Days since read',
            'composite',
            False,
            {
                'composite_template': "program: d = raw_field('#date_read', ''); if d then format_number(days_between(today(), d), '{0:.0f}') fi",
                'composite_sort': 'number',
                'make_category': False,
                'contains_html': False,
            },
        ),
        (
            'people',
            'People',
            'composite',
            True,
            {'composite_template': '{authors}{#narrators:| & |}', 'composite_sort': 'text', 'make_category': True, 'contains_html': False, 'is_names': True},
        ),
    ]
    for label, name, dt, mult, disp in cols:
        ldb.new_api.create_custom_column(label, name, dt, mult, display=disp)
    ldb.close()
    ldb = open_db(out)
    cache = ldb.new_api
    log(f'created {len(cols)} custom columns')
    # }}}

    # {{{ the cast: authors with a long tail, series owned by authors
    authors = sorted({g.person() for _ in range(700)})[:420] + EXOTIC_AUTHORS
    weights = [1 / (i + 1) ** 0.85 for i in range(len(authors))]
    r.shuffle(authors)
    tags = all_tags()
    fiction_tags = [t for t in tags if t.startswith(('Fiction', 'Poetry', 'Comics', 'Children'))]
    nonfiction_tags = [t for t in tags if t.startswith('Nonfiction')]
    series = {}
    for name in {f'{g.fiction_title()} {r.choice(("Cycle", "Chronicles", "Saga", "Trilogy", "Quartet", ""))}'.strip() for _ in range(180)}:
        series[name] = {'author': r.choices(authors, weights)[0], 'next': 1.0}
    series_names = list(series)
    # }}}

    cover_shapes = [(600, 900)] * 14 + [(600, 960), (600, 800), (700, 700), (500, 1000), (900, 600), (300, 450)]
    base_cover_prefs = {k: cprefs[k] for k in cprefs.defaults}
    cover_cache = {}

    def cover_for(mi):
        w, h = r.choice(cover_shapes)
        key = (mi.title, w, h)
        if key not in cover_cache:
            p = override_prefs(base_cover_prefs, cover_width=w, cover_height=h)
            cover_cache[key] = generate_cover(mi, prefs=p)
        return cover_cache[key]

    tmp = os.path.join(out, '.seed-tmp')
    os.makedirs(tmp, exist_ok=True)
    pdf = sample_pdf_data()
    extra = {}  # book index -> dict of custom column values applied after adding
    batch, added = [], []

    for i in range(count):
        mi = Metadata('', [])
        nonfiction = r.random() < 0.28
        in_series = not nonfiction and r.random() < 0.45
        if in_series:
            sname = r.choice(series_names)
            s = series[sname]
            mi.series = sname
            idx = s['next']
            if r.random() < 0.08:
                idx -= 0.5  # a novella between two books
            elif r.random() < 0.06:
                s['next'] += 1  # a gap: book missing from the library
            mi.series_index = idx
            s['next'] += 1
            main_author = s['author']
        else:
            main_author = r.choices(authors, weights)[0]
        roll = r.random()
        if roll < 0.012:
            mi.authors = r.sample(authors, r.randint(12, 30))  # anthology
        elif roll < 0.10:
            mi.authors = [main_author] + r.sample(authors, r.randint(1, 3))
        elif roll < 0.105:
            mi.authors = []  # Unknown
        else:
            mi.authors = [main_author]

        title = g.nonfiction_title() if nonfiction else g.fiction_title()
        if r.random() < 0.02:
            title += ': ' + ' '.join(g.sentence(12, 20).split()[:18])  # absurdly long
        elif r.random() < 0.08:
            title += ': ' + g.fiction_title()
        mi.title = title
        mi.languages = [r.choice(LANGS)]
        mi.publisher = r.choice(PUBLISHERS) if r.random() < 0.9 else None
        mi.pubdate = rand_date(r, datetime(1850, 1, 1, tzinfo=UTC), NOW) if r.random() < 0.93 else None
        if mi.pubdate and r.random() < 0.7:
            mi.pubdate = rand_date(r, datetime(1990, 1, 1, tzinfo=UTC), NOW)
        mi.timestamp = rand_date(r, datetime(2017, 1, 1, tzinfo=UTC), NOW)
        mi.rating = r.choice((None, None, 2, 4, 6, 6, 8, 8, 8, 10, 10, 5, 7, 9))
        pool = nonfiction_tags if nonfiction else fiction_tags
        n = r.choices((0, 1, 2, 3, 4, 6, 9, 40), weights=(4, 15, 25, 25, 15, 10, 5, 1))[0]
        mi.tags = r.sample(pool, min(n, len(pool))) + r.sample(FLAT_TAGS, r.choices((0, 1, 2), (6, 3, 1))[0])
        if n == 40:
            mi.tags += r.sample(FLAT_TAGS, 10)
        ids = {}
        if r.random() < 0.8:
            ids['isbn'] = isbn13(r)
        if r.random() < 0.5:
            ids['goodreads'] = str(r.randint(1000, 60000000))
        if r.random() < 0.3:
            ids['amazon'] = 'B0' + ''.join(r.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789', k=8))
        if r.random() < 0.2:
            ids['google'] = ''.join(r.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-', k=12))
        mi.identifiers = ids
        mi.comments = g.html_comments()
        if r.random() < 0.96:
            mi.cover_data = ('jpg', cover_for(mi))

        # formats
        book_uuid = str(uuid.uuid4())
        n_ch = r.choices((3, 8, 15, 30, 60), weights=(20, 35, 30, 12, 3))[0]
        chapters = [(f'Chapter {c}', r.choices(g.paragraphs, k=r.randint(4, 40))) for c in range(1, n_ch + 1)]
        words = sum(len(p.split()) for _, ps in chapters for p in ps)
        fmt_roll = r.random()
        fmts = {}
        author_str = mi.authors[0] if mi.authors else 'Unknown'
        if fmt_roll < 0.93:
            base = os.path.join(tmp, f'{i}')
            want = r.choices((('EPUB',), ('EPUB', 'PDF'), ('PDF',), ('TXT',), ('EPUB', 'TXT', 'PDF')), weights=(75, 11, 5, 5, 4))[0]
            for fmt in want:
                path = f'{base}.{fmt.lower()}'
                with open(path, 'wb') as f:
                    if fmt == 'EPUB':
                        f.write(make_epub(mi.title, author_str, mi.languages[0], chapters, book_uuid))
                    elif fmt == 'PDF':
                        f.write(pdf)
                    else:
                        f.write('\n\n'.join(p for _, ps in chapters for p in ps).encode())
                fmts[fmt] = path

        # reading data
        status = r.choices(READ_STATUS, weights=(40, 18, 6, 32, 4))[0]
        vals = {
            '#read_status': status,
            '#words': words,
            '#source': r.choice(SOURCES),
            '#acquired': mi.timestamp - timedelta(days=r.randint(0, 400)) if r.random() < 0.7 else None,
        }
        if status in ('Reading', 'Read', 'Abandoned'):
            started = rand_date(r, max(mi.timestamp, NOW - timedelta(days=3000)), NOW - timedelta(days=2))
            vals['#date_started'] = started
            vals['#progress'] = 100.0 if status == 'Read' else round(r.uniform(2, 95), 1)
            vals['#reading_minutes'] = int(words / 250 * vals['#progress'] / 100 * r.uniform(0.8, 1.4))
            if status == 'Read':
                vals['#date_read'] = min(NOW, started + timedelta(days=r.randint(1, 90)))
                vals['#times_read'] = r.choices((1, 2, 3, 7), weights=(80, 14, 5, 1))[0]
                vals['#my_rating'] = r.choice((4, 6, 7, 8, 8, 9, 10, 10))
                if r.random() < 0.3:
                    vals['#review'] = g.html_comments()
                if r.random() < 0.15:
                    vals['#quote'] = g.sentence(10, 30)
            vals['#moods'] = r.sample(MOODS, r.randint(1, 4))
        if r.random() < 0.55:
            vals['#shelf'] = r.choice(SHELVES)
        vals['#owned'] = r.choice((True, False, None))
        if vals.get('#shelf') == 'Loaned out' or r.random() < 0.02:
            vals['#loaned_to'] = r.choice(FRIENDS)
        if r.random() < 0.08:
            vals['#narrators'] = r.sample(authors, r.randint(1, 2))
        if vals['#source'] in ('Purchase', 'Bundle'):
            vals['#price'] = round(r.choice((0.99, 2.99, 4.99, 7.99, 9.99, 12.99, 14.99, 24.99, 49.0)), 2)
        if r.random() < 0.12:
            vals['#reading_list'] = r.choice(READING_LISTS)
        extra[i] = vals
        batch.append((mi, fmts))

        if len(batch) == 100 or i == count - 1:
            ids_, _ = cache.add_books(batch, add_duplicates=True, apply_import_tags=False, run_hooks=False)
            added.extend(ids_)
            for _, fm in batch:
                for p in fm.values():
                    os.remove(p)
            batch = []
            log(f'added {len(added)}/{count} books')
    shutil.rmtree(tmp)
    idmap = dict(enumerate(added))

    # {{{ custom column values, one bulk write per column
    by_field = {}
    for i, vals in extra.items():
        for k, v in vals.items():
            if v is not None:
                by_field.setdefault(k, {})[idmap[i]] = v
    list_next = {}
    for book_id in sorted(by_field.get('#reading_list', {})):
        name = by_field['#reading_list'][book_id]
        list_next[name] = list_next.get(name, 0) + 1
        by_field.setdefault('#reading_list_index', {})[book_id] = float(list_next[name])
    for field, m in by_field.items():
        cache.set_field(field, m)
    log(f'set {len(by_field)} custom fields')
    # }}}

    # {{{ annotations: highlights and bookmarks on books that were opened
    now_iso = lambda d: d.astimezone(UTC).isoformat().replace('+00:00', 'Z')  # noqa: E731
    n_annots = 0
    for i, vals in extra.items():
        book_id = idmap[i]
        if vals['#read_status'] not in ('Reading', 'Read') or r.random() > 0.35:
            continue
        fmts = cache.formats(book_id)
        if 'EPUB' not in fmts:
            continue
        count_h = r.choices((1, 3, 8, 20, 80, 400), weights=(20, 30, 25, 15, 8, 2))[0]
        annots = []
        for _ in range(count_h):
            ts = now_iso(rand_date(r, vals['#date_started'], vals.get('#date_read') or NOW))
            spine = r.randint(0, 5)
            if r.random() < 0.85:
                text = g.sentence(5, 40)
                annots.append({
                    'type': 'highlight',
                    'uuid': uuid.uuid4().hex,
                    'timestamp': ts,
                    'highlighted_text': text,
                    'notes': g.sentence(4, 20) if r.random() < 0.3 else '',
                    'spine_index': spine,
                    'spine_name': f'OEBPS/ch{spine + 1:03d}.xhtml',
                    'start_cfi': f'/4/2/{2 * r.randint(1, 30)}/1:0',
                    'end_cfi': f'/4/2/{2 * r.randint(31, 60)}/1:{len(text)}',
                    'style': r.choice(HIGHLIGHT_STYLES),
                    'toc_family_titles': [f'Chapter {spine + 1}'],
                })
            else:
                annots.append({
                    'type': 'bookmark',
                    'title': f'Chapter {spine + 1}',
                    'timestamp': ts,
                    'pos_type': 'epubcfi',
                    'pos': f'epubcfi(/{2 * (spine + 1)}/4/2/{2 * r.randint(1, 40)})',
                })
        cache.merge_annotations_for_book(book_id, 'EPUB', annots)
        n_annots += len(annots)
    log(f'added {n_annots} annotations')
    # }}}

    # {{{ notes and links on authors, series, tags, publishers
    def note_doc():
        return ''.join(f'<p>{r.choice(g.paragraphs)}</p>' for _ in range(r.randint(1, 5)))

    notes = 0
    for field, share in (('authors', 0.3), ('series', 0.2), ('tags', 0.15), ('publisher', 0.5), ('#shelf', 1.0)):
        if not cache.field_supports_notes(field):
            continue
        for item_id in cache.all_field_ids(field):
            if r.random() < share:
                cache.set_notes_for(field, item_id, note_doc())
                notes += 1
    cache.set_link_map('authors', {a: 'https://en.wikipedia.org/wiki/' + a.replace(' ', '_') for a in cache.all_field_names('authors') if r.random() < 0.4})
    cache.set_link_map('publisher', {p: f'https://example.org/publishers/{i}' for i, p in enumerate(PUBLISHERS)})
    log(f'added {notes} notes and author/publisher links')
    # }}}

    # {{{ searches, virtual libraries, user categories
    cache.set_pref(
        'saved_searches',
        {
            'Unread fantasy': '#read_status:Unread and tags:"=.Fiction.Fantasy"',
            'Highly rated, not reread': '#my_rating:>=4 and #times_read:1',
            'Long books': '#words:>200000',
            'Missing ISBN': 'not identifiers:isbn:',
            'Loaned out': '#loaned_to:true',
            'Has a review': '#review:true',
            'No formats': 'formats:false',
            'Series gaps': 'series:true and series_index:>10',
        },
    )
    cache.set_pref(
        'virtual_libraries',
        {
            'Currently reading': '#read_status:"=Reading"',
            'To read': '#read_status:"=Want to read" or #read_status:Unread',
            'Read in 2025': '#date_read:2025',
            'Fiction': 'tags:"=.Fiction"',
            'Nonfiction': 'tags:"=.Nonfiction"',
            'On the Kindle': '#shelf:Kindle',
            'Not English': 'not languages:eng',
        },
    )
    top_authors = sorted(cache.all_field_names('authors'))[:12]
    cache.set_pref(
        'user_categories',
        {
            'Favourites': [[a, 'authors', 0] for a in top_authors[:6]] + [[s, 'series', 0] for s in series_names[:5]],
            'Favourites.Poets': [[a, 'authors', 0] for a in top_authors[6:9]],
            'Book club picks': [[t, 'tags', 0] for t in ('book club', 'award winner')],
        },
    )
    cache.set_pref('grouped_search_terms', {'people': ['authors', '#narrators']})
    # }}}

    cache.dump_metadata()
    ldb.close()
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(out) for f in fs)
    log(f'done: {len(added)} books, {size / 1e6:.0f} MB in {out}')


def main():
    ap = argparse.ArgumentParser(description='Seed a large generated calibre library.')
    ap.add_argument('--out', default=DEFAULT_OUT)
    ap.add_argument('--count', type=int, default=2000)
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
    build(out, args.count, args.seed)


if __name__ == '__main__':
    main()
